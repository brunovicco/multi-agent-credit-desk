"""Behavior tests for EvaluateCreditApplicationUseCase against fake ports.

Per .claude/rules/testing.md, unit tests isolate external dependencies: this suite never
imports CreditCoreEvaluationAdapter or PolicyMcpClient, only hand-written fakes that implement
the two ports structurally.
"""

import asyncio
from decimal import Decimal

import pytest

from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.application.ports import PolicyCatalogSnapshot
from decisao_agent.domain.errors import PolicyVersionMismatchError, UnknownCriticalFlagError
from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot

_FAKE_OPINION = CreditOpinion(
    policy_version="fake-policy-v1",
    total_score=Decimal("80"),
    component_scores=(),
    decision="APPROVAL_RECOMMENDED",
    approval_authority="ANALYST",
    reason_codes=("SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD",),
    blocking_reasons=(),
)


def _healthy_snapshot(critical_flags: frozenset[str] = frozenset()) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        annual_revenue=Decimal("1000000"),
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
        critical_flags=critical_flags,
    )


class _FakeCreditEvaluationPort:
    """A hand-written test double implementing CreditEvaluationPort structurally."""

    def __init__(self, opinion: CreditOpinion = _FAKE_OPINION) -> None:
        self._opinion = opinion
        self.called = False

    def evaluate(self, snapshot: ApplicationSnapshot) -> CreditOpinion:
        self.called = True
        return self._opinion


class _FakePolicyCatalogPort:
    """A hand-written test double implementing PolicyCatalogPort structurally."""

    def __init__(
        self,
        known_critical_flag_names: frozenset[str] = frozenset(),
        known_policy_versions: frozenset[str] = frozenset({"fake-policy-v1"}),
    ) -> None:
        self._snapshot = PolicyCatalogSnapshot(
            known_critical_flag_names=known_critical_flag_names,
            known_policy_versions=known_policy_versions,
        )

    async def snapshot(self) -> PolicyCatalogSnapshot:
        return self._snapshot


def test_execute_returns_the_opinion_when_flags_and_version_are_known() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion is _FAKE_OPINION


def test_execute_raises_unknown_critical_flag_error_without_calling_the_evaluation_port() -> None:
    evaluation_port = _FakeCreditEvaluationPort()
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=evaluation_port,
        policy_catalog_port=_FakePolicyCatalogPort(known_critical_flag_names=frozenset()),
    )
    snapshot = _healthy_snapshot(critical_flags=frozenset({"NOT_A_REAL_FLAG"}))

    with pytest.raises(UnknownCriticalFlagError) as exc_info:
        asyncio.run(use_case.execute(snapshot))

    assert exc_info.value.flag_names == frozenset({"NOT_A_REAL_FLAG"})
    assert evaluation_port.called is False


def test_execute_raises_policy_version_mismatch_error_for_an_unrecognized_version() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(known_policy_versions=frozenset()),
    )
    snapshot = _healthy_snapshot()

    with pytest.raises(PolicyVersionMismatchError) as exc_info:
        asyncio.run(use_case.execute(snapshot))

    assert exc_info.value.version == "fake-policy-v1"
