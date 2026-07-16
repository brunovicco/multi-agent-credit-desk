"""Truth-table, boundary, and invariant tests for evaluate_credit_application."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from typing import cast

import pytest

from credit_core import (
    DEMO_POLICY_V1,
    ApprovalAuthority,
    CreditApplicationSnapshot,
    CriticalFlag,
    Decision,
    InvalidCreditApplicationError,
    ReasonCode,
    evaluate_credit_application,
)
from credit_core.domain import ScoreComponent

_ANNUAL_REVENUE = Decimal("1000000")
_MONTHLY_DEBT_SERVICE = Decimal("10000")

_BUREAU_SCORE_BY_TIER = {
    0: Decimal("300"),
    20: Decimal("450"),
    40: Decimal("550"),
    60: Decimal("650"),
    80: Decimal("750"),
    100: Decimal("850"),
}
_LEVERAGE_RATIO_BY_TIER = {
    0: Decimal("6"),
    20: Decimal("4"),
    40: Decimal("2.5"),
    60: Decimal("1.5"),
    80: Decimal("0.8"),
    100: Decimal("0.3"),
}
_DSCR_BY_TIER = {
    0: Decimal("0.5"),
    20: Decimal("0.9"),
    40: Decimal("1.05"),
    60: Decimal("1.3"),
    80: Decimal("1.6"),
    100: Decimal("2.5"),
}
_HISTORY_YEARS_BY_TIER = {20: 0, 40: 1, 60: 2, 80: 5, 100: 10}


def _tiered_snapshot(
    bureau_tier: int,
    leverage_tier: int,
    dscr_tier: int,
    history_tier: int,
    requested_amount: Decimal = Decimal("30000"),
) -> CreditApplicationSnapshot:
    """Build a snapshot whose four component raw scores match the given tiers exactly.

    Each tier is one of the raw scores a policy band can produce (0, 20, 40, 60, 80, 100),
    letting boundary tests target an exact total score without depending on ratio arithmetic.
    """
    return CreditApplicationSnapshot(
        annual_revenue=_ANNUAL_REVENUE,
        total_debt=_LEVERAGE_RATIO_BY_TIER[leverage_tier] * _ANNUAL_REVENUE,
        monthly_debt_service=_MONTHLY_DEBT_SERVICE,
        monthly_operating_cash_flow=_DSCR_BY_TIER[dscr_tier] * _MONTHLY_DEBT_SERVICE,
        bureau_score=_BUREAU_SCORE_BY_TIER[bureau_tier],
        years_in_operation=_HISTORY_YEARS_BY_TIER[history_tier],
        requested_amount=requested_amount,
    )


class TestScenarios:
    """Named synthetic company scenarios covering the decision truth table."""

    def test_healthy_company_is_automatically_approved(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        result = evaluate_credit_application(healthy_snapshot)
        assert result.total_score == Decimal("100.00")
        assert result.decision is Decision.AUTOMATIC_APPROVAL
        assert result.approval_authority is ApprovalAuthority.ANALYST
        assert result.blocking_reasons == ()
        assert result.reason_codes == (
            ReasonCode.SCORE_MEETS_AUTOMATIC_APPROVAL_THRESHOLD,
            ReasonCode.REQUESTED_AMOUNT_WITHIN_ANALYST_AUTHORITY,
        )

    def test_leveraged_company_is_referred_to_committee(self) -> None:
        snapshot = CreditApplicationSnapshot(
            annual_revenue=Decimal("1000000"),
            total_debt=Decimal("2500000"),
            monthly_debt_service=Decimal("20000"),
            monthly_operating_cash_flow=Decimal("22000"),
            bureau_score=Decimal("650"),
            years_in_operation=4,
            requested_amount=Decimal("300000"),
        )
        result = evaluate_credit_application(snapshot)
        assert result.total_score == Decimal("50.00")
        assert result.decision is Decision.COMMITTEE_REFERRAL
        assert result.approval_authority is ApprovalAuthority.CREDIT_COMMITTEE

    def test_critically_flagged_company_is_blocked(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        flagged = replace(
            healthy_snapshot, critical_flags=frozenset({CriticalFlag.SEVERE_PAYMENT_DEFAULT})
        )
        result = evaluate_credit_application(flagged)
        assert result.decision is Decision.BLOCKED
        assert result.approval_authority is ApprovalAuthority.NONE
        assert result.blocking_reasons == (ReasonCode.CRITICAL_FLAG_SEVERE_PAYMENT_DEFAULT,)
        assert result.reason_codes == ()

    def test_critical_block_overrides_an_otherwise_perfect_score(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        flagged = replace(healthy_snapshot, critical_flags=frozenset({CriticalFlag.FRAUD_ALERT}))
        result = evaluate_credit_application(flagged)
        assert result.total_score == Decimal("100.00")
        assert result.decision is Decision.BLOCKED
        assert result.approval_authority is ApprovalAuthority.NONE

    def test_multiple_critical_flags_are_reported_in_deterministic_order(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        flagged = replace(
            healthy_snapshot,
            critical_flags=frozenset({CriticalFlag.FRAUD_ALERT, CriticalFlag.BANKRUPTCY_FILING}),
        )
        result = evaluate_credit_application(flagged)
        assert result.blocking_reasons == (
            ReasonCode.CRITICAL_FLAG_BANKRUPTCY_FILING,
            ReasonCode.CRITICAL_FLAG_FRAUD_ALERT,
        )


class TestScoreDecisionBoundaries:
    """Exact-boundary coverage for every score-based decision threshold."""

    @pytest.mark.parametrize(
        (
            "bureau_tier",
            "leverage_tier",
            "dscr_tier",
            "history_tier",
            "expected_total",
            "expected_decision",
        ),
        [
            (100, 60, 60, 100, Decimal("80.00"), Decision.AUTOMATIC_APPROVAL),
            (100, 60, 60, 80, Decimal("78.00"), Decision.CONDITIONAL_APPROVAL),
            (0, 100, 100, 100, Decimal("60.00"), Decision.CONDITIONAL_APPROVAL),
            (0, 80, 100, 100, Decimal("55.00"), Decision.COMMITTEE_REFERRAL),
            (40, 40, 40, 40, Decimal("40.00"), Decision.COMMITTEE_REFERRAL),
            (40, 40, 40, 20, Decimal("38.00"), Decision.DECLINE),
        ],
    )
    def test_score_decision_boundary(
        self,
        bureau_tier: int,
        leverage_tier: int,
        dscr_tier: int,
        history_tier: int,
        expected_total: Decimal,
        expected_decision: Decision,
    ) -> None:
        snapshot = _tiered_snapshot(bureau_tier, leverage_tier, dscr_tier, history_tier)
        result = evaluate_credit_application(snapshot)
        assert result.total_score == expected_total
        assert result.decision is expected_decision


class TestApprovalAuthorityBoundaries:
    """Exact-boundary coverage for every requested-amount authority threshold."""

    @pytest.mark.parametrize(
        ("requested_amount", "expected_authority"),
        [
            (Decimal("50000"), ApprovalAuthority.ANALYST),
            (Decimal("50000.01"), ApprovalAuthority.SENIOR_ANALYST),
            (Decimal("250000"), ApprovalAuthority.SENIOR_ANALYST),
            (Decimal("250000.01"), ApprovalAuthority.CREDIT_COMMITTEE),
            (Decimal("1000000"), ApprovalAuthority.CREDIT_COMMITTEE),
            (Decimal("1000000.01"), ApprovalAuthority.EXECUTIVE_BOARD),
        ],
    )
    def test_approval_authority_boundary(
        self,
        requested_amount: Decimal,
        expected_authority: ApprovalAuthority,
        healthy_snapshot: CreditApplicationSnapshot,
    ) -> None:
        snapshot = replace(healthy_snapshot, requested_amount=requested_amount)
        result = evaluate_credit_application(snapshot)
        assert result.approval_authority is expected_authority

    def test_declined_application_has_no_approval_authority(self) -> None:
        snapshot = _tiered_snapshot(0, 0, 0, 20, requested_amount=Decimal("10000"))
        result = evaluate_credit_application(snapshot)
        assert result.decision is Decision.DECLINE
        assert result.approval_authority is ApprovalAuthority.NONE
        assert ReasonCode.NO_APPROVAL_AUTHORITY_DECISION_NOT_APPROVED in result.reason_codes

    def test_committee_referral_requires_committee_authority_even_for_small_amount(self) -> None:
        snapshot = _tiered_snapshot(0, 80, 100, 100, requested_amount=Decimal("30000"))

        result = evaluate_credit_application(snapshot)

        assert result.decision is Decision.COMMITTEE_REFERRAL
        assert result.approval_authority is ApprovalAuthority.CREDIT_COMMITTEE
        assert (
            ReasonCode.COMMITTEE_REFERRAL_REQUIRES_CREDIT_COMMITTEE_AUTHORITY in result.reason_codes
        )

    def test_committee_referral_above_committee_limit_requires_executive_board(self) -> None:
        snapshot = _tiered_snapshot(0, 80, 100, 100, requested_amount=Decimal("1000000.01"))

        result = evaluate_credit_application(snapshot)

        assert result.decision is Decision.COMMITTEE_REFERRAL
        assert result.approval_authority is ApprovalAuthority.EXECUTIVE_BOARD


class TestEdgeCases:
    def test_zero_debt_service_yields_maximum_coverage_score(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(
            healthy_snapshot,
            monthly_debt_service=Decimal("0"),
            monthly_operating_cash_flow=Decimal("5000"),
        )
        result = evaluate_credit_application(snapshot)
        coverage = next(
            component
            for component in result.component_scores
            if component.component is ScoreComponent.DEBT_SERVICE_COVERAGE
        )
        assert coverage.metric_value == DEMO_POLICY_V1.zero_debt_service_metric_value
        assert coverage.raw_score == Decimal("100")


class TestInvalidInputs:
    def test_float_input_is_rejected(self, healthy_snapshot: CreditApplicationSnapshot) -> None:
        snapshot = replace(healthy_snapshot, annual_revenue=cast(Decimal, 1000000.0))

        with pytest.raises(InvalidCreditApplicationError, match="annual_revenue must be a Decimal"):
            evaluate_credit_application(snapshot)

    @pytest.mark.parametrize(
        "non_finite_value",
        [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
    )
    def test_non_finite_decimal_input_is_rejected(
        self,
        non_finite_value: Decimal,
        healthy_snapshot: CreditApplicationSnapshot,
    ) -> None:
        snapshot = replace(healthy_snapshot, total_debt=non_finite_value)

        with pytest.raises(InvalidCreditApplicationError, match="total_debt must be finite"):
            evaluate_credit_application(snapshot)

    def test_boolean_years_in_operation_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, years_in_operation=cast(int, True))

        with pytest.raises(
            InvalidCreditApplicationError, match="years_in_operation must be an int"
        ):
            evaluate_credit_application(snapshot)

    def test_invalid_critical_flag_type_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        invalid_flags = cast(frozenset[CriticalFlag], frozenset({"FRAUD_ALERT"}))
        snapshot = replace(healthy_snapshot, critical_flags=invalid_flags)

        with pytest.raises(
            InvalidCreditApplicationError, match="critical_flags must be a frozenset"
        ):
            evaluate_credit_application(snapshot)

    def test_negative_total_debt_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, total_debt=Decimal("-1"))
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    def test_negative_monthly_debt_service_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, monthly_debt_service=Decimal("-1"))
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    def test_negative_monthly_operating_cash_flow_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, monthly_operating_cash_flow=Decimal("-1"))
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    def test_non_positive_annual_revenue_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, annual_revenue=Decimal("0"))
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    def test_non_positive_requested_amount_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, requested_amount=Decimal("0"))
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    def test_negative_years_in_operation_is_rejected(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, years_in_operation=-1)
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)

    @pytest.mark.parametrize("bureau_score", [Decimal("-1"), Decimal("1001")])
    def test_invalid_bureau_score_is_rejected(
        self, bureau_score: Decimal, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        snapshot = replace(healthy_snapshot, bureau_score=bureau_score)
        with pytest.raises(InvalidCreditApplicationError):
            evaluate_credit_application(snapshot)


class TestDeterminismAndImmutability:
    def test_repeated_evaluation_is_deterministic(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        first = evaluate_credit_application(healthy_snapshot)
        second = evaluate_credit_application(healthy_snapshot)
        assert first == second

    def test_snapshot_is_immutable(self, healthy_snapshot: CreditApplicationSnapshot) -> None:
        with pytest.raises(FrozenInstanceError):
            healthy_snapshot.bureau_score = Decimal("900")  # type: ignore[misc]

    def test_result_is_immutable(self, healthy_snapshot: CreditApplicationSnapshot) -> None:
        result = evaluate_credit_application(healthy_snapshot)
        with pytest.raises(FrozenInstanceError):
            result.total_score = Decimal("0")  # type: ignore[misc]

    def test_component_score_is_immutable(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        result = evaluate_credit_application(healthy_snapshot)
        with pytest.raises(FrozenInstanceError):
            result.component_scores[0].raw_score = Decimal("0")  # type: ignore[misc]


class TestDecimalOnlyCalculation:
    def test_all_numeric_result_fields_are_decimal(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        result = evaluate_credit_application(healthy_snapshot)
        assert isinstance(result.total_score, Decimal)
        for component in result.component_scores:
            assert isinstance(component.metric_value, Decimal)
            assert isinstance(component.raw_score, Decimal)
            assert isinstance(component.weight, Decimal)
            assert isinstance(component.weighted_score, Decimal)


class TestResultInvariants:
    def test_component_breakdown_sums_to_total_score(
        self, healthy_snapshot: CreditApplicationSnapshot
    ) -> None:
        result = evaluate_credit_application(healthy_snapshot)
        breakdown_total = sum(
            (component.weighted_score for component in result.component_scores), Decimal("0")
        )
        assert breakdown_total == result.total_score

    @pytest.mark.parametrize("critical_flags", [frozenset(), frozenset({CriticalFlag.FRAUD_ALERT})])
    def test_policy_version_is_always_included(
        self,
        critical_flags: frozenset[CriticalFlag],
        healthy_snapshot: CreditApplicationSnapshot,
    ) -> None:
        snapshot = replace(healthy_snapshot, critical_flags=critical_flags)
        result = evaluate_credit_application(snapshot)
        assert result.policy_version == DEMO_POLICY_V1.version
