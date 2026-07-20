"""Proves `python -m policy_mcp` works end to end as a real subprocess over stdio.

Spawns the packaged CLI entrypoint (not an in-process fake), performs one real MCP
initialize handshake, and calls one tool - proving the console entrypoint, transport selection,
and the full server wiring work together, not just the composition root in isolation.

Matches the existing pattern in `tests/integration/test_otel_collector_langfuse.py`: excluded from
the default `uv run pytest` gate via the `not integration` marker filter, run explicitly with
`uv run pytest -m integration services/policy-mcp/tests/integration`.
"""

import os
import sys

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from credit_core.policy import DEMO_POLICY_V1

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

_HANDSHAKE_TIMEOUT_SECONDS = 30.0


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_stdio_subprocess_serves_the_real_policy_catalog() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "policy_mcp"],
        env={**os.environ, "POLICY_MCP_TRANSPORT": "stdio"},
    )

    async with (
        stdio_client(server_params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        with anyio.fail_after(_HANDSHAKE_TIMEOUT_SECONDS):
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "list_policies",
                "get_policy",
                "list_critical_flags",
            }

            result = await session.call_tool("get_policy", {"version": DEMO_POLICY_V1.version})
            assert result.isError is not True
