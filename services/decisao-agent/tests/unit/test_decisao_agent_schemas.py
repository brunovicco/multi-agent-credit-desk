"""Behavior tests for domain-to-wire schema mapping and strict-schema validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from decisao_agent.domain.opinion import ComponentScoreView, CreditOpinion
from decisao_agent.entrypoints import schemas


def test_application_snapshot_input_defaults_critical_flags_to_empty() -> None:
    input_model = schemas.ApplicationSnapshotInput(
        annual_revenue=Decimal("1000000"),
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
    )

    assert input_model.critical_flags == ()


def test_application_snapshot_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        schemas.ApplicationSnapshotInput(
            annual_revenue=Decimal("1000000"),
            total_debt=Decimal("300000"),
            monthly_debt_service=Decimal("10000"),
            monthly_operating_cash_flow=Decimal("25000"),
            bureau_score=Decimal("850"),
            years_in_operation=12,
            requested_amount=Decimal("30000"),
            unexpected_field="not allowed",  # type: ignore[call-arg]
        )


def test_application_snapshot_input_rejects_negative_years_in_operation() -> None:
    with pytest.raises(ValidationError):
        schemas.ApplicationSnapshotInput(
            annual_revenue=Decimal("1000000"),
            total_debt=Decimal("300000"),
            monthly_debt_service=Decimal("10000"),
            monthly_operating_cash_flow=Decimal("25000"),
            bureau_score=Decimal("850"),
            years_in_operation=-1,
            requested_amount=Decimal("30000"),
        )


def test_to_application_snapshot_maps_critical_flags_to_a_frozenset() -> None:
    input_model = schemas.ApplicationSnapshotInput(
        annual_revenue=Decimal("1000000"),
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
        critical_flags=("FRAUD_ALERT", "FRAUD_ALERT"),
    )

    snapshot = schemas.to_application_snapshot(input_model)

    assert snapshot.critical_flags == frozenset({"FRAUD_ALERT"})


def test_to_component_score_maps_every_field() -> None:
    component_score = ComponentScoreView(
        component="BUREAU_SCORE",
        metric_value=Decimal("850"),
        raw_score=Decimal("100"),
        weight=Decimal("0.40"),
        weighted_score=Decimal("40"),
    )

    wire = schemas.to_component_score(component_score)

    assert wire.component == "BUREAU_SCORE"
    assert wire.weighted_score == Decimal("40")


def test_to_credit_opinion_maps_component_scores_in_order() -> None:
    opinion = CreditOpinion(
        policy_version="demo-v1",
        total_score=Decimal("100"),
        component_scores=(
            ComponentScoreView(
                component="BUREAU_SCORE",
                metric_value=Decimal("850"),
                raw_score=Decimal("100"),
                weight=Decimal("0.40"),
                weighted_score=Decimal("40"),
            ),
        ),
        decision="APPROVAL_RECOMMENDED",
        approval_authority="ANALYST",
        reason_codes=("SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD",),
        blocking_reasons=(),
    )

    wire = schemas.to_credit_opinion(opinion)

    assert wire.policy_version == "demo-v1"
    assert len(wire.component_scores) == 1
    assert wire.component_scores[0].component == "BUREAU_SCORE"
    assert wire.decision == "APPROVAL_RECOMMENDED"


def test_credit_opinion_schema_is_frozen_after_construction() -> None:
    wire = schemas.to_credit_opinion(
        CreditOpinion(
            policy_version="demo-v1",
            total_score=Decimal("0"),
            component_scores=(),
            decision="DECLINE",
            approval_authority="NONE",
            reason_codes=(),
            blocking_reasons=(),
        )
    )

    with pytest.raises(ValidationError):
        wire.decision = "BLOCKED"
