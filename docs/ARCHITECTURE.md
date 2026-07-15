# Architecture

## Context

Multi-agent platform that analyzes corporate credit applications for Brazilian legal entities
(pessoas jurídicas, PJ) and produces an auditable credit decision with reproducible evidence. See
`docs/architecture-blueprint.md` for the full narrative and `docs/adr/` for the canonical,
individually recorded decisions.

## Workspace

As of Milestone 1 (workspace foundation), this repository is a uv workspace whose root is a
**virtual coordinator** (`tool.uv.package = false` in `pyproject.toml`) — it holds no application
code and is not itself installed. The workspace members are:

| Package | Import name | Purpose |
|---|---|---|
| `packages/contracts` | `credit_desk_contracts` | Shared schemas, enums, and payload contracts. Scaffolded, empty. |
| `packages/credit-core` | `credit_core` | Deterministic credit scoring and policy core. Scaffolded, empty. |

`credit_core` may import only the standard library and itself; every third-party or other
workspace import is rejected by default, and dynamic import mechanisms (`importlib`, `__import__`)
are explicitly forbidden. This is enforced by `scripts/validate_architecture.py`, not just
documented — see `.claude/rules/credit-core.md` and
`docs/adr/0008-deterministic-core-without-llm.md`.

Application entrypoints (agents, orchestrator) do not exist yet. Their future home is `services/`,
not a root application package — this milestone deliberately does not create that directory.

## Layers

The layered Clean Architecture pattern below is not instantiated by any code in this repository
today. It is the required pattern for whichever `services/*` package is built first, and
`scripts/validate_architecture.py` already discovers and enforces it under any `services/*/src/`
root (see `.claude/rules/architecture.md`).

```text
services/<name>/src/<name>/
├── domain/
├── application/
├── adapters/
└── entrypoints/
```

### Domain

Pure business concepts, invariants, Value Objects, domain services, events, and domain errors.

### Application

Use cases, commands, queries, ports, authorization decisions, and transaction coordination.

### Adapters

Implementations of application ports for databases, messaging, HTTP, cache, storage, identity, and external SDKs.

### Entrypoints

HTTP, CLI, jobs, events, and serverless handlers. Entrypoints validate and translate transport data but do not own business rules.

## Dependency rule

```text
entrypoints -> application -> domain
adapters    -> application/domain
domain      -> no outer layer
```

## Cross-cutting decisions

- Configuration: environment variables validated at startup.
- Logging: structured events to stdout/stderr.
- Tracing: W3C trace context propagated across boundaries.
- Errors: infrastructure errors translated at adapters; external errors mapped at entrypoints.
- Time: UTC internally with timezone-aware values.
- Money: `Decimal` wrapped in a domain Value Object.
- Idempotency: required for externally visible side effects.
- Packaging: the repo `Dockerfile` currently builds a workspace-validation image only (imports
  `credit_core` and `credit_desk_contracts`) — it is not an application runtime image. A future
  milestone replaces its `CMD` with a real `services/*` entrypoint.

## Diagrams

Add C4 context/container diagrams and sequence diagrams for critical flows.
