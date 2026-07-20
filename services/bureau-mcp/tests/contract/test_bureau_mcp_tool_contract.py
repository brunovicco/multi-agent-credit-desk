"""Contract tests: exercise the get_bureau_report tool through the real MCP SDK session machinery.

Uses ``mcp.shared.memory.create_connected_server_and_client_session``, the SDK's own in-process
client/server testing utility - no subprocess, no network. Asserts realistic JSON tool-result
shapes and that both the ``InvalidCnpjError`` and ``CnpjNotFoundError`` paths produce
``isError=True`` with no leaked exception message, stack trace, or raw input, per
``.claude/rules/api-boundaries.md``.
"""

import json
from collections.abc import AsyncIterator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from bureau_mcp.entrypoints.server import build_server

pytestmark = [pytest.mark.contract, pytest.mark.anyio]

_HEALTHY_CNPJ = "11.222.333/0001-81"


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


@pytest.fixture
async def client_session() -> AsyncIterator[ClientSession]:
    server = build_server()
    async with create_connected_server_and_client_session(server) as session:
        yield session


def _text_content(result: object) -> str:
    content = result.content  # type: ignore[attr-defined]
    assert len(content) == 1
    block = content[0]
    assert isinstance(block, TextContent)
    return block.text


async def test_list_tools_exposes_exactly_the_one_bureau_tool(
    client_session: ClientSession,
) -> None:
    tools = await client_session.list_tools()

    tool_names = {tool.name for tool in tools.tools}
    assert tool_names == {"get_bureau_report"}


async def test_get_bureau_report_accepts_a_punctuated_cnpj_and_returns_a_realistic_json_result(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_bureau_report", {"cnpj": _HEALTHY_CNPJ})

    assert result.isError is not True
    body = json.loads(_text_content(result))
    assert body["cnpj"] == "11222333000181"
    assert body["negative_records"] == []


async def test_get_bureau_report_with_malformed_cnpj_returns_stable_error_without_echoing_input(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_bureau_report", {"cnpj": "not-a-cnpj"})

    assert result.isError is True
    body = json.loads(_text_content(result))
    assert body["code"] == "INVALID_CNPJ"
    assert "not-a-cnpj" not in body["message"]
    assert "Traceback" not in body["message"]


async def test_get_bureau_report_with_unknown_cnpj_returns_stable_error_without_stack_trace(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_bureau_report", {"cnpj": "44555666000181"})

    assert result.isError is True
    body = json.loads(_text_content(result))
    assert body["code"] == "CNPJ_NOT_FOUND"
    assert "44555666000181" not in body["message"]
    assert "Traceback" not in body["message"]
