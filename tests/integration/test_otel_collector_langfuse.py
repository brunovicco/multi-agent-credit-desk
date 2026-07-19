"""Proves the local OTel Collector + Langfuse stack (infra/docker-compose.yml) really ingests spans.

Requires `docker compose -f infra/docker-compose.yml up -d` beforehand (see docs/DEVELOPMENT.md);
excluded from the default `uv run pytest` gate via the `not integration` marker filter.
"""

import pytest
from a2a_otel_kit import Observability, ObservabilitySettings


@pytest.mark.integration
def test_span_export_succeeds_against_local_collector() -> None:
    settings = ObservabilitySettings(
        service_name="multi-agent-credit-desk-otel-stack-check",
        service_version="0.1.0",
        environment="test",
        enabled=True,
        otlp_endpoint="http://localhost:4318/v1/traces",
    )

    observability = Observability.configure(settings)
    with observability.start_span("infra.otel_stack_check", attributes={"operation": "smoke_test"}):
        observability.emit_event(
            "infra.otel_stack_check.completed", "success", operation="smoke_test"
        )

    try:
        assert observability.flush() is True
    finally:
        observability.shutdown()
