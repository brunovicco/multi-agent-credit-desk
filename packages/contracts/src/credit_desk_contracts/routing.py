"""Versioned model-routing contracts.

Implements the decision-record format from
``docs/adr/0005-policy-based-deterministic-router-mvp.md``.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from credit_desk_contracts._base import StrictContract, UtcDatetime
from credit_desk_contracts.enums import DataClassification, ModelGroup, RiskLevel, Workload
from credit_desk_contracts.identifiers import RoutingDecisionId, TaskId, WorkflowId


class ModelRouteRequest(StrictContract):
    """A model-routing request submitted by an agent before an LLM call."""

    schema_version: Literal["1.0"]
    requested_at: UtcDatetime
    workflow_id: WorkflowId
    task_id: TaskId
    agent_name: Annotated[str, StringConstraints(min_length=1)]
    workload: Workload
    risk_level: RiskLevel
    data_classification: DataClassification
    context_tokens_estimated: Annotated[int, Field(ge=0)]
    structured_output_required: bool
    max_latency_ms: Annotated[int, Field(gt=0)]
    max_cost_usd: Annotated[Decimal, Field(gt=0)]


class RejectedCandidate(StrictContract):
    """One model group excluded from a routing decision, with the eliminating reason."""

    model_group: ModelGroup
    reason: Annotated[str, StringConstraints(min_length=1)]


class ModelRouteDecision(StrictContract):
    """The outcome of a model-routing decision, including every rejected candidate."""

    schema_version: Literal["1.0"]
    routing_decision_id: RoutingDecisionId
    decided_at: UtcDatetime
    workflow_id: WorkflowId
    task_id: TaskId
    selected_model_group: ModelGroup
    reason: Annotated[str, StringConstraints(min_length=1)]
    rejected_candidates: tuple[RejectedCandidate, ...]
