"""Proves `python -m bureau_mcp` works end to end as a real subprocess over stdio.

Spawns the packaged CLI entrypoint (not an in-process fake), performs one real MCP initialize
handshake, and calls the tool once - proving the console entrypoint, transport selection, and
the full server wiring work together, not just the composition root in isolation. Matches the
existing pattern in `services/policy-mcp/tests/integration/test_server_stdio_roundtrip.py`.
"""

import os
import sys

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

_HANDSHAKE_TIMEOUT_SECONDS = 30.0
_HEALTHY_CNPJ = "11222333000181"


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_stdio_subprocess_serves_the_real_bureau_catalog() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "bureau_mcp"],
        env={**os.environ, "BUREAU_MCP_TRANSPORT": "stdio"},
    )

    async with (
        stdio_client(server_params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        with anyio.fail_after(_HANDSHAKE_TIMEOUT_SECONDS):
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {"get_bureau_report"}

            result = await session.call_tool("get_bureau_report", {"cnpj": _HEALTHY_CNPJ})
            assert result.isError is not True
