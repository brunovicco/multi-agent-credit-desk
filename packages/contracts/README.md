# credit-desk-contracts

Shared, versioned Pydantic v2 schemas for the Multi-Agent Credit Desk workspace: artifact
envelopes, structured events, and model-routing decisions. This package has no consumers yet
(agents, orchestrator, and the model router are not implemented in this repository) — it defines
the contracts they will exchange. Agent-specific artifact payload schemas are deferred until their
producer and consumer boundaries are implemented.

## Design rules

- Every contract rejects unknown fields (`model_config = ConfigDict(extra="forbid")`) and is
  immutable after construction (`frozen=True`).
- Every top-level contract requires an explicit `schema_version` (currently pinned to the
  `Literal["1.0"]` for each contract) — there is no default, so omitting it is a validation error.
- Every timestamp field must be timezone-aware and expressed in UTC; naive or non-UTC datetimes are
  rejected.
- `EventEnvelope` (the telemetry/audit-trail contract) carries only fixed, named fields. It has no
  free-form metadata field, and never carries prompts, model responses, customer payloads, or
  credentials — see `docs/adr/0007-telemetry-without-sensitive-content.md`.
- `ArtifactEnvelope` references stored content through a `content_hash` and `storage_uri`; it does
  not carry the artifact payload itself.
- All identifiers (`WorkflowId`, `TaskId`, etc.) are distinct, non-empty string types. At runtime,
  a plain `str` is validated and accepted directly; under `mypy --strict`, a call site that builds
  one of these fields from a plain `str` variable should wrap it explicitly, e.g.
  `WorkflowId("wf-123")`, so a `TaskId` cannot be passed by mistake where a `WorkflowId` is
  expected.
- Imports inside the package use absolute paths. Relative imports such as
  `from .routing import ModelRouteRequest` are not allowed.

## Public API

| Symbol | Kind | Purpose |
|---|---|---|
| `ArtifactEnvelope` | contract | Reference metadata for one artifact in the evidence bundle |
| `EventEnvelope` | contract | One structured event in the audit trail |
| `ModelRouteRequest` | contract | A model-routing request submitted before an LLM call |
| `ModelRouteDecision` | contract | The outcome of a routing decision, with every rejected candidate |
| `RejectedCandidate` | contract | One model group excluded from a routing decision, with its reason |
| `DataClassification` | enum | LGPD/LC 105-oriented sensitivity tier |
| `EventOutcome` | enum | Terminal outcome of a structured event |
| `ArtifactType` | enum | Kind of artifact produced during a workflow |
| `RiskLevel` | enum | Assessed risk level of an application or routing request |
| `Workload` | enum | LLM workload kind, keyed to a model group by the router |
| `ModelGroup` | enum | Model group selectable by the router, independent of provider |
| `WorkflowId`, `ContextId`, `TaskId`, `AgentExecutionId`, `RoutingDecisionId`, `ArtifactId` | identifier | Non-empty, distinct string identifiers correlating a workflow across boundaries |

## Examples

```python
from datetime import UTC, datetime
from decimal import Decimal

from credit_desk_contracts import (
    DataClassification,
    ModelGroup,
    ModelRouteDecision,
    ModelRouteRequest,
    RejectedCandidate,
    RiskLevel,
    Workload,
)

request = ModelRouteRequest(
    schema_version="1.0",
    requested_at=datetime.now(UTC),
    workflow_id="wf-2026-000123",
    task_id="task-financeiro-1",
    agent_name="financeiro-agent",
    workload=Workload.CASHFLOW_ANALYSIS,
    risk_level=RiskLevel.HIGH,
    data_classification=DataClassification.CONFIDENTIAL,
    context_tokens_estimated=24_000,
    structured_output_required=True,
    max_latency_ms=30_000,
    max_cost_usd=Decimal("0.15"),
)

decision = ModelRouteDecision(
    schema_version="1.0",
    routing_decision_id="rd-2026-000123",
    decided_at=datetime.now(UTC),
    workflow_id=request.workflow_id,
    task_id=request.task_id,
    selected_model_group=ModelGroup.REASONING_STRONG,
    reason="workload table: cashflow_analysis -> reasoning-strong",
    rejected_candidates=(
        RejectedCandidate(
            model_group=ModelGroup.FAST_SMALL,
            reason="workload requires strong reasoning",
        ),
    ),
)
```

```python
from datetime import UTC, datetime

from credit_desk_contracts import ArtifactEnvelope, ArtifactType, DataClassification

artifact = ArtifactEnvelope(
    schema_version="1.0",
    artifact_id="artifact-financeiro-1",
    artifact_type=ArtifactType.FINANCIAL_ANALYSIS,
    workflow_id="wf-2026-000123",
    data_classification=DataClassification.CONFIDENTIAL,
    produced_at=datetime.now(UTC),
    content_hash="sha256:" + "a" * 64,
    size_bytes=2048,
    storage_uri="s3://evidence-bundle/wf-2026-000123/financial-analysis.json",
)
```

Every contract also generates a JSON Schema via `Model.model_json_schema()`, for validating
payloads exchanged with other services (e.g. artifacts, A2A messages) outside this package.
