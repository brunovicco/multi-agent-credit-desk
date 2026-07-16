"""Invariant tests for CreditPolicy validation."""

import dataclasses
from decimal import Decimal
from typing import cast

import pytest

from credit_core import (
    DEMO_POLICY_V1,
    CreditApplicationSnapshot,
    InvalidCreditPolicyError,
    evaluate_credit_application,
)
from credit_core.domain import ScoreComponent
from credit_core.policy import CreditPolicy, ScoreBand, ScoreComponentPolicy, validate_policy


def _replace_component(
    policy: CreditPolicy,
    component: ScoreComponent,
    *,
    weight: Decimal | None = None,
    bands: tuple[ScoreBand, ...] | None = None,
) -> CreditPolicy:
    def _apply(component_policy: ScoreComponentPolicy) -> ScoreComponentPolicy:
        if component_policy.component is not component:
            return component_policy
        return dataclasses.replace(
            component_policy,
            weight=component_policy.weight if weight is None else weight,
            bands=component_policy.bands if bands is None else bands,
        )

    components = tuple(_apply(component_policy) for component_policy in policy.score_components)
    return dataclasses.replace(policy, score_components=components)


def test_demo_policy_is_valid() -> None:
    validate_policy(DEMO_POLICY_V1)


def test_weights_not_summing_to_one_are_rejected() -> None:
    broken = _replace_component(DEMO_POLICY_V1, ScoreComponent.BUREAU_SCORE, weight=Decimal("0.50"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_missing_component_is_rejected() -> None:
    broken = dataclasses.replace(
        DEMO_POLICY_V1,
        score_components=tuple(
            component_policy
            for component_policy in DEMO_POLICY_V1.score_components
            if component_policy.component is not ScoreComponent.OPERATING_HISTORY
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_duplicate_component_is_rejected() -> None:
    broken = dataclasses.replace(
        DEMO_POLICY_V1,
        score_components=(*DEMO_POLICY_V1.score_components, DEMO_POLICY_V1.score_components[0]),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_unsorted_bands_are_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.BUREAU_SCORE,
        bands=(
            ScoreBand(Decimal("400"), Decimal("20")),
            ScoreBand(Decimal("800"), Decimal("100")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_bands_not_covering_zero_boundary_are_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.BUREAU_SCORE,
        bands=(
            ScoreBand(Decimal("800"), Decimal("100")),
            ScoreBand(Decimal("400"), Decimal("20")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_band_score_out_of_range_is_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.BUREAU_SCORE,
        bands=(
            ScoreBand(Decimal("800"), Decimal("120")),
            ScoreBand(Decimal("0"), Decimal("0")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_decision_thresholds_not_strictly_decreasing_are_rejected() -> None:
    broken = dataclasses.replace(DEMO_POLICY_V1, conditional_approval_minimum_score=Decimal("90"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_authority_thresholds_not_strictly_increasing_are_rejected() -> None:
    broken = dataclasses.replace(DEMO_POLICY_V1, senior_analyst_maximum_amount=Decimal("10"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_non_positive_zero_debt_service_metric_value_is_rejected() -> None:
    broken = dataclasses.replace(DEMO_POLICY_V1, zero_debt_service_metric_value=Decimal("0"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_zero_debt_service_metric_below_top_coverage_band_is_rejected() -> None:
    broken = dataclasses.replace(
        DEMO_POLICY_V1,
        zero_debt_service_metric_value=Decimal("1.99"),
    )

    with pytest.raises(
        InvalidCreditPolicyError,
        match="zero_debt_service_metric_value must reach the top",
    ):
        validate_policy(broken)


def test_zero_debt_service_metric_at_top_coverage_boundary_is_valid() -> None:
    policy = dataclasses.replace(
        DEMO_POLICY_V1,
        zero_debt_service_metric_value=Decimal("2.00"),
    )

    validate_policy(policy)


def test_non_positive_component_weight_is_rejected() -> None:
    broken = _replace_component(DEMO_POLICY_V1, ScoreComponent.LEVERAGE_RATIO, weight=Decimal("0"))
    # Compensate elsewhere so the total still sums to 1.00 and only the zero weight is exercised.
    broken = _replace_component(broken, ScoreComponent.BUREAU_SCORE, weight=Decimal("0.65"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_float_component_weight_is_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.BUREAU_SCORE,
        weight=cast(Decimal, 0.40),
    )

    with pytest.raises(InvalidCreditPolicyError, match="weight must be a Decimal"):
        validate_policy(broken)


def test_empty_bands_are_rejected() -> None:
    broken = _replace_component(DEMO_POLICY_V1, ScoreComponent.BUREAU_SCORE, bands=())
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_negative_ascending_boundary_is_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.LEVERAGE_RATIO,
        bands=(
            ScoreBand(Decimal("-1"), Decimal("100")),
            ScoreBand(Decimal("Infinity"), Decimal("0")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_unsorted_ascending_bands_are_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.LEVERAGE_RATIO,
        bands=(
            ScoreBand(Decimal("2.00"), Decimal("60")),
            ScoreBand(Decimal("1.00"), Decimal("80")),
            ScoreBand(Decimal("Infinity"), Decimal("0")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_ascending_bands_not_covering_infinity_are_rejected() -> None:
    broken = _replace_component(
        DEMO_POLICY_V1,
        ScoreComponent.LEVERAGE_RATIO,
        bands=(
            ScoreBand(Decimal("0.50"), Decimal("100")),
            ScoreBand(Decimal("5.00"), Decimal("20")),
        ),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_decision_threshold_out_of_range_is_rejected() -> None:
    broken = dataclasses.replace(
        DEMO_POLICY_V1,
        approval_recommendation_minimum_score=Decimal("120"),
    )
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


@pytest.mark.parametrize(
    "non_finite_value",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
)
def test_non_finite_decision_threshold_is_rejected(non_finite_value: Decimal) -> None:
    broken = dataclasses.replace(
        DEMO_POLICY_V1,
        approval_recommendation_minimum_score=non_finite_value,
    )

    with pytest.raises(InvalidCreditPolicyError, match="must be finite"):
        validate_policy(broken)


def test_non_positive_authority_threshold_is_rejected() -> None:
    broken = dataclasses.replace(DEMO_POLICY_V1, analyst_maximum_amount=Decimal("0"))
    with pytest.raises(InvalidCreditPolicyError):
        validate_policy(broken)


def test_evaluate_rejects_an_invalid_policy(
    healthy_snapshot: CreditApplicationSnapshot,
) -> None:
    broken = dataclasses.replace(DEMO_POLICY_V1, conditional_approval_minimum_score=Decimal("90"))
    with pytest.raises(InvalidCreditPolicyError):
        evaluate_credit_application(healthy_snapshot, policy=broken)
