# ADR-0004: Three separated routing layers

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-002

## Context

"Routing" conflates three distinct decisions.

## Decision

| Layer | Question | Owner |
|---|---|---|
| Agent routing | Which agent executes the activity? | `orchestrator` (via Agent Card skills) |
| Model routing | Which model group serves the workload? | `model-router` (infrastructure service) |
| Provider routing | Which deployment/provider serves the call? | LiteLLM Gateway |

`model-router` is not an A2A agent — it is infrastructure, called over HTTP by agents before each
LLM call.

## Consequences

Changing the model-routing mechanism (e.g., adding RouteLLM in Phase 3) does not change agents or
the A2A protocol. LiteLLM handles provider abstraction, retries, cooldowns, and fallback within the
group.
