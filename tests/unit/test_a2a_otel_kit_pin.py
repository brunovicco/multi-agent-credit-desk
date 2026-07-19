"""Proves the pinned ``a2a-otel-kit`` dependency installs and its public API works.

No `services/*` package consumes this library yet (see ADR-0003, docs/ARCHITECTURE.md); this test
plays the same role as the `credit_core`/`credit_desk_contracts` import check in the workspace
validation `Dockerfile` CMD, but for this pinned dependency. `enabled=False` keeps the test free of
network access: no OTLP endpoint is required in that mode.
"""

from a2a_otel_kit import Observability, ObservabilitySettings


def test_observability_lifecycle_completes_with_tracing_disabled() -> None:
    settings = ObservabilitySettings(
        service_name="multi-agent-credit-desk-workspace-check",
        service_version="0.1.0",
        environment="test",
        enabled=False,
    )

    observability = Observability.configure(settings)
    with observability.start_span("workspace.pin_check", attributes={"operation": "smoke_test"}):
        observability.emit_event("workspace.pin_check.completed", "success", operation="smoke_test")

    assert observability.flush() is True
    observability.shutdown()
    observability.shutdown()  # documented as idempotent; must not raise
