"""Adapter that queries policy-mcp's catalog over the real MCP protocol.

Spawns ``python -m policy_mcp`` as a stdio subprocess per call, per this package's first
milestone scope (no long-lived A2A task session yet to hold a persistent MCP session open) - see
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``. This is the only
module that speaks the MCP protocol; ``application.evaluate`` depends only on
``application.ports.PolicyCatalogPort``.

Every failure mode of the subprocess and the MCP session - a bad command, a crashed or hung
policy-mcp process, a malformed tool response - is translated into ``PolicyCatalogUnavailableError``
here, per ``.claude/rules/architecture.md``'s "translate infrastructure exceptions before they
leave an adapter". An explicit overall timeout bounds every call, per AGENTS.md's "add explicit
timeouts to external calls".
"""

import json
import os
import sys
from collections.abc import Sequence
from datetime import timedelta

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

from decisao_agent.application.ports import PolicyCatalogSnapshot
from decisao_agent.domain.errors import PolicyCatalogUnavailableError

_DEFAULT_ARGS: tuple[str, ...] = ("-m", "policy_mcp")
_DEFAULT_TIMEOUT_SECONDS = 30.0


class PolicyMcpClient:
    """``PolicyCatalogPort`` implementation backed by a real policy-mcp MCP server process."""

    def __init__(
        self,
        command: str | None = None,
        args: Sequence[str] = _DEFAULT_ARGS,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the client with the command used to spawn policy-mcp.

        Args:
            command: The executable to spawn. Defaults to the current Python interpreter
                (``sys.executable``), so the packaged policy-mcp is used without a separate
                install step.
            args: The arguments passed to ``command``. Defaults to ``-m policy_mcp``.
            timeout_seconds: The overall deadline for spawning policy-mcp, completing the MCP
                handshake, and both tool calls.
        """
        self._command = command if command is not None else sys.executable
        self._args = tuple(args)
        self._timeout_seconds = timeout_seconds

    async def snapshot(self) -> PolicyCatalogSnapshot:
        """Fetch the current known critical flag names and policy versions from policy-mcp.

        Returns:
            A ``PolicyCatalogSnapshot`` covering policy-mcp's current catalog.

        Raises:
            PolicyCatalogUnavailableError: If policy-mcp cannot be spawned or reached within
                the configured timeout, either tool call returns an MCP tool error, or a
                response does not have the expected shape.
        """
        try:
            return await self._fetch_snapshot()
        except PolicyCatalogUnavailableError:
            raise
        except Exception as exc:
            raise PolicyCatalogUnavailableError(
                "failed to reach the policy-mcp subprocess"
            ) from exc

    async def _fetch_snapshot(self) -> PolicyCatalogSnapshot:
        """Run the actual MCP session, with no exception translation.

        Returns:
            A ``PolicyCatalogSnapshot`` covering policy-mcp's current catalog.
        """
        server_params = StdioServerParameters(
            command=self._command,
            args=list(self._args),
            env={**os.environ, "POLICY_MCP_TRANSPORT": "stdio"},
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
                critical_flags_result = await session.call_tool("list_critical_flags", {})
                policies_result = await session.call_tool("list_policies", {})

        return PolicyCatalogSnapshot(
            known_critical_flag_names=_extract_string_field(
                critical_flags_result, "list_critical_flags", "critical_flags", "name"
            ),
            known_policy_versions=_extract_string_field(
                policies_result, "list_policies", "policies", "version"
            ),
        )


def _extract_string_field(
    result: CallToolResult, tool_name: str, list_field: str, item_field: str
) -> frozenset[str]:
    """Extract a set of string values from one field of every item in a JSON list.

    Args:
        result: The tool call result to extract from.
        tool_name: The tool name that was called, used only for error messages.
        list_field: The top-level JSON body field expected to hold a list of objects.
        item_field: The string field expected on every item of ``list_field``.

    Returns:
        The set of ``item_field`` values across every item.

    Raises:
        PolicyCatalogUnavailableError: If ``result.isError`` is ``True``, the result does not
            have the expected ``{list_field: [{item_field: str}, ...]}`` shape, or its text
            content is not valid JSON.
    """
    if result.isError:
        raise PolicyCatalogUnavailableError(f"{tool_name} returned an MCP tool error")
    if len(result.content) != 1 or not isinstance(result.content[0], TextContent):
        raise PolicyCatalogUnavailableError(f"{tool_name} returned an unexpected result shape")

    try:
        body = json.loads(result.content[0].text)
    except json.JSONDecodeError as exc:
        raise PolicyCatalogUnavailableError(f"{tool_name} returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise PolicyCatalogUnavailableError(f"{tool_name} returned a non-object JSON body")

    items = body.get(list_field)
    if not isinstance(items, list):
        raise PolicyCatalogUnavailableError(f"{tool_name} did not return a {list_field!r} list")

    values: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(item_field), str):
            raise PolicyCatalogUnavailableError(
                f"{tool_name} returned a {list_field!r} item without a string {item_field!r}"
            )
        values.add(item[item_field])
    return frozenset(values)
