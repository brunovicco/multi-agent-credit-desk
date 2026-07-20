"""Behavior tests for domain-to-wire schema mapping and strict-schema validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from bureau_mcp.domain.report import BureauReport, NegativeRecord, NegativeRecordKind
from bureau_mcp.entrypoints import schemas


def test_to_negative_record_maps_every_field() -> None:
    record = NegativeRecord(
        kind=NegativeRecordKind.PROTEST, amount=Decimal("1000"), registered_days_ago=10
    )

    wire = schemas.to_negative_record(record)

    assert wire.kind == "PROTEST"
    assert wire.amount == Decimal("1000")
    assert wire.registered_days_ago == 10


def test_to_bureau_report_maps_negative_records_in_order() -> None:
    report = BureauReport(
        cnpj="33444555000181",
        external_score=Decimal("180"),
        negative_records=(
            NegativeRecord(
                kind=NegativeRecordKind.PROTEST, amount=Decimal("1000"), registered_days_ago=1
            ),
            NegativeRecord(
                kind=NegativeRecordKind.LAWSUIT, amount=Decimal("2000"), registered_days_ago=2
            ),
        ),
    )

    wire = schemas.to_bureau_report(report)

    assert wire.cnpj == "33444555000181"
    assert wire.external_score == Decimal("180")
    assert [record.kind for record in wire.negative_records] == ["PROTEST", "LAWSUIT"]


def test_to_bureau_report_maps_a_clean_record_to_an_empty_tuple() -> None:
    report = BureauReport(cnpj="11222333000181", external_score=Decimal("850"), negative_records=())

    wire = schemas.to_bureau_report(report)

    assert wire.negative_records == ()


def test_bureau_report_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        schemas.BureauReport(
            cnpj="11222333000181",
            external_score=Decimal("850"),
            negative_records=(),
            unexpected_field="not allowed",  # type: ignore[call-arg]
        )


def test_bureau_report_schema_is_frozen_after_construction() -> None:
    wire = schemas.to_bureau_report(
        BureauReport(cnpj="11222333000181", external_score=Decimal("850"), negative_records=())
    )

    with pytest.raises(ValidationError):
        wire.cnpj = "other"
