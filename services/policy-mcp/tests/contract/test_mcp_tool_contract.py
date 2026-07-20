"""Contract tests: exercise all three policy-mcp tools through the real MCP SDK session machinery.

Uses ``mcp.shared.memory.create_connected_server_and_client_session``, the SDK's own in-process
client/server testing utility - no subprocess, no network. Asserts realistic JSON tool-result
shapes and that the ``PolicyNotFoundError`` path produces ``isError=True`` with no leaked
exception message or stack trace, per ``.claude/rules/api-boundaries.md``.
"""

import json
from collections.abc import AsyncIterator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from credit_core.policy import DEMO_POLICY_V1
from policy_mcp.entrypoints.server import build_server

pytestmark = [pytest.mark.contract, pytest.mark.anyio]


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


async def test_list_tools_exposes_exactly_the_three_catalog_tools(
    client_session: ClientSession,
) -> None:
    tools = await client_session.list_tools()

    tool_names = {tool.name for tool in tools.tools}
    assert tool_names == {"list_policies", "get_policy", "list_critical_flags"}


async def test_list_policies_returns_a_realistic_json_result(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("list_policies", {})

    assert result.isError is not True
    body = json.loads(_text_content(result))
    assert body["policies"][0]["version"] == DEMO_POLICY_V1.version


async def test_get_policy_returns_full_detail_for_the_demo_policy_version(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_policy", {"version": DEMO_POLICY_V1.version})

    assert result.isError is not True
    body = json.loads(_text_content(result))
    assert body["version"] == DEMO_POLICY_V1.version
    assert len(body["score_components"]) == len(DEMO_POLICY_V1.score_components)
    assert len(body["approval_authority_tiers"]) == 4
    assert body["approval_authority_tiers"][-1]["maximum_amount"] is None


async def test_get_policy_with_unknown_version_returns_stable_error_without_stack_trace(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_policy", {"version": "does-not-exist"})

    assert result.isError is True
    body = json.loads(_text_content(result))
    assert body["code"] == "POLICY_NOT_FOUND"
    assert "does-not-exist" in body["message"]
    assert "Traceback" not in body["message"]
    assert "credit_core" not in body["message"]


async def test_list_critical_flags_returns_every_synthetic_flag(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("list_critical_flags", {})

    assert result.isError is not True
    body = json.loads(_text_content(result))
    names = {flag["name"] for flag in body["critical_flags"]}
    assert names == {"BANKRUPTCY_FILING", "SEVERE_PAYMENT_DEFAULT", "FRAUD_ALERT"}
