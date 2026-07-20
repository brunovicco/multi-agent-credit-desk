"""Behavior tests for bureau_mcp's domain report value objects."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from bureau_mcp.domain.report import BureauReport, NegativeRecord, NegativeRecordKind


def test_negative_record_is_frozen() -> None:
    record = NegativeRecord(
        kind=NegativeRecordKind.PROTEST, amount=Decimal("1000"), registered_days_ago=10
    )

    with pytest.raises(FrozenInstanceError):
        record.amount = Decimal("0")  # type: ignore[misc]


def test_negative_record_equality_is_structural() -> None:
    first = NegativeRecord(
        kind=NegativeRecordKind.LAWSUIT, amount=Decimal("500"), registered_days_ago=5
    )
    second = NegativeRecord(
        kind=NegativeRecordKind.LAWSUIT, amount=Decimal("500"), registered_days_ago=5
    )

    assert first == second
    assert first is not second


def test_bureau_report_is_frozen() -> None:
    report = BureauReport(cnpj="11222333000181", external_score=Decimal("850"), negative_records=())

    with pytest.raises(FrozenInstanceError):
        report.external_score = Decimal("0")  # type: ignore[misc]


def test_bureau_report_holds_negative_records_in_order() -> None:
    protest = NegativeRecord(
        kind=NegativeRecordKind.PROTEST, amount=Decimal("1000"), registered_days_ago=1
    )
    lawsuit = NegativeRecord(
        kind=NegativeRecordKind.LAWSUIT, amount=Decimal("2000"), registered_days_ago=2
    )
    report = BureauReport(
        cnpj="33444555000181",
        external_score=Decimal("180"),
        negative_records=(protest, lawsuit),
    )

    assert report.negative_records == (protest, lawsuit)
