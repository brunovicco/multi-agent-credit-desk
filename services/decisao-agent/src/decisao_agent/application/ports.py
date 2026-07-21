"""Consumer-defined ports for decisao-agent's evaluation application layer.

Defined on the consumer side (``application``), near the use case that needs them, per
``.claude/rules/architecture.md``. ``CreditEvaluationPort`` is the seam that keeps this layer
independent of ``credit_core``; ``PolicyCatalogPort`` is the seam that keeps it independent of
how policy-mcp is actually reached (MCP over stdio today). ``ModelRoutingPort`` and
``ChatCompletionPort`` are the seams for the optional, best-effort LLM-drafted opinion narrative
- see ``docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md``.

``ChatMessage``/``ChatCompletionResult`` live here, not in ``adapters.litellm_client`` where they
were first defined, now that a real consumer (``ChatCompletionPort``) needs to reference them -
they are decisao-agent's own generic chat-completion vocabulary, not a shared workspace contract
like ``credit_desk_contracts.routing.ModelRouteRequest``/``ModelRouteDecision``, which
``ModelRoutingPort`` uses verbatim.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from credit_desk_contracts.routing import ModelRouteDecision, ModelRouteRequest
from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot


class CreditEvaluationPort(Protocol):
    """Synchronous access to the deterministic credit evaluation core.

    The only implementation shipped today, ``CreditCoreEvaluationAdapter``, calls
    ``credit_core.evaluation.evaluate_credit_application`` directly. It is synchronous because
    ``credit_core`` is a pure, in-process computation with no I/O.
    """

    def evaluate(self, snapshot: ApplicationSnapshot) -> CreditOpinion:
        """Evaluate one application snapshot and return the resulting credit opinion.

        Args:
            snapshot: The applicant financial and bureau snapshot to evaluate.

        Returns:
            The structured, reproducible evaluation outcome.

        Raises:
            InvalidApplicationSnapshotError: If ``snapshot`` violates an input invariant.
        """
        ...


@dataclass(frozen=True, slots=True)
class PolicyCatalogSnapshot:
    """The subset of policy-mcp's catalog the evaluation use case cross-checks against.

    Attributes:
        known_critical_flag_names: Every critical flag name policy-mcp's catalog recognizes.
        known_policy_versions: Every policy version policy-mcp's catalog recognizes.
    """

    known_critical_flag_names: frozenset[str]
    known_policy_versions: frozenset[str]


class PolicyCatalogPort(Protocol):
    """Read-only access to policy-mcp's catalog, for cross-checking an evaluation.

    The only implementation shipped today, ``PolicyMcpClient``, speaks the MCP protocol to a
    ``policy-mcp`` server process over stdio.
    """

    async def snapshot(self) -> PolicyCatalogSnapshot:
        """Fetch the current known critical flag names and policy versions.

        Returns:
            A ``PolicyCatalogSnapshot`` covering policy-mcp's current catalog.
        """
        ...


class ModelRoutingPort(Protocol):
    """Read-only access to a model-routing decision, for drafting the opinion narrative.

    The only implementation shipped today, ``ModelRouterClient``, calls
    ``policy-model-router``'s ``POST /route`` over HTTP.
    """

    async def route(self, request: ModelRouteRequest) -> ModelRouteDecision:
        """Request a model-routing decision for one workload.

        Args:
            request: The model-routing request to submit.

        Returns:
            The routing decision, including every rejected candidate.

        Raises:
            ModelRoutingUnavailableError: If a decision cannot be obtained.
        """
        ...


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One message in a chat completion request.

    Attributes:
        role: The message role (``"system"``, ``"user"``, or ``"assistant"``).
        content: The message text.
    """

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatCompletionResult:
    """The outcome of one chat completion request.

    Attributes:
        model: The model group the completion was served from.
        content: The completion text.
    """

    model: str
    content: str


class ChatCompletionPort(Protocol):
    """Access to a chat completion, for drafting the opinion narrative.

    The only implementation shipped today, ``LiteLLMClient``, calls LiteLLM's
    OpenAI-compatible ``POST /chat/completions`` over HTTP.
    """

    async def complete(self, model: str, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        """Request one chat completion.

        Args:
            model: The model group to complete with (e.g. ``"reasoning-strong"``).
            messages: The conversation to complete, in order.

        Returns:
            The completion result.

        Raises:
            ChatCompletionUnavailableError: If a completion cannot be obtained.
        """
        ...
