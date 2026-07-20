"""Behavior tests for BureauReportQueries against a fake port, isolated from the real dataset.

Per .claude/rules/testing.md, unit tests isolate external dependencies: this suite never
imports SyntheticBureauSource, only a hand-written fake that implements BureauLookupPort
structurally.
"""

from decimal import Decimal

import pytest

from bureau_mcp.application.queries import BureauReportQueries
from bureau_mcp.domain.errors import CnpjNotFoundError, InvalidCnpjError
from bureau_mcp.domain.report import BureauReport, NegativeRecord, NegativeRecordKind

_FAKE_REPORT = BureauReport(
    cnpj="11222333000181",
    external_score=Decimal("850"),
    negative_records=(
        NegativeRecord(
            kind=NegativeRecordKind.BOUNCED_CHECK, amount=Decimal("100"), registered_days_ago=3
        ),
    ),
)


class _FakeBureauLookupPort:
    """A hand-written test double implementing BureauLookupPort structurally."""

    def __init__(self, report: BureauReport = _FAKE_REPORT) -> None:
        self._report = report

    def get_report(self, cnpj: str) -> BureauReport:
        if cnpj != self._report.cnpj:
            raise CnpjNotFoundError(cnpj)
        return self._report


def test_get_report_normalizes_a_punctuated_cnpj_before_delegating_to_the_port() -> None:
    queries = BureauReportQueries(_FakeBureauLookupPort())

    report = queries.get_report("11.222.333/0001-81")

    assert report is _FAKE_REPORT


def test_get_report_raises_invalid_cnpj_error_before_calling_the_port() -> None:
    queries = BureauReportQueries(_FakeBureauLookupPort())

    with pytest.raises(InvalidCnpjError):
        queries.get_report("not-a-cnpj")


def test_get_report_propagates_cnpj_not_found_from_the_port() -> None:
    queries = BureauReportQueries(_FakeBureauLookupPort())

    with pytest.raises(CnpjNotFoundError) as exc_info:
        queries.get_report("22333444000181")

    assert exc_info.value.cnpj == "22333444000181"
