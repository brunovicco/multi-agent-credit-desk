"""The pure, deterministic credit evaluation entrypoint.

This module contains the only evaluation logic in ``credit_core``: input validation and the
single pure function ``evaluate_credit_application``. It has no I/O, no clock, and no
randomness - the same snapshot and policy always produce an equal
``CreditEvaluationResult``.
"""

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from credit_core.domain import (
    ApprovalAuthority,
    ComponentScore,
    CreditApplicationSnapshot,
    CreditEvaluationResult,
    CriticalFlag,
    Decision,
    ReasonCode,
    ScoreComponent,
)
from credit_core.errors import InvalidCreditApplicationError
from credit_core.policy import (
    DEMO_POLICY_V1,
    SCORE_QUANTUM,
    CreditPolicy,
    ScoreComponentPolicy,
    ScoreDirection,
    validate_policy,
)

_MIN_BUREAU_SCORE = Decimal("0")
_MAX_BUREAU_SCORE = Decimal("1000")
_EVALUATION_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)
_DECIMAL_SNAPSHOT_FIELDS = (
    "annual_revenue",
    "total_debt",
    "monthly_debt_service",
    "monthly_operating_cash_flow",
    "bureau_score",
    "requested_amount",
)

_CRITICAL_FLAG_REASON_CODES: dict[CriticalFlag, ReasonCode] = {
    CriticalFlag.BANKRUPTCY_FILING: ReasonCode.CRITICAL_FLAG_BANKRUPTCY_FILING,
    CriticalFlag.SEVERE_PAYMENT_DEFAULT: ReasonCode.CRITICAL_FLAG_SEVERE_PAYMENT_DEFAULT,
    CriticalFlag.FRAUD_ALERT: ReasonCode.CRITICAL_FLAG_FRAUD_ALERT,
}


def validate_snapshot(snapshot: CreditApplicationSnapshot) -> None:
    """Validate every invariant a ``CreditApplicationSnapshot`` must satisfy before scoring.

    Args:
        snapshot: The applicant snapshot to validate.

    Raises:
        InvalidCreditApplicationError: If a monetary value is negative or non-positive where a
            strictly positive value is required, the bureau score is out of range, years in
            operation is negative, or the requested amount is not strictly positive.
    """
    if not isinstance(snapshot, CreditApplicationSnapshot):
        raise InvalidCreditApplicationError("snapshot must be a CreditApplicationSnapshot.")

    for field_name in _DECIMAL_SNAPSHOT_FIELDS:
        _require_finite_decimal(field_name, getattr(snapshot, field_name))

    if type(snapshot.years_in_operation) is not int:
        raise InvalidCreditApplicationError("years_in_operation must be an int.")
    if not isinstance(snapshot.critical_flags, frozenset) or any(
        not isinstance(flag, CriticalFlag) for flag in snapshot.critical_flags
    ):
        raise InvalidCreditApplicationError(
            "critical_flags must be a frozenset containing only CriticalFlag values."
        )

    if snapshot.annual_revenue <= 0:
        raise InvalidCreditApplicationError("annual_revenue must be strictly positive.")
    if snapshot.total_debt < 0:
        raise InvalidCreditApplicationError("total_debt must not be negative.")
    if snapshot.monthly_debt_service < 0:
        raise InvalidCreditApplicationError("monthly_debt_service must not be negative.")
    if snapshot.monthly_operating_cash_flow < 0:
        raise InvalidCreditApplicationError("monthly_operating_cash_flow must not be negative.")
    if not (_MIN_BUREAU_SCORE <= snapshot.bureau_score <= _MAX_BUREAU_SCORE):
        raise InvalidCreditApplicationError(
            f"bureau_score must fall within [{_MIN_BUREAU_SCORE}, {_MAX_BUREAU_SCORE}]."
        )
    if snapshot.years_in_operation < 0:
        raise InvalidCreditApplicationError("years_in_operation must not be negative.")
    if snapshot.requested_amount <= 0:
        raise InvalidCreditApplicationError("requested_amount must be strictly positive.")


