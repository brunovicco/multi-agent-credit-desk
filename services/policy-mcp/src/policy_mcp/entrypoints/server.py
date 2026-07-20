"""Composition root for the policy-mcp MCP server.

Wires ``CreditCorePolicySource`` to ``PolicyCatalogQueries`` and registers the three read-only
tools: ``list_policies``, ``get_policy``, and ``list_critical_flags``. Per
``.claude/rules/api-boundaries.md``, ``PolicyNotFoundError`` is mapped here to a stable,
machine-readable MCP tool error (``isError=True``, code ``"POLICY_NOT_FOUND"``) rather than a raw
exception message or stack trace. Each call emits one structured log line: tool name, requested
version where applicable, outcome, and duration in milliseconds - never payload or content, per
``AGENTS.md``.
"""

import json
import logging
import time

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from policy_mcp.adapters.credit_core_policy_source import CreditCorePolicySource
from policy_mcp.application.queries import PolicyCatalogQueries
from policy_mcp.domain.errors import PolicyNotFoundError
from policy_mcp.entrypoints import schemas

logger = logging.getLogger(__name__)

_POLICY_NOT_FOUND_CODE = "POLICY_NOT_FOUND"
_SERVER_NAME = "policy-mcp"


def build_server(queries: PolicyCatalogQueries | None = None) -> FastMCP:
    """Build the policy-mcp MCP server and register its three read-only tools.

    Args:
        queries: The policy catalog query service to use. Defaults to a
            ``PolicyCatalogQueries`` backed by ``CreditCorePolicySource``. Tests inject a fake
            port here to stay isolated from ``credit_core``, per ``.claude/rules/testing.md``.

    Returns:
        A fully configured ``FastMCP`` server instance.
    """
    resolved_queries = (
        queries if queries is not None else PolicyCatalogQueries(CreditCorePolicySource())
    )
    server = FastMCP(name=_SERVER_NAME)

    @server.tool(structured_output=False)
    def list_policies() -> schemas.PolicyListResult:
        """List a short summary of every known credit policy version."""
        started = time.monotonic()
        result = schemas.to_policy_list_result(resolved_queries.list_policies())
        _log_tool_call("list_policies", version=None, outcome="ok", started=started)
        return result

    @server.tool(structured_output=False)
    def get_policy(version: str) -> schemas.PolicyDetail | CallToolResult:
        """Get the full detail of one credit policy version.

        Args:
            version: The policy version identifier to look up.
        """
        started = time.monotonic()
        try:
            detail = resolved_queries.get_policy(version)
        except PolicyNotFoundError:
            _log_tool_call("get_policy", version=version, outcome="not_found", started=started)
            return _policy_not_found_result(version)
        _log_tool_call("get_policy", version=version, outcome="ok", started=started)
        return schemas.to_policy_detail(detail)

    @server.tool(structured_output=False)
    def list_critical_flags() -> schemas.CriticalFlagCatalog:
        """List every synthetic critical flag that forces a deterministic block."""
        started = time.monotonic()
        result = schemas.to_critical_flag_catalog(resolved_queries.list_critical_flags())
        _log_tool_call("list_critical_flags", version=None, outcome="ok", started=started)
        return result

    return server


def _policy_not_found_result(version: str) -> CallToolResult:
    """Build a stable, machine-readable MCP tool error for an unknown policy version.

    Args:
        version: The unknown policy version that was requested.

    Returns:
        A ``CallToolResult`` with ``isError=True`` and a JSON body carrying a stable
        ``"POLICY_NOT_FOUND"`` code - never the underlying exception's message or stack trace.
    """
    payload = {
        "code": _POLICY_NOT_FOUND_CODE,
        "message": f"No policy found for version {version!r}.",
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        isError=True,
    )


def _log_tool_call(tool: str, *, version: str | None, outcome: str, started: float) -> None:
    """Emit one structured log line for a completed tool call.

    Args:
        tool: The tool name that was called.
        version: The requested policy version, if applicable to the tool.
        outcome: A short, stable outcome label (e.g. ``"ok"``, ``"not_found"``).
        started: The ``time.monotonic()`` value captured when the call began.
    """
    duration_ms = (time.monotonic() - started) * 1000
    logger.info(
        "policy_mcp.tool_call",
        extra={
            "tool": tool,
            "version": version,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 3),
        },
    )
