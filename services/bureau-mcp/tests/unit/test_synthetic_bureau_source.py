"""Behavior tests for SyntheticBureauSource's fixed dataset of the three demo personas."""

from decimal import Decimal

import pytest

from bureau_mcp.adapters.synthetic_bureau_source import SyntheticBureauSource
from bureau_mcp.domain.cnpj import validate_cnpj
from bureau_mcp.domain.errors import CnpjNotFoundError
from bureau_mcp.domain.report import NegativeRecordKind


@pytest.fixture
def source() -> SyntheticBureauSource:
    return SyntheticBureauSource()


def test_every_dataset_cnpj_is_itself_a_valid_cnpj(source: SyntheticBureauSource) -> None:
    """Guard against a hardcoded CNPJ silently becoming invalid if the algorithm ever changes."""
    for cnpj in ("11222333000181", "22333444000181", "33444555000181"):
        assert validate_cnpj(cnpj) == cnpj
        assert source.get_report(cnpj).cnpj == cnpj


def test_healthy_persona_has_a_high_score_and_no_negative_records(
    source: SyntheticBureauSource,
) -> None:
    report = source.get_report("11222333000181")

    assert report.external_score == Decimal("850")
    assert report.negative_records == ()


def test_leveraged_persona_has_a_moderate_score_and_one_overdue_debt(
    source: SyntheticBureauSource,
) -> None:
    report = source.get_report("22333444000181")

    assert report.external_score == Decimal("520")
    assert len(report.negative_records) == 1
    assert report.negative_records[0].kind == NegativeRecordKind.OVERDUE_DEBT


def test_negative_history_persona_has_a_low_score_and_two_records(
    source: SyntheticBureauSource,
) -> None:
    report = source.get_report("33444555000181")

    assert report.external_score == Decimal("180")
    assert {record.kind for record in report.negative_records} == {
        NegativeRecordKind.PROTEST,
        NegativeRecordKind.LAWSUIT,
    }


def test_get_report_raises_cnpj_not_found_for_an_unknown_cnpj(
    source: SyntheticBureauSource,
) -> None:
    unknown_cnpj = "44555666000181"

    with pytest.raises(CnpjNotFoundError) as exc_info:
        source.get_report(unknown_cnpj)

    assert exc_info.value.cnpj == unknown_cnpj
