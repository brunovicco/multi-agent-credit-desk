"""decisao-agent's evaluation use case: score an application and, best-effort, draft its opinion.

Composes the synchronous deterministic evaluation (``CreditEvaluationPort``) and an asynchronous
cross-check against policy-mcp's catalog (``PolicyCatalogPort``), so credit_core's decision can
never be trusted against a critical flag or policy version policy-mcp does not itself recognize.
Optionally composes ``ModelRoutingPort``/``ChatCompletionPort`` to draft a narrative parecer via
LLM - strictly best-effort: drafting failure never blocks, delays, or alters the deterministic
``decision`` above, per ``docs/adr/0008-deterministic-core-without-llm.md`` and
``docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md``. This module never
imports ``credit_core`` or a transport/serialization library.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError

from credit_desk_contracts.enums import DataClassification, RiskLevel, Workload
from credit_desk_contracts.identifiers import TaskId, WorkflowId
from credit_desk_contracts.routing import ModelRouteRequest
from decisao_agent.application.ports import (
    ChatCompletionPort,
    ChatMessage,
    CreditEvaluationPort,
    ModelRoutingPort,
    PolicyCatalogPort,
)
from decisao_agent.domain.errors import (
    ChatCompletionUnavailableError,
    ModelRoutingUnavailableError,
    PolicyVersionMismatchError,
    UnknownCriticalFlagError,
)
from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot

_AGENT_NAME = "decisao-agent"
_MAX_LATENCY_MS = 30_000
# opinion_drafting always maps to reasoning-strong (policy-model-router's own workload table),
# its most expensive group - verified live against a real policy-model-router container that
# $0.15 (the blueprint's generic example ceiling, for a different, cheaper workload) makes
# every routing request fail with "no_viable_model_group": reasoning-strong's estimated cost
# already exceeds it before any real completion is attempted.
_MAX_COST_USD = Decimal("0.50")
_CHARS_PER_TOKEN_ESTIMATE = 4

_RISK_LEVEL_BY_DECISION: dict[str, RiskLevel] = {
    "APPROVAL_RECOMMENDED": RiskLevel.LOW,
    "CONDITIONAL_APPROVAL": RiskLevel.MEDIUM,
    "COMMITTEE_REFERRAL": RiskLevel.HIGH,
    "DECLINE": RiskLevel.CRITICAL,
    "BLOCKED": RiskLevel.CRITICAL,
}
_DEFAULT_RISK_LEVEL = RiskLevel.HIGH


class EvaluateCreditApplicationUseCase:
    """Evaluates a credit application snapshot, cross-checked against policy-mcp's catalog."""

    def __init__(
        self,
        evaluation_port: CreditEvaluationPort,
        policy_catalog_port: PolicyCatalogPort,
        model_routing_port: ModelRoutingPort | None = None,
        chat_completion_port: ChatCompletionPort | None = None,
    ) -> None:
        """Initialize the use case with its required ports and optional narrative-drafting ports.

        Args:
            evaluation_port: The deterministic credit evaluation port to use.
            policy_catalog_port: The policy-mcp catalog port to cross-check against.
            model_routing_port: The policy-model-router port to use for narrative drafting.
                ``None`` (the default) skips narrative drafting entirely - every returned
                ``CreditOpinion.narrative`` is ``None``.
            chat_completion_port: The chat-completion port to use for narrative drafting.
                ``None`` (the default) skips narrative drafting entirely, same as
                ``model_routing_port=None``. Both must be provided to attempt drafting.
        """
        self._evaluation_port = evaluation_port
        self._policy_catalog_port = policy_catalog_port
        self._model_routing_port = model_routing_port
        self._chat_completion_port = chat_completion_port

    async def execute(
        self,
        snapshot: ApplicationSnapshot,
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> CreditOpinion:
        """Evaluate one application snapshot, validated against policy-mcp's catalog.

        Args:
            snapshot: The applicant financial and bureau snapshot to evaluate.
            workflow_id: The caller's workflow correlation ID, if one exists (e.g. the A2A
                server's ``RequestContext.context_id``), used for the narrative-drafting
                routing request. ``None`` (the default) generates a fresh one - correct for
                callers with no real workflow context yet, such as the batch CLI.
            task_id: The caller's task correlation ID, if one exists (e.g. the A2A server's
                ``RequestContext.task_id``). Same default behavior as ``workflow_id``.

        Returns:
            The structured, reproducible evaluation outcome. ``narrative`` is populated only
            when both narrative-drafting ports were provided and drafting succeeded; otherwise
            it is ``None`` - narrative drafting never raises and never affects any other field.

        Raises:
            UnknownCriticalFlagError: If ``snapshot.critical_flags`` names a flag policy-mcp
                does not recognize.
            InvalidApplicationSnapshotError: If ``snapshot`` violates an input invariant.
            PolicyVersionMismatchError: If credit_core applies a policy version policy-mcp does
                not recognize.
        """
        catalog = await self._policy_catalog_port.snapshot()

        unknown_flag_names = snapshot.critical_flags - catalog.known_critical_flag_names
        if unknown_flag_names:
            raise UnknownCriticalFlagError(unknown_flag_names)

        opinion = self._evaluation_port.evaluate(snapshot)

        if opinion.policy_version not in catalog.known_policy_versions:
            raise PolicyVersionMismatchError(opinion.policy_version)

        narrative = await self._draft_narrative(opinion, workflow_id, task_id)
        return replace(opinion, narrative=narrative)

    async def _draft_narrative(
        self, opinion: CreditOpinion, workflow_id: str | None, task_id: str | None
    ) -> str | None:
        """Best-effort draft an LLM narrative parecer for an already-computed opinion.

        Args:
            opinion: The deterministic evaluation outcome to describe in prose.
            workflow_id: The caller's workflow correlation ID, or ``None`` to generate one.
            task_id: The caller's task correlation ID, or ``None`` to generate one.

        Returns:
            The drafted narrative, or ``None`` if drafting was not requested (either port is
            unset) or failed for any reason - including building the routing request itself.
            Never raises: any failure on this path is caught and treated as "no narrative
            available," never as an evaluation failure.
        """
        if self._model_routing_port is None or self._chat_completion_port is None:
            return None

        messages = _build_opinion_messages(opinion)
        try:
            request = ModelRouteRequest(
                schema_version="1.0",
                requested_at=datetime.now(UTC),
                workflow_id=WorkflowId(workflow_id or str(uuid4())),
                task_id=TaskId(task_id or str(uuid4())),
                agent_name=_AGENT_NAME,
                workload=Workload.OPINION_DRAFTING,
                risk_level=_RISK_LEVEL_BY_DECISION.get(opinion.decision, _DEFAULT_RISK_LEVEL),
                data_classification=DataClassification.CONFIDENTIAL,
                context_tokens_estimated=_estimate_tokens(messages),
                structured_output_required=False,
                max_latency_ms=_MAX_LATENCY_MS,
                max_cost_usd=_MAX_COST_USD,
            )
            decision = await self._model_routing_port.route(request)
            result = await self._chat_completion_port.complete(
                decision.selected_model_group.value, messages
            )
        except (ModelRoutingUnavailableError, ChatCompletionUnavailableError, ValidationError):
            return None
        return result.content


def _build_opinion_messages(opinion: CreditOpinion) -> tuple[ChatMessage, ...]:
    """Build the prompt describing an already-computed deterministic opinion.

    The LLM drafts prose describing ``opinion``; it never re-derives or overrides ``decision``,
    ``total_score``, or any other deterministic field - those are given as fixed inputs.

    Args:
        opinion: The deterministic evaluation outcome to describe.

    Returns:
        The system and user messages to submit for completion.
    """
    system = ChatMessage(
        role="system",
        content=(
            "You are a credit analyst assistant. Draft a short, factual parecer (credit "
            "opinion narrative) in Portuguese summarizing the deterministic evaluation result "
            "below. Do not invent facts, do not change the decision, and do not cite any "
            "figure other than the ones provided."
        ),
    )
    component_lines = "\n".join(
        f"- {component.component}: metric={component.metric_value}, "
        f"score={component.raw_score}, weight={component.weight}"
        for component in opinion.component_scores
    )
    user = ChatMessage(
        role="user",
        content=(
            f"Policy version: {opinion.policy_version}\n"
            f"Total score: {opinion.total_score}\n"
            f"Decision: {opinion.decision}\n"
            f"Approval authority: {opinion.approval_authority}\n"
            f"Reason codes: {', '.join(opinion.reason_codes) or 'none'}\n"
            f"Blocking reasons: {', '.join(opinion.blocking_reasons) or 'none'}\n"
            f"Component scores:\n{component_lines or '- none'}"
        ),
    )
    return (system, user)


def _estimate_tokens(messages: Sequence[ChatMessage]) -> int:
    """Roughly estimate the token count of a set of messages, for the routing request.

    Args:
        messages: The messages to estimate.

    Returns:
        A conservative estimate: total character count divided by
        ``_CHARS_PER_TOKEN_ESTIMATE``.
    """
    total_chars = sum(len(message.content) for message in messages)
    return total_chars // _CHARS_PER_TOKEN_ESTIMATE
