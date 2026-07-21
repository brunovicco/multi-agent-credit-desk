"""Behavior tests for ModelRouterClient, isolated from any real network via httpx.MockTransport.

Per .claude/rules/testing.md, unit tests isolate the network: every test constructs its own
``httpx.MockTransport`` handler rather than reaching a real policy-model-router. The real
service is exercised by
``tests/integration/test_model_router_client_live.py``.
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from credit_desk_contracts.enums import DataClassification, ModelGroup, RiskLevel, Workload
from credit_desk_contracts.identifiers import TaskId, WorkflowId
from credit_desk_contracts.routing import ModelRouteRequest
from decisao_agent.adapters.model_router_client import ModelRouterClient
from decisao_agent.domain.errors import ModelRoutingUnavailableError

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


def _request() -> ModelRouteRequest:
    return ModelRouteRequest(
        schema_version="1.0",
        requested_at=datetime.now(UTC),
        workflow_id=WorkflowId("wf-1"),
        task_id=TaskId("task-1"),
        agent_name="decisao-agent",
        workload=Workload.OPINION_DRAFTING,
        risk_level=RiskLevel.MEDIUM,
        data_classification=DataClassification.INTERNAL,
        context_tokens_estimated=2000,
        structured_output_required=False,
        max_latency_ms=30000,
        max_cost_usd=Decimal("0.50"),
    )


def _decision_body() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "routing_decision_id": "decision-1",
        "decided_at": datetime.now(UTC).isoformat(),
        "workflow_id": "wf-1",
        "task_id": "task-1",
        "selected_model_group": "reasoning-strong",
        "reason": "workload 'opinion_drafting' maps to model group 'reasoning-strong'",
        "rejected_candidates": [
            {"model_group": "fast-small", "reason": "not mapped to this workload"},
        ],
    }


async def test_route_returns_the_decision_on_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/route"
        return httpx.Response(200, json=_decision_body())

    client = ModelRouterClient(transport=httpx.MockTransport(handler))

    decision = await client.route(_request())

    assert decision.selected_model_group == ModelGroup.REASONING_STRONG
    assert len(decision.rejected_candidates) == 1


async def test_route_raises_for_a_non_2xx_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "validation error"})

    client = ModelRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ModelRoutingUnavailableError):
        await client.route(_request())


async def test_route_raises_for_a_connection_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = ModelRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ModelRoutingUnavailableError):
        await client.route(_request())


async def test_route_raises_for_a_malformed_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = ModelRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ModelRoutingUnavailableError):
        await client.route(_request())


async def test_route_raises_for_a_non_json_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = ModelRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ModelRoutingUnavailableError):
        await client.route(_request())
