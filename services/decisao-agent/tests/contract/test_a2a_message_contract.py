"""Contract tests: exercise decisao-agent's A2A executor through the real a2a-sdk client/server
machinery, in-process over an ASGI transport (no real socket, no subprocess).

Mirrors the pattern in `services/policy-mcp/tests/contract/test_mcp_tool_contract.py`: use the
SDK's own client against the real request handler and executor, rather than hand-constructing
fake `RequestContext`/`EventQueue` objects that would reimplement SDK internals fragilely. Each
test builds its own app/client pair so pytest-anyio's per-test event loop keeps them isolated -
reusing one client across multiple `send_message` calls in a single test was observed to trigger
noisy (but ultimately non-fatal) OpenTelemetry context-teardown warnings from the SDK's internal
event queue dispatcher.

The executor uses the ``Task``/``TaskUpdater`` pattern (see
``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``), so a ``send_message`` call yields exactly one
``StreamResponse`` (``ClientConfig(streaming=False, ...)``) wrapping the completed ``Task``: the
success body lives in the task's ``credit_opinion`` artifact, a failure body lives in the task's
terminal status message.
"""

import json
from collections.abc import AsyncIterator

import httpx
import pytest
from a2a.client import Client, ClientConfig, create_client
from a2a.helpers.proto_helpers import new_text_message
from a2a.types import CancelTaskRequest, Role, SendMessageRequest, Task, TaskState

from decisao_agent.entrypoints.a2a_server import build_app
from decisao_agent.entrypoints.agent_card import build_agent_card

pytestmark = [pytest.mark.contract, pytest.mark.anyio]

_BASE_URL = "http://testserver"

_HEALTHY_INPUT = json.dumps(
    {
        "annual_revenue": "1000000",
        "total_debt": "300000",
        "monthly_debt_service": "10000",
        "monthly_operating_cash_flow": "25000",
        "bureau_score": "850",
        "years_in_operation": 12,
        "requested_amount": "30000",
        "critical_flags": [],
    }
)


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


@pytest.fixture
async def a2a_client() -> AsyncIterator[Client]:
    agent_card = build_agent_card(_BASE_URL)
    app = build_app(_BASE_URL)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=_BASE_URL
    ) as httpx_client:
        client = await create_client(
            agent_card, client_config=ClientConfig(streaming=False, httpx_client=httpx_client)
        )
        try:
            yield client
        finally:
            await client.close()


async def _send_and_get_task(client: Client, text: str) -> Task:
    message = new_text_message(text, media_type="application/json", role=Role.ROLE_USER)
    request = SendMessageRequest(message=message)
    task: Task | None = None
    async for response in client.send_message(request):
        task = response.task
    assert task is not None
    return task


def _task_body(task: Task) -> str:
    if task.status.state == TaskState.TASK_STATE_COMPLETED:
        parts = task.artifacts[0].parts
    else:
        parts = task.status.message.parts
    return "".join(part.text for part in parts)


async def test_send_message_evaluates_a_healthy_application(a2a_client: Client) -> None:
    task = await _send_and_get_task(a2a_client, _HEALTHY_INPUT)
    body = json.loads(_task_body(task))

    assert task.status.state == TaskState.TASK_STATE_COMPLETED
    assert body["decision"] == "APPROVAL_RECOMMENDED"
    assert body["policy_version"] == "credit-core-demo-policy-v1"


async def test_send_message_preserves_decimal_precision(a2a_client: Client) -> None:
    task = await _send_and_get_task(a2a_client, _HEALTHY_INPUT)
    body = json.loads(_task_body(task))

    assert body["total_score"] == "100.00"
    assert isinstance(body["total_score"], str)


async def test_send_message_reports_a_stable_error_for_malformed_input(
    a2a_client: Client,
) -> None:
    task = await _send_and_get_task(a2a_client, "not valid json")
    body = json.loads(_task_body(task))

    assert task.status.state == TaskState.TASK_STATE_FAILED
    assert body["code"] == "INVALID_INPUT"


async def test_send_message_reports_a_stable_error_for_an_unknown_critical_flag(
    a2a_client: Client,
) -> None:
    payload = json.dumps({**json.loads(_HEALTHY_INPUT), "critical_flags": ["NOT_A_REAL_FLAG"]})

    task = await _send_and_get_task(a2a_client, payload)
    body = json.loads(_task_body(task))

    assert task.status.state == TaskState.TASK_STATE_FAILED
    assert body["code"] == "UNKNOWN_CRITICAL_FLAG"


async def test_cancel_a_completed_task_is_a_no_op(a2a_client: Client) -> None:
    task = await _send_and_get_task(a2a_client, _HEALTHY_INPUT)

    cancelled = await a2a_client.cancel_task(CancelTaskRequest(id=task.id))

    assert cancelled.status.state == TaskState.TASK_STATE_COMPLETED
