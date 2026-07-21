"""Adapter that queries bureau-mcp's report over the real MCP protocol.

Spawns ``python -m bureau_mcp`` as a stdio subprocess per call, mirroring
``decisao_agent.adapters.policy_mcp_client``'s pattern - no long-lived MCP session held open
across calls in this milestone's scope. This is the only module that speaks the MCP protocol;
``application.assess`` depends only on ``application.ports.BureauReportPort``.

bureau-mcp's own stable tool-error codes (``INVALID_CNPJ``, ``CNPJ_NOT_FOUND``) are translated
into cadastral-agent's own domain errors here; every other failure mode of the subprocess and the
MCP session - a bad command, a crashed or hung process, a malformed tool response - is translated
into ``BureauReportUnavailableError``, per ``.claude/rules/architecture.md``'s "translate
infrastructure exceptions before they leave an adapter". An explicit overall timeout bounds every
call, per AGENTS.md's "add explicit timeouts to external calls".
"""

import json
import os
import sys
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

from cadastral_agent.domain.bureau_finding import (
    BureauFinding,
    NegativeRecordFinding,
    NegativeRecordKind,
)
from cadastral_agent.domain.errors import (
    BureauReportUnavailableError,
    CnpjNotFoundError,
    InvalidCnpjError,
)

_DEFAULT_ARGS: tuple[str, ...] = ("-m", "bureau_mcp")
_DEFAULT_TIMEOUT_SECONDS = 30.0
_INVALID_CNPJ_CODE = "INVALID_CNPJ"
_CNPJ_NOT_FOUND_CODE = "CNPJ_NOT_FOUND"


