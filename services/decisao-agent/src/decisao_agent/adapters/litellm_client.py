"""Adapter that requests a chat completion from LiteLLM's OpenAI-compatible proxy.

No use case consumes this yet - built and tested standalone first, the same way
``ModelRouterClient`` and ``PolicyMcpClient`` were. ``LITELLM_MASTER_KEY`` authenticates to the
local proxy per ``infra/docker-compose.yml``; without a real provider key
(``GROQ_API_KEY``/``ANTHROPIC_API_KEY``) configured on the proxy itself, completions fail even
though this client and the proxy are both reachable - see ``docs/DEVELOPMENT.md``'s "Local infra
stack" section. No real provider credentials are available in this environment, so this adapter
is verified against a real reachable LiteLLM proxy only up to the point completions would
require a paid provider key; ``tests/unit`` covers the rest against a fake transport.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from decisao_agent.domain.errors import ChatCompletionUnavailableError

_BASE_URL_ENV_VAR = "DECISAO_AGENT_LITELLM_BASE_URL"
_MASTER_KEY_ENV_VAR = "LITELLM_MASTER_KEY"
_DEFAULT_BASE_URL = "http://localhost:4000"
_DEFAULT_TIMEOUT_SECONDS = 60.0


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


class LiteLLMClient:
    """Requests a chat completion from a real LiteLLM HTTP proxy."""

    def __init__(
        self,
        base_url: str | None = None,
        master_key: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the client with the LiteLLM proxy to call.

        Args:
            base_url: The base URL to call. Defaults to the ``DECISAO_AGENT_LITELLM_BASE_URL``
                environment variable, or ``http://localhost:4000`` (the default local compose
                mapping - see ``docs/DEVELOPMENT.md``).
            master_key: The bearer token to authenticate with. Defaults to the
                ``LITELLM_MASTER_KEY`` environment variable.
            timeout_seconds: The request timeout. Defaults to 60s, matching the longest provider
                timeout configured in ``infra/litellm/config.yaml``.
            transport: An optional ``httpx`` transport override, for tests to inject
                ``httpx.MockTransport`` instead of making a real network call.
        """
        self._base_url = (
            base_url
            if base_url is not None
            else os.environ.get(_BASE_URL_ENV_VAR, _DEFAULT_BASE_URL)
        )
        self._master_key = (
            master_key if master_key is not None else os.environ.get(_MASTER_KEY_ENV_VAR)
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def complete(self, model: str, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        """Request one chat completion.

        Args:
            model: The model group to complete with (e.g. ``"reasoning-strong"``), matching
                ``credit_desk_contracts.enums.ModelGroup``.
            messages: The conversation to complete, in order.

        Returns:
            The completion result.

        Raises:
            ChatCompletionUnavailableError: If LiteLLM cannot be reached within the configured
                timeout, responds with a non-2xx status, or returns a body that does not carry a
                completion message.
        """
        headers = {"Authorization": f"Bearer {self._master_key}"} if self._master_key else {}
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
        }

        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout_seconds, transport=self._transport
        ) as client:
            try:
                response = await client.post("/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ChatCompletionUnavailableError("failed to reach LiteLLM") from exc

        try:
            body: Any = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ChatCompletionUnavailableError(
                "LiteLLM returned an unexpected response shape"
            ) from exc
        if not isinstance(content, str):
            raise ChatCompletionUnavailableError("LiteLLM returned an unexpected response shape")

        return ChatCompletionResult(model=model, content=content)
