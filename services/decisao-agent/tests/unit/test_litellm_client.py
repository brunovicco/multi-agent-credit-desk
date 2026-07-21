"""Behavior tests for LiteLLMClient, isolated from any real network via httpx.MockTransport.

Per .claude/rules/testing.md, unit tests isolate the network: every test constructs its own
``httpx.MockTransport`` handler rather than reaching a real LiteLLM proxy. No real provider API
keys are available in this environment, so a genuine end-to-end completion cannot be verified
here - only the client's own request/response handling.
"""

import json

import httpx
import pytest

from decisao_agent.adapters.litellm_client import ChatMessage, LiteLLMClient
from decisao_agent.domain.errors import ChatCompletionUnavailableError

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are a credit analyst."),
        ChatMessage(role="user", content="Draft a short opinion."),
    ]


async def test_complete_returns_the_completion_content_on_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "reasoning-strong"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Approved, healthy applicant."}}]},
        )

    client = LiteLLMClient(master_key="test-key", transport=httpx.MockTransport(handler))

    result = await client.complete("reasoning-strong", _messages())

    assert result.model == "reasoning-strong"
    assert result.content == "Approved, healthy applicant."


async def test_complete_sends_the_bearer_token_when_configured() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = LiteLLMClient(master_key="test-key", transport=httpx.MockTransport(handler))

    await client.complete("fast-small", _messages())


async def test_complete_omits_the_authorization_header_when_no_key_is_configured() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = LiteLLMClient(master_key=None, transport=httpx.MockTransport(handler))

    await client.complete("fast-small", _messages())


async def test_complete_raises_for_a_non_2xx_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = LiteLLMClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ChatCompletionUnavailableError):
        await client.complete("reasoning-strong", _messages())


async def test_complete_raises_for_a_connection_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = LiteLLMClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ChatCompletionUnavailableError):
        await client.complete("reasoning-strong", _messages())


async def test_complete_raises_for_a_missing_choices_field() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = LiteLLMClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ChatCompletionUnavailableError):
        await client.complete("reasoning-strong", _messages())


async def test_complete_raises_for_a_non_string_content() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": 123}}]})

    client = LiteLLMClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ChatCompletionUnavailableError):
        await client.complete("reasoning-strong", _messages())


async def test_complete_raises_for_a_non_json_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = LiteLLMClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ChatCompletionUnavailableError):
        await client.complete("reasoning-strong", _messages())
