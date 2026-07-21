"""Behavior tests for EvaluateCreditApplicationUseCase against fake ports.

Per .claude/rules/testing.md, unit tests isolate external dependencies: this suite never
imports CreditCoreEvaluationAdapter or PolicyMcpClient, only hand-written fakes that implement
the two ports structurally.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from credit_desk_contracts.enums import ModelGroup
from credit_desk_contracts.identifiers import RoutingDecisionId, TaskId, WorkflowId
from credit_desk_contracts.routing import ModelRouteDecision, ModelRouteRequest
from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.application.ports import ChatCompletionResult, ChatMessage, PolicyCatalogSnapshot
from decisao_agent.domain.errors import (
    ChatCompletionUnavailableError,
    ModelRoutingUnavailableError,
    PolicyVersionMismatchError,
    UnknownCriticalFlagError,
)
from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot

_UTC_NOW = datetime.now(UTC)

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


_FAKE_ROUTE_DECISION = ModelRouteDecision(
    schema_version="1.0",
    routing_decision_id=RoutingDecisionId("decision-1"),
    decided_at=_UTC_NOW,
    workflow_id=WorkflowId("wf-1"),
    task_id=TaskId("task-1"),
    selected_model_group=ModelGroup.REASONING_STRONG,
    reason="workload maps to reasoning-strong",
    rejected_candidates=(),
)


class _FakeModelRoutingPort:
    """A hand-written test double implementing ModelRoutingPort structurally."""

    def __init__(self, decision: ModelRouteDecision = _FAKE_ROUTE_DECISION) -> None:
        self._decision = decision
        self.last_request: ModelRouteRequest | None = None

    async def route(self, request: ModelRouteRequest) -> ModelRouteDecision:
        self.last_request = request
        return self._decision


class _FailingModelRoutingPort:
    """A hand-written test double whose route() always raises."""

    async def route(self, request: ModelRouteRequest) -> ModelRouteDecision:
        raise ModelRoutingUnavailableError("simulated failure")


class _FakeChatCompletionPort:
    """A hand-written test double implementing ChatCompletionPort structurally."""

    def __init__(self, content: str = "Parecer favorável ao crédito.") -> None:
        self._content = content
        self.last_model: str | None = None

    async def complete(self, model: str, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        self.last_model = model
        return ChatCompletionResult(model=model, content=self._content)


class _FailingChatCompletionPort:
    """A hand-written test double whose complete() always raises."""

    async def complete(self, model: str, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        raise ChatCompletionUnavailableError("simulated failure")


def test_execute_returns_the_opinion_when_flags_and_version_are_known() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion == _FAKE_OPINION
    assert opinion.narrative is None


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


def test_execute_leaves_narrative_none_when_no_drafting_ports_are_wired() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion.narrative is None


def test_execute_leaves_narrative_none_when_only_one_drafting_port_is_wired() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=_FakeModelRoutingPort(),
        chat_completion_port=None,
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion.narrative is None


def test_execute_attaches_the_drafted_narrative_when_both_ports_succeed() -> None:
    model_routing_port = _FakeModelRoutingPort()
    chat_completion_port = _FakeChatCompletionPort(content="Parecer favorável.")
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=model_routing_port,
        chat_completion_port=chat_completion_port,
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion.narrative == "Parecer favorável."
    assert chat_completion_port.last_model == ModelGroup.REASONING_STRONG.value
    assert model_routing_port.last_request is not None
    assert model_routing_port.last_request.workload.value == "opinion_drafting"
    assert model_routing_port.last_request.data_classification.value == "confidential"


def test_execute_generates_fresh_correlation_ids_when_none_are_given() -> None:
    model_routing_port = _FakeModelRoutingPort()
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=model_routing_port,
        chat_completion_port=_FakeChatCompletionPort(),
    )
    snapshot = _healthy_snapshot()

    asyncio.run(use_case.execute(snapshot))

    assert model_routing_port.last_request is not None
    assert len(model_routing_port.last_request.workflow_id) > 0
    assert len(model_routing_port.last_request.task_id) > 0


def test_execute_forwards_the_callers_correlation_ids_when_given() -> None:
    model_routing_port = _FakeModelRoutingPort()
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=model_routing_port,
        chat_completion_port=_FakeChatCompletionPort(),
    )
    snapshot = _healthy_snapshot()

    asyncio.run(use_case.execute(snapshot, workflow_id="real-workflow-1", task_id="real-task-1"))

    assert model_routing_port.last_request is not None
    assert model_routing_port.last_request.workflow_id == "real-workflow-1"
    assert model_routing_port.last_request.task_id == "real-task-1"


def test_execute_leaves_narrative_none_when_routing_fails() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=_FailingModelRoutingPort(),
        chat_completion_port=_FakeChatCompletionPort(),
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion.narrative is None
    assert opinion.decision == "APPROVAL_RECOMMENDED"


def test_execute_leaves_narrative_none_when_completion_fails() -> None:
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=_FakeCreditEvaluationPort(),
        policy_catalog_port=_FakePolicyCatalogPort(
            known_policy_versions=frozenset({"fake-policy-v1"})
        ),
        model_routing_port=_FakeModelRoutingPort(),
        chat_completion_port=_FailingChatCompletionPort(),
    )
    snapshot = _healthy_snapshot()

    opinion = asyncio.run(use_case.execute(snapshot))

    assert opinion.narrative is None
    assert opinion.decision == "APPROVAL_RECOMMENDED"
