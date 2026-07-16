"""Versioned structured-event envelope shared across agents and infrastructure services."""

from typing import Annotated, Literal

from pydantic import StringConstraints

from credit_desk_contracts._base import StrictContract, UtcDatetime
from credit_desk_contracts.enums import DataClassification, EventOutcome
from credit_desk_contracts.identifiers import AgentExecutionId, ContextId, TaskId, WorkflowId

EventName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")]


class EventEnvelope(StrictContract):
    """One structured event in the credit review audit trail.

    Telemetry contracts intentionally exclude prompts, model responses, customer payloads,
    credentials, and free-form metadata; a dedicated event only ever carries the fixed fields
    declared here. Content that must be inspected later belongs in the artifact store and is
    referenced from telemetry through an :class:`~credit_desk_contracts.artifacts.ArtifactEnvelope`
    identifier, not embedded in the event itself.
    """

    schema_version: Literal["1.0"]
    event_name: EventName
    event_outcome: EventOutcome
    occurred_at: UtcDatetime
    data_classification: DataClassification
    workflow_id: WorkflowId
    context_id: ContextId | None = None
    task_id: TaskId | None = None
    agent_execution_id: AgentExecutionId | None = None
