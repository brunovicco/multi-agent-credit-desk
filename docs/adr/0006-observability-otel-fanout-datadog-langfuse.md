# ADR-0006: Observability via OpenTelemetry fan-out to Datadog and Langfuse

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-004

## Context

Datadog is a market keyword, but requires a paid account, and whoever clones the repository cannot
reproduce the traces. Langfuse is self-hosted and covers the genAI layer (cost, tokens, evals) but
is not infrastructure APM.

## Decision

Instrumentation exclusively via OpenTelemetry (SDK + `gen_ai.*` semantic conventions), with W3C
`traceparent` propagation across all calls (A2A, model-router, MCP, queues). A central OTel
Collector fans out to:

- a **Datadog** exporter (APM + LLM Observability) — enabled by profile, for environments with an
  account;
- an **OTLP → Langfuse** exporter, self-hosted — always active in the compose stack, reproducible
  by any evaluator.

The native LiteLLM → Langfuse callback complements per-call cost/token data.

## Consequences

"Backend-agnostic by design" becomes a demonstrable feature. The compose stack becomes heavier
(Langfuse v3 = Postgres + ClickHouse + Redis + MinIO) — accepted, it is faithful to production.
