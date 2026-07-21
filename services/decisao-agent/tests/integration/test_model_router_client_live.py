"""Proves ModelRouterClient works end to end against a real policy-model-router container.

Requires `docker compose -f infra/docker-compose.yml up -d policy-model-router` beforehand (see
docs/DEVELOPMENT.md); excluded from the default `uv run pytest` gate via the `not integration`
marker filter. Matches the existing pattern in
`tests/integration/test_otel_collector_langfuse.py`.

No equivalent live test exists for `LiteLLMClient`: completions require a real provider API key
(`GROQ_API_KEY`/`ANTHROPIC_API_KEY`), which is not available in this environment - see
`decisao_agent.adapters.litellm_client`'s module docstring.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from credit_desk_contracts.enums import DataClassification, ModelGroup, RiskLevel, Workload
from credit_desk_contracts.identifiers import TaskId, WorkflowId
from credit_desk_contracts.routing import ModelRouteRequest
from decisao_agent.adapters.model_router_client import ModelRouterClient

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


def _request(workload: Workload, structured_output_required: bool) -> ModelRouteRequest:
    return ModelRouteRequest(
        schema_version="1.0",
        requested_at=datetime.now(UTC),
        workflow_id=WorkflowId("wf-integration-test"),
        task_id=TaskId("task-integration-test"),
        agent_name="decisao-agent",
        workload=workload,
        risk_level=RiskLevel.MEDIUM,
        data_classification=DataClassification.INTERNAL,
        context_tokens_estimated=2000,
        structured_output_required=structured_output_required,
        max_latency_ms=30000,
        max_cost_usd=Decimal("0.50"),
    )


async def test_route_selects_reasoning_strong_for_opinion_drafting() -> None:
    client = ModelRouterClient()

    decision = await client.route(
        _request(Workload.OPINION_DRAFTING, structured_output_required=False)
    )

    assert decision.selected_model_group == ModelGroup.REASONING_STRONG
    assert len(decision.rejected_candidates) == 3


async def test_route_selects_fast_structured_output_for_json_repair() -> None:
    client = ModelRouterClient()

    decision = await client.route(_request(Workload.JSON_REPAIR, structured_output_required=True))

    assert decision.selected_model_group == ModelGroup.FAST_STRUCTURED_OUTPUT
