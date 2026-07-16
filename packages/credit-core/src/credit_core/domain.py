"""Immutable value objects and closed enums for the deterministic credit evaluation core.

Every type here is a plain, frozen data holder: no I/O, no behavior beyond structural equality.
Evaluation logic lives in ``credit_core.evaluation``; policy configuration lives in
``credit_core.policy``.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class CriticalFlag(Enum):
    """Synthetic critical red flags that force a deterministic block.

    These are demo-only categories for the synthetic policy shipped in ``credit_core.policy``;
    they are not a production risk taxonomy.
    """

    BANKRUPTCY_FILING = "BANKRUPTCY_FILING"
    SEVERE_PAYMENT_DEFAULT = "SEVERE_PAYMENT_DEFAULT"
    FRAUD_ALERT = "FRAUD_ALERT"


class ScoreComponent(Enum):
    """The four score components evaluated by the synthetic demo credit policy."""

    BUREAU_SCORE = "BUREAU_SCORE"
    LEVERAGE_RATIO = "LEVERAGE_RATIO"
    DEBT_SERVICE_COVERAGE = "DEBT_SERVICE_COVERAGE"
    OPERATING_HISTORY = "OPERATING_HISTORY"


class Decision(Enum):
    """Closed set of credit decisions produced by ``evaluate_credit_application``."""

    APPROVAL_RECOMMENDED = "APPROVAL_RECOMMENDED"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"
    COMMITTEE_REFERRAL = "COMMITTEE_REFERRAL"
    DECLINE = "DECLINE"
    BLOCKED = "BLOCKED"


class ApprovalAuthority(Enum):
    """Closed set of approval authorities.

    ``NONE`` applies whenever no approval is granted, that is, whenever ``Decision`` is
    ``DECLINE`` or ``BLOCKED``.
    """

    NONE = "NONE"
    ANALYST = "ANALYST"
    SENIOR_ANALYST = "SENIOR_ANALYST"
    CREDIT_COMMITTEE = "CREDIT_COMMITTEE"
    EXECUTIVE_BOARD = "EXECUTIVE_BOARD"


class ReasonCode(Enum):
    """Stable, deterministic reason codes for decisions, authority, and blocking outcomes."""

    SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD = "SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD"
    SCORE_MEETS_CONDITIONAL_APPROVAL_THRESHOLD = "SCORE_MEETS_CONDITIONAL_APPROVAL_THRESHOLD"
    SCORE_MEETS_COMMITTEE_REFERRAL_THRESHOLD = "SCORE_MEETS_COMMITTEE_REFERRAL_THRESHOLD"
    SCORE_BELOW_COMMITTEE_REFERRAL_THRESHOLD = "SCORE_BELOW_COMMITTEE_REFERRAL_THRESHOLD"
    REQUESTED_AMOUNT_WITHIN_ANALYST_AUTHORITY = "REQUESTED_AMOUNT_WITHIN_ANALYST_AUTHORITY"
    REQUESTED_AMOUNT_WITHIN_SENIOR_ANALYST_AUTHORITY = (
        "REQUESTED_AMOUNT_WITHIN_SENIOR_ANALYST_AUTHORITY"
    )
    REQUESTED_AMOUNT_WITHIN_CREDIT_COMMITTEE_AUTHORITY = (
        "REQUESTED_AMOUNT_WITHIN_CREDIT_COMMITTEE_AUTHORITY"
    )
    REQUESTED_AMOUNT_REQUIRES_EXECUTIVE_BOARD_AUTHORITY = (
        "REQUESTED_AMOUNT_REQUIRES_EXECUTIVE_BOARD_AUTHORITY"
    )
    COMMITTEE_REFERRAL_REQUIRES_CREDIT_COMMITTEE_AUTHORITY = (
        "COMMITTEE_REFERRAL_REQUIRES_CREDIT_COMMITTEE_AUTHORITY"
    )
    NO_APPROVAL_AUTHORITY_DECISION_NOT_APPROVED = "NO_APPROVAL_AUTHORITY_DECISION_NOT_APPROVED"
    CRITICAL_FLAG_BANKRUPTCY_FILING = "CRITICAL_FLAG_BANKRUPTCY_FILING"
    CRITICAL_FLAG_SEVERE_PAYMENT_DEFAULT = "CRITICAL_FLAG_SEVERE_PAYMENT_DEFAULT"
    CRITICAL_FLAG_FRAUD_ALERT = "CRITICAL_FLAG_FRAUD_ALERT"


@dataclass(frozen=True, slots=True)
class CreditApplicationSnapshot:
    """Immutable, pre-validated financial and bureau snapshot of a credit applicant.

    All monetary, ratio-bearing, and score inputs are ``Decimal``. This is a plain data
    snapshot: it carries no behavior and is validated by
    ``credit_core.evaluation.validate_snapshot`` before scoring.

    Attributes:
        annual_revenue: Reported annual revenue. Must be strictly positive.
        total_debt: Total outstanding debt. Must not be negative.
        monthly_debt_service: Monthly debt service obligation. Must not be negative; zero is a
            valid edge case meaning the applicant has no current debt service obligation.
        monthly_operating_cash_flow: Monthly operating cash flow. Must not be negative.
        bureau_score: External bureau score on a 0-1000 scale. Must fall within that range.
        years_in_operation: Whole years the applicant has been operating. Must not be negative.
        requested_amount: Requested credit amount. Must be strictly positive.
        critical_flags: Synthetic critical red flags reported for the applicant. An empty
            frozenset means no critical flag was raised.
    """

    annual_revenue: Decimal
    total_debt: Decimal
    monthly_debt_service: Decimal
    monthly_operating_cash_flow: Decimal
    bureau_score: Decimal
    years_in_operation: int
    requested_amount: Decimal
    critical_flags: frozenset[CriticalFlag] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ComponentScore:
    """One scored component of the synthetic demo policy, before and after weighting."""

    component: ScoreComponent
    metric_value: Decimal
    raw_score: Decimal
    weight: Decimal
    weighted_score: Decimal


@dataclass(frozen=True, slots=True)
class CreditEvaluationResult:
    """Structured, reproducible outcome of ``evaluate_credit_application``.

    ``blocking_reasons`` is non-empty only when ``decision`` is ``Decision.BLOCKED``. A
    non-empty ``blocking_reasons`` always takes precedence over ``total_score`` in determining
    ``decision`` and ``approval_authority``, which is set to ``ApprovalAuthority.NONE`` whenever
    blocked. ``total_score`` and ``component_scores`` are always populated, even when blocked,
    so the evaluation remains fully auditable.

    Attributes:
        policy_version: Version identifier of the policy applied, always present.
        total_score: Sum of every component's ``weighted_score``.
        component_scores: Full per-component breakdown, in policy declaration order.
        decision: The final decision.
        approval_authority: The approval authority required for ``decision``.
        reason_codes: Deterministic reason codes explaining ``decision`` and
            ``approval_authority``. Empty whenever ``decision`` is ``BLOCKED``.
        blocking_reasons: Deterministic reason codes for each critical flag that caused a
            block. Empty unless ``decision`` is ``BLOCKED``.
    """

    policy_version: str
    total_score: Decimal
    component_scores: tuple[ComponentScore, ...]
    decision: Decision
    approval_authority: ApprovalAuthority
    reason_codes: tuple[ReasonCode, ...]
    blocking_reasons: tuple[ReasonCode, ...]
