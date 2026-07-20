"""Behavior tests for policy_mcp's domain catalog value objects."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from policy_mcp.domain.catalog import (
    ApprovalAuthorityTier,
    CriticalFlagView,
    DecisionThresholds,
    PolicyDetail,
    PolicySummary,
    ScoreBandView,
    ScoreComponentView,
)


def test_score_band_view_is_frozen() -> None:
    band = ScoreBandView(boundary=Decimal("800"), score=Decimal("100"))

    with pytest.raises(FrozenInstanceError):
        band.score = Decimal("0")  # type: ignore[misc]


def test_score_band_view_equality_is_structural() -> None:
    first = ScoreBandView(boundary=Decimal("800"), score=Decimal("100"))
    second = ScoreBandView(boundary=Decimal("800"), score=Decimal("100"))

    assert first == second
    assert first is not second


def test_policy_summary_holds_decision_thresholds() -> None:
    thresholds = DecisionThresholds(
        approval_recommendation_minimum_score=Decimal("80"),
        conditional_approval_minimum_score=Decimal("60"),
        committee_referral_minimum_score=Decimal("40"),
    )
    summary = PolicySummary(
        version="demo-v1",
        score_component_count=4,
        approval_authority_tier_count=4,
        decision_thresholds=thresholds,
    )

    assert summary.decision_thresholds is thresholds
    assert summary.score_component_count == 4


def test_approval_authority_tier_top_tier_has_no_maximum() -> None:
    tier = ApprovalAuthorityTier(
        authority="EXECUTIVE_BOARD",
        minimum_amount=Decimal("1000000"),
        maximum_amount=None,
    )

    assert tier.maximum_amount is None


def test_policy_detail_is_frozen() -> None:
    detail = PolicyDetail(
        version="demo-v1",
        score_components=(
            ScoreComponentView(
                component="BUREAU_SCORE",
                weight=Decimal("0.40"),
                direction="HIGHER_IS_BETTER",
                bands=(ScoreBandView(boundary=Decimal("800"), score=Decimal("100")),),
            ),
        ),
        decision_thresholds=DecisionThresholds(
            approval_recommendation_minimum_score=Decimal("80"),
            conditional_approval_minimum_score=Decimal("60"),
            committee_referral_minimum_score=Decimal("40"),
        ),
        approval_authority_tiers=(
            ApprovalAuthorityTier(
                authority="ANALYST",
                minimum_amount=Decimal("0"),
                maximum_amount=Decimal("50000"),
            ),
        ),
        zero_debt_service_metric_value=Decimal("999"),
    )

    with pytest.raises(FrozenInstanceError):
        detail.version = "other"  # type: ignore[misc]


def test_critical_flag_view_carries_name_and_value() -> None:
    flag = CriticalFlagView(name="FRAUD_ALERT", value="FRAUD_ALERT")

    assert flag.name == "FRAUD_ALERT"
    assert flag.value == "FRAUD_ALERT"
