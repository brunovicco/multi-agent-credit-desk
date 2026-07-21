"""Adapter that requests a model-routing decision from ``policy-model-router``.

No use case consumes this yet - built and tested standalone first, matching the precedent
``PolicyMcpClient`` established in
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``: wiring this into
``EvaluateCreditApplicationUseCase`` to draft an LLM opinion is deferred to a follow-up
milestone. The request/response shapes are ``credit_desk_contracts.routing``'s
``ModelRouteRequest``/``ModelRouteDecision`` verbatim - verified field-for-field against
``policy-model-router``'s own OpenAPI schema (``docs/DEVELOPMENT.md``'s "Local infra stack"),
not assumed.
"""

import os

import httpx
from pydantic import ValidationError

from credit_desk_contracts.routing import ModelRouteDecision, ModelRouteRequest
from decisao_agent.domain.errors import ModelRoutingUnavailableError

_BASE_URL_ENV_VAR = "DECISAO_AGENT_MODEL_ROUTER_BASE_URL"
_DEFAULT_BASE_URL = "http://localhost:8081"
_DEFAULT_TIMEOUT_SECONDS = 10.0


class ModelRouterClient:
    """Requests a model-routing decision from a real ``policy-model-router`` HTTP server."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the client with the ``policy-model-router`` base URL to call.

        Args:
            base_url: The base URL to call. Defaults to the ``DECISAO_AGENT_MODEL_ROUTER_BASE_URL``
                environment variable, or ``http://localhost:8081`` (the default local compose
                mapping - see ``docs/DEVELOPMENT.md``).
            timeout_seconds: The request timeout.
            transport: An optional ``httpx`` transport override, for tests to inject
                ``httpx.MockTransport`` instead of making a real network call.
        """
        self._base_url = (
            base_url
            if base_url is not None
            else os.environ.get(_BASE_URL_ENV_VAR, _DEFAULT_BASE_URL)
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def route(self, request: ModelRouteRequest) -> ModelRouteDecision:
        """Request a model-routing decision for one workload.

        Args:
            request: The model-routing request to submit.

        Returns:
            The routing decision, including every rejected candidate.

        Raises:
            ModelRoutingUnavailableError: If ``policy-model-router`` cannot be reached within
                the configured timeout, responds with a non-2xx status, or returns a body that
                is not a valid ``ModelRouteDecision``.
        """
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout_seconds, transport=self._transport
        ) as client:
            try:
                response = await client.post("/route", json=request.model_dump(mode="json"))
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelRoutingUnavailableError("failed to reach policy-model-router") from exc

        try:
            return ModelRouteDecision.model_validate_json(response.content)
        except (ValidationError, ValueError) as exc:
            raise ModelRoutingUnavailableError(
                "policy-model-router returned an unexpected response shape"
            ) from exc