def _require_finite_decimal(field_name: str, value: object) -> None:
    if not isinstance(value, Decimal):
        raise InvalidCreditApplicationError(f"{field_name} must be a Decimal.")
    if not value.is_finite():
        raise InvalidCreditApplicationError(f"{field_name} must be finite.")


def evaluate_credit_application(
    snapshot: CreditApplicationSnapshot,
    policy: CreditPolicy = DEMO_POLICY_V1,
) -> CreditEvaluationResult:
    """Evaluate one credit application snapshot against a deterministic credit policy.

    This is the single pure entrypoint of ``credit_core``: given an equal snapshot and policy,
    it always returns an equal result. Critical red flags in ``snapshot.critical_flags`` take
    precedence over the score-based decision and approval authority, per
    ``docs/adr/0008-deterministic-core-without-llm.md``; the score and its full breakdown are
    still computed and returned even when blocked, so the result stays fully auditable.

    Args:
        snapshot: The applicant financial and bureau snapshot. Validated on entry.
        policy: The credit policy to apply. Validated on entry. Defaults to ``DEMO_POLICY_V1``,
            a synthetic demo policy - see ``packages/credit-core/README.md`` before using any
            other policy in a non-demo context.

    Returns:
        A ``CreditEvaluationResult`` carrying the policy version, total score, full component
        breakdown, decision, approval authority, and reason codes.

    Raises:
        InvalidCreditApplicationError: If ``snapshot`` violates an input invariant.
        InvalidCreditPolicyError: If ``policy`` violates a configuration invariant.
    """
    validate_policy(policy)
    validate_snapshot(snapshot)

    with localcontext(_EVALUATION_CONTEXT):
        return _evaluate_validated(snapshot, policy)


def _evaluate_validated(
    snapshot: CreditApplicationSnapshot,
    policy: CreditPolicy,
) -> CreditEvaluationResult:
    component_scores = tuple(
        _score_component(component_policy, snapshot, policy)
        for component_policy in policy.score_components
    )
    total_score = sum(
        (component.weighted_score for component in component_scores), Decimal("0")
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_EVEN)

    if snapshot.critical_flags:
        blocking_reasons = tuple(
            _CRITICAL_FLAG_REASON_CODES[flag]
            for flag in sorted(snapshot.critical_flags, key=lambda flag: flag.name)
        )
        return CreditEvaluationResult(
            policy_version=policy.version,
            total_score=total_score,
            component_scores=component_scores,
            decision=Decision.BLOCKED,
            approval_authority=ApprovalAuthority.NONE,
            reason_codes=(),
            blocking_reasons=blocking_reasons,
        )

    decision, decision_reason = _decide(total_score, policy)
    authority, authority_reason = _authority(decision, snapshot.requested_amount, policy)

    return CreditEvaluationResult(
        policy_version=policy.version,
        total_score=total_score,
        component_scores=component_scores,
        decision=decision,
        approval_authority=authority,
        reason_codes=(decision_reason, authority_reason),
        blocking_reasons=(),
    )


def _score_component(
    component_policy: ScoreComponentPolicy,
    snapshot: CreditApplicationSnapshot,
    policy: CreditPolicy,
) -> ComponentScore:
    metric_value = _metric_value(component_policy.component, snapshot, policy)
    raw_score = _raw_score(metric_value, component_policy)
    weighted_score = (raw_score * component_policy.weight).quantize(
        SCORE_QUANTUM, rounding=ROUND_HALF_EVEN
    )
    return ComponentScore(
        component=component_policy.component,
        metric_value=metric_value,
        raw_score=raw_score,
        weight=component_policy.weight,
        weighted_score=weighted_score,
    )


