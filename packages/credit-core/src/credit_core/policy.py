"""Policy configuration for the deterministic credit evaluation core.

This module holds configuration only: weights, score bands, decision thresholds, and
approval-authority thresholds. It contains no evaluation logic - see
``credit_core.evaluation`` for the pure evaluator that applies a ``CreditPolicy``.

``DEMO_POLICY_V1`` is a synthetic demonstration policy. Every threshold, weight, and authority
boundary in it is invented for this project's test and demonstration purposes only, and none of
it is derived from a production credit policy. See ``packages/credit-core/README.md`` for the
full rationale before using it, or any policy shaped like it, outside a demo or test context.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from itertools import pairwise

from credit_core.domain import ScoreComponent
from credit_core.errors import InvalidCreditPolicyError

SCORE_QUANTUM = Decimal("0.01")
"""Quantization unit applied to every weighted component score and the total score.

Rounding uses ``ROUND_HALF_EVEN`` (banker's rounding), applied once per weighted component
score. The total score is the exact sum of the already-quantized weighted component scores, and
is itself re-quantized defensively with the same unit and rounding mode. No other rounding step
exists anywhere in the evaluation path.
"""

_MIN_RAW_SCORE = Decimal("0")
_MAX_RAW_SCORE = Decimal("100")
_TOTAL_WEIGHT = Decimal("1.00")


class ScoreDirection(Enum):
    """Direction in which a higher metric value is favorable for a scored component."""

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True, slots=True)
class ScoreBand:
    """One boundary/score pair used to map a metric value to a raw component score.

    For ``ScoreDirection.HIGHER_IS_BETTER``, ``boundary`` is a minimum-inclusive threshold: a
    component's bands must be sorted by strictly descending ``boundary``, with the last band's
    boundary equal to zero. For ``ScoreDirection.LOWER_IS_BETTER``, ``boundary`` is a
    maximum-inclusive threshold: bands must be sorted by strictly ascending ``boundary``, with
    the last band's boundary equal to ``Decimal("Infinity")``. In both directions, ``score``
    must be strictly monotonic across the sorted bands so every band is meaningful.
    """

    boundary: Decimal
    score: Decimal


@dataclass(frozen=True, slots=True)
class ScoreComponentPolicy:
    """Policy configuration for one scored component: its weight, direction, and bands."""

    component: ScoreComponent
    weight: Decimal
    direction: ScoreDirection
    bands: tuple[ScoreBand, ...]


@dataclass(frozen=True, slots=True)
class CreditPolicy:
    """A complete, versioned, immutable credit evaluation policy configuration.

    Instances hold only numeric thresholds, weights, and bands; ``credit_core.evaluation``
    applies them. See ``DEMO_POLICY_V1`` for the synthetic policy shipped with this package.

    Attributes:
        version: A version identifier included in every ``CreditEvaluationResult``.
        score_components: Exactly one ``ScoreComponentPolicy`` per ``ScoreComponent`` member,
            with weights summing to exactly ``1.00``.
        automatic_approval_minimum_score: Minimum total score, inclusive, for automatic
            approval.
        conditional_approval_minimum_score: Minimum total score, inclusive, for conditional
            approval. Must be strictly less than ``automatic_approval_minimum_score``.
        committee_referral_minimum_score: Minimum total score, inclusive, for committee
            referral. Must be strictly less than ``conditional_approval_minimum_score``. Any
            score below this threshold is declined.
        analyst_maximum_amount: Maximum requested amount, inclusive, an analyst may approve.
        senior_analyst_maximum_amount: Maximum requested amount, inclusive, a senior analyst may
            approve. Must be strictly greater than ``analyst_maximum_amount``.
        credit_committee_maximum_amount: Maximum requested amount, inclusive, the credit
            committee may approve. Must be strictly greater than
            ``senior_analyst_maximum_amount``. Any amount above this threshold requires
            executive board authority.
        zero_debt_service_metric_value: Sentinel debt-service-coverage metric value used when
            ``monthly_debt_service`` is zero, since the ratio is undefined in that case. Must be
            strictly positive and large enough to fall in the top coverage band, representing
            the documented policy choice that no debt service obligation is treated as maximum
            favorable coverage.
    """

    version: str
    score_components: tuple[ScoreComponentPolicy, ...]
    automatic_approval_minimum_score: Decimal
    conditional_approval_minimum_score: Decimal
    committee_referral_minimum_score: Decimal
    analyst_maximum_amount: Decimal
    senior_analyst_maximum_amount: Decimal
    credit_committee_maximum_amount: Decimal
    zero_debt_service_metric_value: Decimal


def validate_policy(policy: CreditPolicy) -> None:
    """Validate every invariant a ``CreditPolicy`` must satisfy before it can be applied.

    Args:
        policy: The policy configuration to validate.

    Raises:
        InvalidCreditPolicyError: If any weight, band, or threshold is missing, out of range,
            unsorted, or otherwise internally inconsistent.
    """
    if not isinstance(policy, CreditPolicy):
        raise InvalidCreditPolicyError("policy must be a CreditPolicy.")
    if not isinstance(policy.version, str) or not policy.version.strip():
        raise InvalidCreditPolicyError("policy version must be a non-empty string.")
    if not isinstance(policy.score_components, tuple):
        raise InvalidCreditPolicyError("score_components must be a tuple.")

    _validate_components(policy.score_components)
    _validate_decision_thresholds(policy)
    _validate_authority_thresholds(policy)
    _validate_zero_debt_service_metric(policy)


def _validate_components(components: tuple[ScoreComponentPolicy, ...]) -> None:
    for component_policy in components:
        if not isinstance(component_policy, ScoreComponentPolicy):
            raise InvalidCreditPolicyError(
                "score_components must contain only ScoreComponentPolicy values."
            )
        if not isinstance(component_policy.component, ScoreComponent):
            raise InvalidCreditPolicyError(
                "each component policy must reference a valid ScoreComponent."
            )
        if not isinstance(component_policy.direction, ScoreDirection):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} direction must be a ScoreDirection."
            )
        _require_finite_decimal(
            f"{component_policy.component.value} weight", component_policy.weight
        )
        if not isinstance(component_policy.bands, tuple):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} bands must be a tuple."
            )

    expected = set(ScoreComponent)
    present = {component_policy.component for component_policy in components}
    if present != expected or len(components) != len(expected):
        raise InvalidCreditPolicyError(
            "policy must define exactly one ScoreComponentPolicy per ScoreComponent member."
        )

    weight_total = sum((component_policy.weight for component_policy in components), Decimal("0"))
    if weight_total != _TOTAL_WEIGHT:
        raise InvalidCreditPolicyError(
            f"component weights must sum to exactly {_TOTAL_WEIGHT}, got {weight_total}."
        )

    for component_policy in components:
        if component_policy.weight <= 0:
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} weight must be strictly positive."
            )
        _validate_bands(component_policy)


def _validate_bands(component_policy: ScoreComponentPolicy) -> None:
    bands = component_policy.bands
    if not bands:
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} must define at least one score band."
        )

    for band in bands:
        if not isinstance(band, ScoreBand):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} bands must contain only ScoreBand values."
            )
        if not isinstance(band.boundary, Decimal):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} band boundaries must be Decimal values."
            )
        if band.boundary.is_nan() or band.boundary == Decimal("-Infinity"):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} band boundaries must not be NaN or "
                "negative infinity."
            )
        _require_finite_decimal(f"{component_policy.component.value} band score", band.score)
        if not (_MIN_RAW_SCORE <= band.score <= _MAX_RAW_SCORE):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} band score {band.score} is out of range "
                f"[{_MIN_RAW_SCORE}, {_MAX_RAW_SCORE}]."
            )

    if component_policy.direction is ScoreDirection.HIGHER_IS_BETTER:
        _validate_descending_bands(component_policy)
    else:
        _validate_ascending_bands(component_policy)


def _validate_descending_bands(component_policy: ScoreComponentPolicy) -> None:
    bands = component_policy.bands
    if any(not band.boundary.is_finite() for band in bands):
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} descending boundaries must be finite."
        )
    for previous, current in pairwise(bands):
        if not (previous.boundary > current.boundary and previous.score > current.score):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} bands must be sorted by strictly "
                "descending boundary and strictly descending score."
            )
    if bands[-1].boundary != Decimal("0"):
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} must cover down to a zero boundary."
        )


def _validate_ascending_bands(component_policy: ScoreComponentPolicy) -> None:
    bands = component_policy.bands
    if any(not band.boundary.is_finite() for band in bands[:-1]):
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} boundaries before the final band must be finite."
        )
    if bands[0].boundary < Decimal("0"):
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} boundaries must not be negative."
        )
    for previous, current in pairwise(bands):
        if not (previous.boundary < current.boundary and previous.score > current.score):
            raise InvalidCreditPolicyError(
                f"{component_policy.component.value} bands must be sorted by strictly "
                "ascending boundary and strictly descending score."
            )
    if bands[-1].boundary != Decimal("Infinity"):
        raise InvalidCreditPolicyError(
            f"{component_policy.component.value} must cover up to an infinite boundary."
        )


def _validate_decision_thresholds(policy: CreditPolicy) -> None:
    thresholds = (
        policy.automatic_approval_minimum_score,
        policy.conditional_approval_minimum_score,
        policy.committee_referral_minimum_score,
    )
    for field_name, threshold in zip(
        (
            "automatic_approval_minimum_score",
            "conditional_approval_minimum_score",
            "committee_referral_minimum_score",
        ),
        thresholds,
        strict=True,
    ):
        _require_finite_decimal(field_name, threshold)
        if not (_MIN_RAW_SCORE <= threshold <= _MAX_RAW_SCORE):
            raise InvalidCreditPolicyError(
                f"decision thresholds must fall within [{_MIN_RAW_SCORE}, {_MAX_RAW_SCORE}]."
            )
    if not (thresholds[0] > thresholds[1] > thresholds[2]):
        raise InvalidCreditPolicyError(
            "decision thresholds must be strictly decreasing: automatic approval > "
            "conditional approval > committee referral."
        )


def _validate_authority_thresholds(policy: CreditPolicy) -> None:
    thresholds = (
        policy.analyst_maximum_amount,
        policy.senior_analyst_maximum_amount,
        policy.credit_committee_maximum_amount,
    )
    for field_name, threshold in zip(
        (
            "analyst_maximum_amount",
            "senior_analyst_maximum_amount",
            "credit_committee_maximum_amount",
        ),
        thresholds,
        strict=True,
    ):
        _require_finite_decimal(field_name, threshold)
    if any(threshold <= 0 for threshold in thresholds):
        raise InvalidCreditPolicyError("approval-authority thresholds must be strictly positive.")
    if not (thresholds[0] < thresholds[1] < thresholds[2]):
        raise InvalidCreditPolicyError(
            "approval-authority thresholds must be strictly increasing: analyst < senior "
            "analyst < credit committee."
        )


def _validate_zero_debt_service_metric(policy: CreditPolicy) -> None:
    metric_value = policy.zero_debt_service_metric_value
    _require_finite_decimal("zero_debt_service_metric_value", metric_value)
    if metric_value <= 0:
        raise InvalidCreditPolicyError("zero_debt_service_metric_value must be strictly positive.")

    coverage_policy = next(
        component_policy
        for component_policy in policy.score_components
        if component_policy.component is ScoreComponent.DEBT_SERVICE_COVERAGE
    )
    if coverage_policy.direction is not ScoreDirection.HIGHER_IS_BETTER:
        raise InvalidCreditPolicyError(
            "DEBT_SERVICE_COVERAGE must use HIGHER_IS_BETTER so zero debt service is favorable."
        )
    top_band_boundary = coverage_policy.bands[0].boundary
    if metric_value < top_band_boundary:
        raise InvalidCreditPolicyError(
            "zero_debt_service_metric_value must reach the top DEBT_SERVICE_COVERAGE band."
        )


def _require_finite_decimal(field_name: str, value: object) -> None:
    if not isinstance(value, Decimal):
        raise InvalidCreditPolicyError(f"{field_name} must be a Decimal.")
    if not value.is_finite():
        raise InvalidCreditPolicyError(f"{field_name} must be finite.")


DEMO_POLICY_V1 = CreditPolicy(
    version="credit-core-demo-policy-v1",
    score_components=(
        ScoreComponentPolicy(
            component=ScoreComponent.BUREAU_SCORE,
            weight=Decimal("0.40"),
            direction=ScoreDirection.HIGHER_IS_BETTER,
            bands=(
                ScoreBand(Decimal("800"), Decimal("100")),
                ScoreBand(Decimal("700"), Decimal("80")),
                ScoreBand(Decimal("600"), Decimal("60")),
                ScoreBand(Decimal("500"), Decimal("40")),
                ScoreBand(Decimal("400"), Decimal("20")),
                ScoreBand(Decimal("0"), Decimal("0")),
            ),
        ),
        ScoreComponentPolicy(
            component=ScoreComponent.LEVERAGE_RATIO,
            weight=Decimal("0.25"),
            direction=ScoreDirection.LOWER_IS_BETTER,
            bands=(
                ScoreBand(Decimal("0.50"), Decimal("100")),
                ScoreBand(Decimal("1.00"), Decimal("80")),
                ScoreBand(Decimal("2.00"), Decimal("60")),
                ScoreBand(Decimal("3.00"), Decimal("40")),
                ScoreBand(Decimal("5.00"), Decimal("20")),
                ScoreBand(Decimal("Infinity"), Decimal("0")),
            ),
        ),
        ScoreComponentPolicy(
            component=ScoreComponent.DEBT_SERVICE_COVERAGE,
            weight=Decimal("0.25"),
            direction=ScoreDirection.HIGHER_IS_BETTER,
            bands=(
                ScoreBand(Decimal("2.00"), Decimal("100")),
                ScoreBand(Decimal("1.50"), Decimal("80")),
                ScoreBand(Decimal("1.20"), Decimal("60")),
                ScoreBand(Decimal("1.00"), Decimal("40")),
                ScoreBand(Decimal("0.80"), Decimal("20")),
                ScoreBand(Decimal("0"), Decimal("0")),
            ),
        ),
        ScoreComponentPolicy(
            component=ScoreComponent.OPERATING_HISTORY,
            weight=Decimal("0.10"),
            direction=ScoreDirection.HIGHER_IS_BETTER,
            bands=(
                ScoreBand(Decimal("10"), Decimal("100")),
                ScoreBand(Decimal("5"), Decimal("80")),
                ScoreBand(Decimal("2"), Decimal("60")),
                ScoreBand(Decimal("1"), Decimal("40")),
                ScoreBand(Decimal("0"), Decimal("20")),
            ),
        ),
    ),
    automatic_approval_minimum_score=Decimal("80"),
    conditional_approval_minimum_score=Decimal("60"),
    committee_referral_minimum_score=Decimal("40"),
    analyst_maximum_amount=Decimal("50000"),
    senior_analyst_maximum_amount=Decimal("250000"),
    credit_committee_maximum_amount=Decimal("1000000"),
    zero_debt_service_metric_value=Decimal("999"),
)

validate_policy(DEMO_POLICY_V1)
