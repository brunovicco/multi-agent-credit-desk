"""Drift-regression tests: the adapter must match credit_core field-for-field, not spot checks.

This is the executable form of the core architectural decision recorded in
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``: what decisao-agent
reports can never silently drift from what ``credit_core`` actually computes.
"""

from decimal import Decimal

import pytest

from credit_core.domain import CreditApplicationSnapshot, CriticalFlag
from credit_core.evaluation import evaluate_credit_application
from decisao_agent.adapters.credit_core_evaluation_adapter import CreditCoreEvaluationAdapter
from decisao_agent.domain.errors import InvalidApplicationSnapshotError
from decisao_agent.domain.snapshot import ApplicationSnapshot


@pytest.fixture
def adapter() -> CreditCoreEvaluationAdapter:
    return CreditCoreEvaluationAdapter()


def _healthy_snapshot(
    critical_flags: frozenset[str] = frozenset(), annual_revenue: Decimal = Decimal("1000000")
) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        annual_revenue=annual_revenue,
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
        critical_flags=critical_flags,
    )


def _healthy_credit_core_snapshot(
    critical_flags: frozenset[CriticalFlag] = frozenset(),
) -> CreditApplicationSnapshot:
    return CreditApplicationSnapshot(
        annual_revenue=Decimal("1000000"),
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
        critical_flags=critical_flags,
    )


def test_evaluate_matches_credit_core_field_for_field(
    adapter: CreditCoreEvaluationAdapter,
) -> None:
    opinion = adapter.evaluate(_healthy_snapshot())
    expected = evaluate_credit_application(_healthy_credit_core_snapshot())

    assert opinion.policy_version == expected.policy_version
    assert opinion.total_score == expected.total_score
    assert opinion.decision == expected.decision.value
    assert opinion.approval_authority == expected.approval_authority.value
    assert opinion.reason_codes == tuple(code.value for code in expected.reason_codes)
    assert opinion.blocking_reasons == tuple(code.value for code in expected.blocking_reasons)

    assert len(opinion.component_scores) == len(expected.component_scores)
    for view, component_score in zip(
        opinion.component_scores, expected.component_scores, strict=True
    ):
        assert view.component == component_score.component.value
        assert view.metric_value == component_score.metric_value
        assert view.raw_score == component_score.raw_score
        assert view.weight == component_score.weight
        assert view.weighted_score == component_score.weighted_score


def test_evaluate_raises_for_an_unknown_critical_flag_name(
    adapter: CreditCoreEvaluationAdapter,
) -> None:
    snapshot = _healthy_snapshot(critical_flags=frozenset({"NOT_A_REAL_FLAG"}))

    with pytest.raises(InvalidApplicationSnapshotError):
        adapter.evaluate(snapshot)


def test_evaluate_raises_for_a_credit_core_validation_failure(
    adapter: CreditCoreEvaluationAdapter,
) -> None:
    invalid_snapshot = _healthy_snapshot(annual_revenue=Decimal("0"))

    with pytest.raises(InvalidApplicationSnapshotError) as exc_info:
        adapter.evaluate(invalid_snapshot)

    assert "annual_revenue" in exc_info.value.reason


def test_evaluate_translates_a_critical_flag_into_a_block(
    adapter: CreditCoreEvaluationAdapter,
) -> None:
    opinion = adapter.evaluate(_healthy_snapshot(critical_flags=frozenset({"FRAUD_ALERT"})))

    assert opinion.decision == "BLOCKED"
    assert opinion.blocking_reasons == ("CRITICAL_FLAG_FRAUD_ALERT",)