def _metric_value(
    component: ScoreComponent,
    snapshot: CreditApplicationSnapshot,
    policy: CreditPolicy,
) -> Decimal:
    if component is ScoreComponent.BUREAU_SCORE:
        return snapshot.bureau_score
    if component is ScoreComponent.LEVERAGE_RATIO:
        return snapshot.total_debt / snapshot.annual_revenue
    if component is ScoreComponent.DEBT_SERVICE_COVERAGE:
        if snapshot.monthly_debt_service == 0:
            return policy.zero_debt_service_metric_value
        return snapshot.monthly_operating_cash_flow / snapshot.monthly_debt_service
    return Decimal(snapshot.years_in_operation)


def _raw_score(metric_value: Decimal, component_policy: ScoreComponentPolicy) -> Decimal:
    if component_policy.direction is ScoreDirection.HIGHER_IS_BETTER:
        for band in component_policy.bands:
            if metric_value >= band.boundary:
                return band.score
    else:
        for band in component_policy.bands:
            if metric_value <= band.boundary:
                return band.score
    raise AssertionError(  # pragma: no cover
        f"no band matched metric_value={metric_value} for {component_policy.component}: "
        "policy validation should have made this unreachable."
    )


def _decide(total_score: Decimal, policy: CreditPolicy) -> tuple[Decision, ReasonCode]:
    if total_score >= policy.approval_recommendation_minimum_score:
        return (
            Decision.APPROVAL_RECOMMENDED,
            ReasonCode.SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD,
        )
    if total_score >= policy.conditional_approval_minimum_score:
        return (
            Decision.CONDITIONAL_APPROVAL,
            ReasonCode.SCORE_MEETS_CONDITIONAL_APPROVAL_THRESHOLD,
        )
    if total_score >= policy.committee_referral_minimum_score:
        return Decision.COMMITTEE_REFERRAL, ReasonCode.SCORE_MEETS_COMMITTEE_REFERRAL_THRESHOLD
    return Decision.DECLINE, ReasonCode.SCORE_BELOW_COMMITTEE_REFERRAL_THRESHOLD


def _authority(
    decision: Decision,
    requested_amount: Decimal,
    policy: CreditPolicy,
) -> tuple[ApprovalAuthority, ReasonCode]:
    if decision in (Decision.DECLINE, Decision.BLOCKED):
        return ApprovalAuthority.NONE, ReasonCode.NO_APPROVAL_AUTHORITY_DECISION_NOT_APPROVED
    if decision is Decision.COMMITTEE_REFERRAL:
        if requested_amount > policy.credit_committee_maximum_amount:
            return (
                ApprovalAuthority.EXECUTIVE_BOARD,
                ReasonCode.REQUESTED_AMOUNT_REQUIRES_EXECUTIVE_BOARD_AUTHORITY,
            )
        return (
            ApprovalAuthority.CREDIT_COMMITTEE,
            ReasonCode.COMMITTEE_REFERRAL_REQUIRES_CREDIT_COMMITTEE_AUTHORITY,
        )
    if requested_amount <= policy.analyst_maximum_amount:
        return ApprovalAuthority.ANALYST, ReasonCode.REQUESTED_AMOUNT_WITHIN_ANALYST_AUTHORITY
    if requested_amount <= policy.senior_analyst_maximum_amount:
        return (
            ApprovalAuthority.SENIOR_ANALYST,
            ReasonCode.REQUESTED_AMOUNT_WITHIN_SENIOR_ANALYST_AUTHORITY,
        )
    if requested_amount <= policy.credit_committee_maximum_amount:
        return (
            ApprovalAuthority.CREDIT_COMMITTEE,
            ReasonCode.REQUESTED_AMOUNT_WITHIN_CREDIT_COMMITTEE_AUTHORITY,
        )
    return (
        ApprovalAuthority.EXECUTIVE_BOARD,
        ReasonCode.REQUESTED_AMOUNT_REQUIRES_EXECUTIVE_BOARD_AUTHORITY,
    )
