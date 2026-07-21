"""Behavior tests for cadastral-agent's wire schemas and domain-to-wire mappings."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadastral_agent.domain.assessment import KycAssessment, KycDecision
from cadastral_agent.entrypoints.schemas import CnpjInput, to_kyc_assessment_output


def test_cnpj_input_accepts_a_punctuated_cnpj() -> None:
    input_model = CnpjInput.model_validate_json('{"cnpj": "11.222.333/0001-81"}')

    assert input_model.cnpj == "11.222.333/0001-81"


def test_cnpj_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CnpjInput.model_validate_json('{"cnpj": "11222333000181", "extra": "field"}')


def test_to_kyc_assessment_output_maps_every_field() -> None:
    assessment = KycAssessment(
        cnpj="11222333000181",
        external_score=Decimal("850"),
        decision=KycDecision.APPROVED,
        reason_codes=(),
    )

    output = to_kyc_assessment_output(assessment)

    assert output.cnpj == "11222333000181"
    assert output.external_score == Decimal("850")
    assert output.decision == "APPROVED"
    assert output.reason_codes == ()


def test_to_kyc_assessment_output_preserves_decimal_precision() -> None:
    assessment = KycAssessment(
        cnpj="11222333000181",
        external_score=Decimal("180.5"),
        decision=KycDecision.BLOCKED,
        reason_codes=("LAWSUIT_ON_FILE",),
    )

    output = to_kyc_assessment_output(assessment)

    assert output.model_dump_json().count("180.5") == 1


def test_output_schema_is_immutable() -> None:
    assessment = KycAssessment(
        cnpj="11222333000181",
        external_score=Decimal("850"),
        decision=KycDecision.APPROVED,
        reason_codes=(),
    )
    output = to_kyc_assessment_output(assessment)

    with pytest.raises(ValidationError):
        output.cnpj = "99999999000199"
