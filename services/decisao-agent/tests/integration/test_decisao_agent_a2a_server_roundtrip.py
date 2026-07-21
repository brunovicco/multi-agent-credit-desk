"""Proves `python -m decisao_agent.entrypoints.a2a_server` works end to end as a real subprocess
over real TCP loopback, including its own real `python -m policy_mcp` subprocess call.

Spawns the packaged A2A server entrypoint (not an in-process fake or ASGI transport), waits for
the well-known Agent Card endpoint to answer, then drives one real `send_message` call over HTTP
with the real `a2a-sdk` client - proving process startup, host/port binding, and the full
executor chain (credit_core in-process, policy-mcp as a nested subprocess) work together end to
end. Matches the existing pattern in
`services/decisao-agent/tests/integration/test_decisao_agent_cli_stdio_roundtrip.py`.
"""

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest
from a2a.client import ClientConfig, create_client
from a2a.helpers.proto_helpers import new_text_message
from a2a.types import Role, SendMessageRequest, TaskState

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

_HOST = "127.0.0.1"
_PORT = "8199"
_BASE_URL = f"http://{_HOST}:{_PORT}"
_AGENT_CARD_PATH = "/.well-known/agent-card.json"
_READY_TIMEOUT_SECONDS = 15.0
_REQUEST_TIMEOUT_SECONDS = 30.0

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
def a2a_server_process() -> Iterator[subprocess.Popen[bytes]]:
    process = subprocess.Popen(
        [sys.executable, "-m", "decisao_agent.entrypoints.a2a_server"],
        env={**os.environ, "DECISAO_AGENT_A2A_HOST": _HOST, "DECISAO_AGENT_A2A_PORT": _PORT},
    )
    try:
        _wait_until_ready(process)
        yield process
    finally:
        process.terminate()
        process.wait(timeout=_READY_TIMEOUT_SECONDS)


def _wait_until_ready(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("a2a_server process exited before becoming ready")
        try:
            response = httpx.get(f"{_BASE_URL}{_AGENT_CARD_PATH}", timeout=1.0)
        except httpx.TransportError:
            time.sleep(0.2)
            continue
        if response.status_code == 200:
            return
        time.sleep(0.2)
    raise TimeoutError("a2a_server did not become ready in time")


async def _send(text: str) -> str:
    async with httpx.AsyncClient(base_url=_BASE_URL) as httpx_client:
        client = await create_client(
            _BASE_URL,
            client_config=ClientConfig(streaming=False, httpx_client=httpx_client),
            relative_card_path=_AGENT_CARD_PATH,
        )
        try:
            message = new_text_message(text, media_type="application/json", role=Role.ROLE_USER)
            request = SendMessageRequest(message=message)
            task = None
            async for response in client.send_message(request):
                task = response.task
            assert task is not None
            assert task.status.state == TaskState.TASK_STATE_COMPLETED
            return "".join(part.text for part in task.artifacts[0].parts)
        finally:
            await client.close()


async def test_a2a_server_evaluates_a_healthy_application_end_to_end(
    a2a_server_process: subprocess.Popen[bytes],
) -> None:
    body = json.loads(await _send(_HEALTHY_INPUT))

    assert body["decision"] == "APPROVAL_RECOMMENDED"
    assert body["policy_version"] == "credit-core-demo-policy-v1"
