"""Behavior tests for PolicyMcpClient's tool-result parsing, isolated from any real subprocess.

Per .claude/rules/testing.md, unit tests isolate external processes: this suite never spawns
policy-mcp, only constructs ``CallToolResult`` objects directly, the same shape the real MCP SDK
client would hand back. The real subprocess roundtrip is covered by
``tests/integration/test_decisao_agent_cli_stdio_roundtrip.py``.
"""

import json

import pytest
from mcp.types import CallToolResult, TextContent

from decisao_agent.adapters.policy_mcp_client import _extract_string_field
from decisao_agent.domain.errors import PolicyCatalogUnavailableError


def _ok_result(body: object) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(body))], isError=False)


def test_extract_string_field_returns_every_value() -> None:
    result = _ok_result({"critical_flags": [{"name": "FRAUD_ALERT"}, {"name": "BANKRUPTCY"}]})

    names = _extract_string_field(result, "list_critical_flags", "critical_flags", "name")

    assert names == frozenset({"FRAUD_ALERT", "BANKRUPTCY"})


def test_extract_string_field_deduplicates_values() -> None:
    result = _ok_result({"policies": [{"version": "v1"}, {"version": "v1"}]})

    versions = _extract_string_field(result, "list_policies", "policies", "version")

    assert versions == frozenset({"v1"})


def test_extract_string_field_returns_empty_set_for_an_empty_list() -> None:
    result = _ok_result({"critical_flags": []})

    assert _extract_string_field(result, "list_critical_flags", "critical_flags", "name") == (
        frozenset()
    )


def test_extract_string_field_raises_when_result_is_error() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text=json.dumps({"code": "SOMETHING"}))],
        isError=True,
    )

    with pytest.raises(PolicyCatalogUnavailableError):
        _extract_string_field(result, "list_critical_flags", "critical_flags", "name")


def test_extract_string_field_raises_when_content_is_not_a_single_text_block() -> None:
    result = CallToolResult(content=[], isError=False)

    with pytest.raises(PolicyCatalogUnavailableError):
        _extract_string_field(result, "list_critical_flags", "critical_flags", "name")


def test_extract_string_field_raises_when_body_is_not_an_object() -> None:
    result = _ok_result(["not", "an", "object"])

    with pytest.raises(PolicyCatalogUnavailableError):
        _extract_string_field(result, "list_critical_flags", "critical_flags", "name")


def test_extract_string_field_raises_when_list_field_is_missing() -> None:
    result = _ok_result({"unexpected": []})

    with pytest.raises(PolicyCatalogUnavailableError):
        _extract_string_field(result, "list_critical_flags", "critical_flags", "name")


def test_extract_string_field_raises_when_an_item_field_has_the_wrong_type() -> None:
    result = _ok_result({"critical_flags": [{"name": 123}]})

    with pytest.raises(PolicyCatalogUnavailableError):
        _extract_string_field(result, "list_critical_flags", "critical_flags", "name")
