"""Composition root for the bureau-mcp MCP server.

Wires ``SyntheticBureauSource`` to ``BureauReportQueries`` and registers the single read-only
tool, ``get_bureau_report``. Per ``.claude/rules/api-boundaries.md``, ``InvalidCnpjError`` and
``CnpjNotFoundError`` are mapped here to stable, machine-readable MCP tool errors
(``isError=True``, codes ``"INVALID_CNPJ"`` and ``"CNPJ_NOT_FOUND"``) rather than a raw
exception message or stack trace. Each call emits one structured log line: tool name, outcome,
and duration in milliseconds - never the CNPJ or report content, per AGENTS.md.
"""

import json
import logging
import time

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from bureau_mcp.adapters.synthetic_bureau_source import SyntheticBureauSource
from bureau_mcp.application.queries import BureauReportQueries
from bureau_mcp.domain.errors import CnpjNotFoundError, InvalidCnpjError
from bureau_mcp.entrypoints import schemas

logger = logging.getLogger(__name__)

_INVALID_CNPJ_CODE = "INVALID_CNPJ"
_CNPJ_NOT_FOUND_CODE = "CNPJ_NOT_FOUND"
_SERVER_NAME = "bureau-mcp"


def build_server(queries: BureauReportQueries | None = None) -> FastMCP:
    """Build the bureau-mcp MCP server and register its single read-only tool.

    Args:
        queries: The bureau report query service to use. Defaults to a
            ``BureauReportQueries`` backed by ``SyntheticBureauSource``. Tests inject a fake
            port here to stay isolated from the shipped dataset, per
            ``.claude/rules/testing.md``.

    Returns:
        A fully configured ``FastMCP`` server instance.
    """
    resolved_queries = (
        queries if queries is not None else BureauReportQueries(SyntheticBureauSource())
    )
    server = FastMCP(name=_SERVER_NAME)

    @server.tool(structured_output=False)
    def get_bureau_report(cnpj: str) -> schemas.BureauReport | CallToolResult:
        """Get the synthetic credit-bureau report for one company.

        Args:
            cnpj: The company's CNPJ, punctuated or digits-only.
        """
        started = time.monotonic()
        try:
            bureau_report = resolved_queries.get_report(cnpj)
        except InvalidCnpjError:
            _log_tool_call("get_bureau_report", outcome="invalid_cnpj", started=started)
            return _invalid_cnpj_result()
        except CnpjNotFoundError:
            _log_tool_call("get_bureau_report", outcome="not_found", started=started)
            return _cnpj_not_found_result()
        _log_tool_call("get_bureau_report", outcome="ok", started=started)
        return schemas.to_bureau_report(bureau_report)

    return server


def _invalid_cnpj_result() -> CallToolResult:
    """Build a stable, machine-readable MCP tool error for a malformed CNPJ.

    Returns:
        A ``CallToolResult`` with ``isError=True`` and a JSON body carrying a stable
        ``"INVALID_CNPJ"`` code - never the underlying exception's message, which would echo
        the raw input back verbatim.
    """
    payload = {"code": _INVALID_CNPJ_CODE, "message": "The provided CNPJ is not valid."}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        isError=True,
    )


def _cnpj_not_found_result() -> CallToolResult:
    """Build a stable, machine-readable MCP tool error for an unknown CNPJ.

    Returns:
        A ``CallToolResult`` with ``isError=True`` and a JSON body carrying a stable
        ``"CNPJ_NOT_FOUND"`` code - never the underlying exception's message or stack trace.
    """
    payload = {
        "code": _CNPJ_NOT_FOUND_CODE,
        "message": "No bureau report was found for the provided CNPJ.",
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        isError=True,
    )


def _log_tool_call(tool: str, *, outcome: str, started: float) -> None:
    """Emit one structured log line for a completed tool call.

    Args:
        tool: The tool name that was called.
        outcome: A short, stable outcome label (e.g. ``"ok"``, ``"not_found"``).
        started: The ``time.monotonic()`` value captured when the call began.
    """
    duration_ms = (time.monotonic() - started) * 1000
    logger.info(
        "bureau_mcp.tool_call",
        extra={
            "tool": tool,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 3),
        },
    )
