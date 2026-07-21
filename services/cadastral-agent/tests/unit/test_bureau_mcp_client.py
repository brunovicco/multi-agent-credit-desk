"""Behavior tests for BureauMcpClient's tool-result parsing, isolated from any real subprocess.

Per .claude/rules/testing.md, unit tests isolate external processes: this suite never spawns
bureau-mcp, only constructs ``CallToolResult`` objects directly, the same shape the real MCP SDK
client would hand back. The real subprocess roundtrip is covered by
``tests/integration/test_bureau_mcp_client_failure_modes.py``.
"""

import json
from decimal import Decimal

import pytest
from mcp.types import CallToolResult, TextContent

from cadastral_agent.adapters.bureau_mcp_client import _parse_bureau_report_result
from cadastral_agent.domain.bureau_finding import NegativeRecordKind
from cadastral_agent.domain.errors import (
    BureauReportUnavailableError,
    CnpjNotFoundError,
    InvalidCnpjError,
)


def _ok_result(body: object) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(body))], isError=False)


def _error_result(code: str) -> CallToolResult:
    body = {"code": code, "message": "irrelevant"}
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(body))], isError=True)


def test_parses_a_clean_report() -> None:
    result = _ok_result({"cnpj": "11222333000181", "external_score": "850", "negative_records": []})

    finding = _parse_bureau_report_result(result)

    assert finding.cnpj == "11222333000181"
    assert finding.external_score == Decimal("850")
    assert finding.negative_records == ()


def test_parses_a_report_with_negative_records() -> None:
    result = _ok_result(
        {
            "cnpj": "22333444000181",
            "external_score": "520",
            "negative_records": [
                {"kind": "OVERDUE_DEBT", "amount": "15000.00", "registered_days_ago": 120}
            ],
        }
    )

    finding = _parse_bureau_report_result(result)

    assert len(finding.negative_records) == 1
    record = finding.negative_records[0]
    assert record.kind == NegativeRecordKind.OVERDUE_DEBT
    assert record.amount == Decimal("15000.00")
    assert record.registered_days_ago == 120


def test_raises_invalid_cnpj_for_the_invalid_cnpj_code() -> None:
    with pytest.raises(InvalidCnpjError):
        _parse_bureau_report_result(_error_result("INVALID_CNPJ"))


def test_raises_cnpj_not_found_for_the_cnpj_not_found_code() -> None:
    with pytest.raises(CnpjNotFoundError):
        _parse_bureau_report_result(_error_result("CNPJ_NOT_FOUND"))


def test_raises_bureau_report_unavailable_for_an_unrecognized_error_code() -> None:
    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(_error_result("SOMETHING_ELSE"))


def test_raises_bureau_report_unavailable_when_content_is_not_a_single_text_block() -> None:
    result = CallToolResult(content=[], isError=False)

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_when_body_is_not_an_object() -> None:
    result = _ok_result(["not", "an", "object"])

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_when_cnpj_field_is_missing() -> None:
    result = _ok_result({"external_score": "850", "negative_records": []})

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_when_external_score_is_malformed() -> None:
    result = _ok_result(
        {"cnpj": "11222333000181", "external_score": "not-a-number", "negative_records": []}
    )

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_for_an_unknown_record_kind() -> None:
    result = _ok_result(
        {
            "cnpj": "11222333000181",
            "external_score": "850",
            "negative_records": [
                {"kind": "NOT_A_REAL_KIND", "amount": "100", "registered_days_ago": 1}
            ],
        }
    )

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_when_registered_days_ago_is_malformed() -> None:
    result = _ok_result(
        {
            "cnpj": "11222333000181",
            "external_score": "850",
            "negative_records": [
                {"kind": "OVERDUE_DEBT", "amount": "100", "registered_days_ago": "soon"}
            ],
        }
    )

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)


def test_raises_bureau_report_unavailable_when_json_is_invalid() -> None:
    result = CallToolResult(content=[TextContent(type="text", text="not json")], isError=False)

    with pytest.raises(BureauReportUnavailableError):
        _parse_bureau_report_result(result)
