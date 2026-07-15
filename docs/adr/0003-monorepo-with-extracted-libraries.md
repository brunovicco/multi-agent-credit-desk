# ADR-0003: Monorepo application with extracted libraries

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-001

## Context

The original proposal envisioned 12 repositories; version 0.1 of the blueprint decided on a pure
monorepo. On revision, separate repositories have real portfolio value (profile visibility, their
own README, independent installability) — but the extraction criterion cannot be to mirror the
architecture in repositories.

## Decision

Extraction criterion: does it have standalone value outside the Credit Desk? Result — 4 visible
repositories:

| Repository | Content | Role |
|---|---|---|
| `multi-agent-credit-desk` | Application (monorepo, uv workspace) | Main demo, `docker compose up` |
| `a2a-otel-kit` | Library: OTel init, `traceparent` propagation, structlog JSON, sanitization, A2A/MCP interceptors | pip-installable, generic |
| `policy-model-router` | Service: eliminatory constraints + workload table + decision record | Published image (GHCR), generic for any LiteLLM stack |
| `openfinance-br-mcp` | MCP server (already existing, mock) | Open Finance data source |

The monorepo consumes `a2a-otel-kit` as a pinned dependency (release tags + changelog, updated via
PR) and `policy-model-router` as an image in the compose stack — demonstrating real contract
versioning between repositories, without paying the cost of maintaining 12.

Remain in the monorepo (no standalone audience): orchestrator, the 4 agents, `credit-core`,
`contracts`, `bureau-mcp`, `policy-mcp`, infra.

## Consequences

Release overhead only where there is value. Splitting the agents into separate repositories would
kill the one-command evaluation experience. Extracted library interfaces in 0.x may change quickly
early on — mitigated by contract tests in the monorepo and frequent releases.
