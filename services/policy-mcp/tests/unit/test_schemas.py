"""Behavior tests for domain-to-wire schema mapping and strict-schema validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from policy_mcp.domain.catalog import (
    ApprovalAuthorityTier,
    CriticalFlagView,
    DecisionThresholds,
    PolicyDetail,
    PolicySummary,
    ScoreBandView,
    ScoreComponentView,
)
from policy_mcp.entrypoints import schemas

_THRESHOLDS = DecisionThresholds(
    approval_recommendation_minimum_score=Decimal("80"),
    conditional_approval_minimum_score=Decimal("60"),
    committee_referral_minimum_score=Decimal("40"),
)


def test_to_score_band_maps_boundary_and_score() -> None:
    band = ScoreBandView(boundary=Decimal("800"), score=Decimal("100"))

    wire = schemas.to_score_band(band)

    assert wire.boundary == Decimal("800")
    assert wire.score == Decimal("100")


def test_to_score_band_accepts_an_infinite_boundary() -> None:
    """credit_core's own last LOWER_IS_BETTER band always has an infinite boundary."""
    band = ScoreBandView(boundary=Decimal("Infinity"), score=Decimal("0"))

    wire = schemas.to_score_band(band)

    assert wire.boundary == Decimal("Infinity")


def test_to_score_component_maps_bands_in_order() -> None:
    component = ScoreComponentView(
        component="BUREAU_SCORE",
        weight=Decimal("0.40"),
        direction="HIGHER_IS_BETTER",
        bands=(
            ScoreBandView(boundary=Decimal("800"), score=Decimal("100")),
            ScoreBandView(boundary=Decimal("0"), score=Decimal("0")),
        ),
    )

    wire = schemas.to_score_component(component)

    assert wire.component == "BUREAU_SCORE"
    assert wire.weight == Decimal("0.40")
    assert wire.direction == "HIGHER_IS_BETTER"
    assert [band.boundary for band in wire.bands] == [Decimal("800"), Decimal("0")]


def test_to_decision_thresholds_maps_every_field() -> None:
    wire = schemas.to_decision_thresholds(_THRESHOLDS)

    assert wire.approval_recommendation_minimum_score == Decimal("80")
    assert wire.conditional_approval_minimum_score == Decimal("60")
    assert wire.committee_referral_minimum_score == Decimal("40")


def test_to_approval_authority_tier_maps_none_maximum() -> None:
    tier = ApprovalAuthorityTier(
        authority="EXECUTIVE_BOARD", minimum_amount=Decimal("1000000"), maximum_amount=None
    )

    wire = schemas.to_approval_authority_tier(tier)

    assert wire.authority == "EXECUTIVE_BOARD"
    assert wire.maximum_amount is None


def test_to_policy_summary_maps_counts_and_thresholds() -> None:
    summary = PolicySummary(
        version="demo-v1",
        score_component_count=4,
        approval_authority_tier_count=4,
        decision_thresholds=_THRESHOLDS,
    )

    wire = schemas.to_policy_summary(summary)

    assert wire.version == "demo-v1"
    assert wire.score_component_count == 4
    assert wire.approval_authority_tier_count == 4
    assert wire.decision_thresholds.approval_recommendation_minimum_score == Decimal("80")


def test_to_policy_list_result_wraps_every_summary() -> None:
    summary = PolicySummary(
        version="demo-v1",
        score_component_count=4,
        approval_authority_tier_count=4,
        decision_thresholds=_THRESHOLDS,
    )

    wire = schemas.to_policy_list_result((summary, summary))

    assert len(wire.policies) == 2


def test_to_policy_detail_maps_every_field() -> None:
    detail = PolicyDetail(
        version="demo-v1",
        score_components=(
            ScoreComponentView(
                component="BUREAU_SCORE",
                weight=Decimal("1.00"),
                direction="HIGHER_IS_BETTER",
                bands=(ScoreBandView(boundary=Decimal("0"), score=Decimal("0")),),
            ),
        ),
        decision_thresholds=_THRESHOLDS,
        approval_authority_tiers=(
            ApprovalAuthorityTier(
                authority="ANALYST", minimum_amount=Decimal("0"), maximum_amount=Decimal("1000")
            ),
        ),
        zero_debt_service_metric_value=Decimal("999"),
    )

    wire = schemas.to_policy_detail(detail)

    assert wire.version == "demo-v1"
    assert len(wire.score_components) == 1
    assert wire.zero_debt_service_metric_value == Decimal("999")
    assert wire.approval_authority_tiers[0].authority == "ANALYST"


def test_to_critical_flag_catalog_wraps_every_flag() -> None:
    flags = (
        CriticalFlagView(name="FRAUD_ALERT", value="FRAUD_ALERT"),
        CriticalFlagView(name="BANKRUPTCY_FILING", value="BANKRUPTCY_FILING"),
    )

    wire = schemas.to_critical_flag_catalog(flags)

    assert [flag.name for flag in wire.critical_flags] == ["FRAUD_ALERT", "BANKRUPTCY_FILING"]


def test_policy_summary_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        schemas.PolicySummary(
            version="demo-v1",
            score_component_count=4,
            approval_authority_tier_count=4,
            decision_thresholds=schemas.to_decision_thresholds(_THRESHOLDS),
            unexpected_field="not allowed",  # type: ignore[call-arg]
        )


def test_policy_detail_schema_is_frozen_after_construction() -> None:
    wire = schemas.to_policy_detail(
        PolicyDetail(
            version="demo-v1",
            score_components=(),
            decision_thresholds=_THRESHOLDS,
            approval_authority_tiers=(),
            zero_debt_service_metric_value=Decimal("999"),
        )
    )

    with pytest.raises(ValidationError):
        wire.version = "other"
