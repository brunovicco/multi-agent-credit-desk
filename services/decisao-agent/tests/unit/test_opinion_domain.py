"""Behavior tests for decisao_agent's CreditOpinion value object."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from decisao_agent.domain.opinion import ComponentScoreView, CreditOpinion


def test_component_score_view_is_frozen() -> None:
    component_score = ComponentScoreView(
        component="BUREAU_SCORE",
        metric_value=Decimal("780"),
        raw_score=Decimal("100"),
        weight=Decimal("0.40"),
        weighted_score=Decimal("40"),
    )

    with pytest.raises(FrozenInstanceError):
        component_score.raw_score = Decimal("0")  # type: ignore[misc]


def test_credit_opinion_is_frozen() -> None:
    opinion = CreditOpinion(
        policy_version="demo-v1",
        total_score=Decimal("80"),
        component_scores=(),
        decision="APPROVAL_RECOMMENDED",
        approval_authority="ANALYST",
        reason_codes=(),
        blocking_reasons=(),
    )

    with pytest.raises(FrozenInstanceError):
        opinion.decision = "BLOCKED"  # type: ignore[misc]


def test_credit_opinion_holds_component_scores_in_order() -> None:
    bureau_score = ComponentScoreView(
        component="BUREAU_SCORE",
        metric_value=Decimal("780"),
        raw_score=Decimal("100"),
        weight=Decimal("0.40"),
        weighted_score=Decimal("40"),
    )
    leverage_ratio = ComponentScoreView(
        component="LEVERAGE_RATIO",
        metric_value=Decimal("0.24"),
        raw_score=Decimal("80"),
        weight=Decimal("0.30"),
        weighted_score=Decimal("24"),
    )
    opinion = CreditOpinion(
        policy_version="demo-v1",
        total_score=Decimal("64"),
        component_scores=(bureau_score, leverage_ratio),
        decision="APPROVAL_RECOMMENDED",
        approval_authority="ANALYST",
        reason_codes=("SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD",),
        blocking_reasons=(),
    )

    assert opinion.component_scores == (bureau_score, leverage_ratio)
