"""Policy-mcp's own vocabulary for the credit policy catalog it serves.

These are frozen, immutable Value Objects: plain data holders with no behavior beyond structural
equality, no I/O, and no framework types. They intentionally mirror the shape of
``credit_core.policy.CreditPolicy`` and ``credit_core.domain.CriticalFlag`` without importing
those types - the translation happens once, at the adapter boundary in
``policy_mcp.adapters.credit_core_policy_source``. Every numeric value is ``Decimal``, per this
project's engineering rules for monetary and score values.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ScoreBandView:
    """One boundary/score pair used to map a metric value to a raw component score.

    Attributes:
        boundary: The metric boundary for this band.
        score: The raw score awarded once the boundary is met, in the range [0, 100].
    """

    boundary: Decimal
    score: Decimal


@dataclass(frozen=True, slots=True)
class ScoreComponentView:
    """One scored component of a credit policy: its weight, direction, and ordered bands.

    Attributes:
        component: The scored component's name (e.g. ``"BUREAU_SCORE"``).
        weight: The component's weight in the total score. Weights across every component of a
            policy sum to exactly ``1``.
        direction: Either ``"HIGHER_IS_BETTER"`` or ``"LOWER_IS_BETTER"``.
        bands: The component's boundary/score bands, in policy declaration order.
    """

    component: str
    weight: Decimal
    direction: str
    bands: tuple[ScoreBandView, ...]


@dataclass(frozen=True, slots=True)
class DecisionThresholds:
    """Minimum total-score thresholds, inclusive, for each score-based decision outcome.

    Attributes:
        approval_recommendation_minimum_score: Minimum total score for an approval
            recommendation.
        conditional_approval_minimum_score: Minimum total score for conditional approval.
        committee_referral_minimum_score: Minimum total score for committee referral. A total
            score below this threshold means decline.
    """

    approval_recommendation_minimum_score: Decimal
    conditional_approval_minimum_score: Decimal
    committee_referral_minimum_score: Decimal


@dataclass(frozen=True, slots=True)
class ApprovalAuthorityTier:
    """One approval-authority tier and the requested-amount range it covers.

    Attributes:
        authority: The approval authority's name (e.g. ``"ANALYST"``).
        minimum_amount: The previous tier's ``maximum_amount``, or zero for the first tier.
        maximum_amount: The largest requested amount, inclusive, this tier covers. ``None`` means
            no upper bound (the top tier).
    """

    authority: str
    minimum_amount: Decimal
    maximum_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class PolicySummary:
    """A short, listable summary of one policy version.

    Attributes:
        version: The policy version identifier.
        score_component_count: How many scored components the policy defines.
        approval_authority_tier_count: How many approval-authority tiers the policy defines.
        decision_thresholds: The policy's score-based decision thresholds.
    """

    version: str
    score_component_count: int
    approval_authority_tier_count: int
    decision_thresholds: DecisionThresholds


@dataclass(frozen=True, slots=True)
class PolicyDetail:
    """The full detail of one versioned credit policy.

    Attributes:
        version: The policy version identifier.
        score_components: Every scored component, in policy declaration order.
        decision_thresholds: The policy's score-based decision thresholds.
        approval_authority_tiers: Every approval-authority tier, ordered from the smallest to the
            largest requested-amount range.
        zero_debt_service_metric_value: The sentinel debt-service-coverage metric value used when
            an applicant has no monthly debt service obligation.
    """

    version: str
    score_components: tuple[ScoreComponentView, ...]
    decision_thresholds: DecisionThresholds
    approval_authority_tiers: tuple[ApprovalAuthorityTier, ...]
    zero_debt_service_metric_value: Decimal


@dataclass(frozen=True, slots=True)
class CriticalFlagView:
    """One synthetic critical flag that forces a deterministic block, regardless of score.

    Attributes:
        name: The flag's enum member name (e.g. ``"BANKRUPTCY_FILING"``).
        value: The flag's enum value.
    """

    name: str
    value: str