class BureauMcpClient:
    """``BureauReportPort`` implementation backed by a real bureau-mcp MCP server process."""

    def __init__(
        self,
        command: str | None = None,
        args: Sequence[str] = _DEFAULT_ARGS,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the client with the command used to spawn bureau-mcp.

        Args:
            command: The executable to spawn. Defaults to the current Python interpreter
                (``sys.executable``), so the packaged bureau-mcp is used without a separate
                install step.
            args: The arguments passed to ``command``. Defaults to ``-m bureau_mcp``.
            timeout_seconds: The overall deadline for spawning bureau-mcp, completing the MCP
                handshake, and the tool call.
        """
        self._command = command if command is not None else sys.executable
        self._args = tuple(args)
        self._timeout_seconds = timeout_seconds

    async def get_report(self, cnpj: str) -> BureauFinding:
        """Fetch the bureau finding for one company.

        Args:
            cnpj: The company's CNPJ, punctuated or digits-only.

        Returns:
            The bureau finding for ``cnpj``.

        Raises:
            InvalidCnpjError: If ``cnpj`` is not a validly formatted identifier.
            CnpjNotFoundError: If bureau-mcp has no report on file for ``cnpj``.
            BureauReportUnavailableError: If bureau-mcp cannot be spawned or reached within the
                configured timeout, or the tool call returns an unexpected result shape.
        """
        try:
            return await self._fetch_report(cnpj)
        except (InvalidCnpjError, CnpjNotFoundError, BureauReportUnavailableError):
            raise
        except Exception as exc:
            raise BureauReportUnavailableError("failed to reach the bureau-mcp subprocess") from exc

    async def _fetch_report(self, cnpj: str) -> BureauFinding:
        """Run the actual MCP session and parse its result, with minimal exception translation.

        Args:
            cnpj: The company's CNPJ, punctuated or digits-only.

        Returns:
            The bureau finding for ``cnpj``.
        """
        server_params = StdioServerParameters(
            command=self._command,
            args=list(self._args),
            env={**os.environ, "BUREAU_MCP_TRANSPORT": "stdio"},
        )
        with anyio.fail_after(self._timeout_seconds):
            async with (
                stdio_client(server_params) as (read_stream, write_stream),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self._timeout_seconds),
                ) as session,
            ):
                await session.initialize()
                result = await session.call_tool("get_bureau_report", {"cnpj": cnpj})

        return _parse_bureau_report_result(result)


def _parse_bureau_report_result(result: CallToolResult) -> BureauFinding:
    """Parse a ``get_bureau_report`` tool result into a ``BureauFinding``.

    Args:
        result: The raw tool call result to parse.

    Returns:
        The parsed bureau finding.

    Raises:
        InvalidCnpjError: If the result carries bureau-mcp's ``INVALID_CNPJ`` error code.
        CnpjNotFoundError: If the result carries bureau-mcp's ``CNPJ_NOT_FOUND`` error code.
        BureauReportUnavailableError: If the result is an unrecognized error, or does not have
            the expected result shape.
    """
    if len(result.content) != 1 or not isinstance(result.content[0], TextContent):
        raise BureauReportUnavailableError("get_bureau_report returned an unexpected result shape")

    try:
        body = json.loads(result.content[0].text)
    except json.JSONDecodeError as exc:
        raise BureauReportUnavailableError("get_bureau_report returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise BureauReportUnavailableError("get_bureau_report returned a non-object JSON body")

    if result.isError:
        code = body.get("code")
        if code == _INVALID_CNPJ_CODE:
            raise InvalidCnpjError
        if code == _CNPJ_NOT_FOUND_CODE:
            raise CnpjNotFoundError
        raise BureauReportUnavailableError(
            f"get_bureau_report returned an unrecognized error code: {code!r}"
        )

    return _bureau_finding_from_body(body)


def _bureau_finding_from_body(body: dict[str, object]) -> BureauFinding:
    """Map a validated JSON body into a ``BureauFinding``.

    Args:
        body: The parsed JSON body of a successful ``get_bureau_report`` result.

    Returns:
        The parsed bureau finding.

    Raises:
        BureauReportUnavailableError: If ``body`` does not have the expected shape.
    """
    cnpj = body.get("cnpj")
    records = body.get("negative_records")
    if not isinstance(cnpj, str) or not isinstance(records, list):
        raise BureauReportUnavailableError("get_bureau_report returned a malformed report body")

    external_score = _decimal_field(body.get("external_score"), "external_score")
    negative_records = tuple(_negative_record_from_body(record) for record in records)
    return BureauFinding(
        cnpj=cnpj, external_score=external_score, negative_records=negative_records
    )


def _negative_record_from_body(record: object) -> NegativeRecordFinding:
    """Map one item of ``negative_records`` into a ``NegativeRecordFinding``.

    Args:
        record: The raw JSON item to map.

    Returns:
        The parsed negative record finding.

    Raises:
        BureauReportUnavailableError: If ``record`` does not have the expected shape.
    """
    if not isinstance(record, dict):
        raise BureauReportUnavailableError("get_bureau_report returned a malformed negative record")

    kind_value = record.get("kind")
    try:
        kind = NegativeRecordKind(kind_value)
    except ValueError as exc:
        raise BureauReportUnavailableError(
            f"get_bureau_report returned an unknown record kind: {kind_value!r}"
        ) from exc

    registered_days_ago = record.get("registered_days_ago")
    if not isinstance(registered_days_ago, int):
        raise BureauReportUnavailableError(
            "get_bureau_report returned a malformed registered_days_ago"
        )

    amount = _decimal_field(record.get("amount"), "amount")
    return NegativeRecordFinding(kind=kind, amount=amount, registered_days_ago=registered_days_ago)


def _decimal_field(value: object, field_name: str) -> Decimal:
    """Parse one JSON field expected to hold a decimal-safe numeric string.

    Args:
        value: The raw field value to parse.
        field_name: The field name, used only for the error message.

    Returns:
        The parsed ``Decimal``.

    Raises:
        BureauReportUnavailableError: If ``value`` is not a valid decimal.
    """
    if not isinstance(value, str | int):
        raise BureauReportUnavailableError(f"get_bureau_report returned a malformed {field_name}")
    try:
        return Decimal(value) if isinstance(value, str) else Decimal(str(value))
    except InvalidOperation as exc:
        raise BureauReportUnavailableError(
            f"get_bureau_report returned a malformed {field_name}"
        ) from exc
