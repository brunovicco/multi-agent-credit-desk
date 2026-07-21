# Architecture

## Context

Multi-agent platform that analyzes corporate credit applications for Brazilian legal entities
(pessoas jurídicas, PJ) and produces an auditable credit decision with reproducible evidence. See
`docs/architecture-blueprint.md` for the full narrative and `docs/adr/` for the canonical,
individually recorded decisions.

## Workspace

As of Milestone 3 (deterministic credit core), this repository is a uv workspace whose root is a
**virtual coordinator** (`tool.uv.package = false` in `pyproject.toml`) - it holds no application
code and is not itself installed. The workspace members are:

| Package | Import name | Purpose |
|---|---|---|
| `packages/contracts` | `credit_desk_contracts` | Versioned Pydantic v2 schemas for artifact envelopes, structured events, and model-routing decisions. Agent-specific artifact payload schemas are deferred. See `packages/contracts/README.md`. |
| `packages/credit-core` | `credit_core` | Deterministic credit scoring and policy core. Implemented behind a synthetic demo policy - see `packages/credit-core/README.md`. |
| `services/policy-mcp` | `policy_mcp` | Read-only MCP server exposing a versioned catalog of the credit policy `credit_core` enforces. The workspace's first `services/*` package - see `services/policy-mcp/README.md`. |
| `services/bureau-mcp` | `bureau_mcp` | Read-only MCP server exposing a synthetic credit-bureau report catalog (external score, negative records), keyed by CNPJ. No real credit-bureau connection exists or is planned - see `services/bureau-mcp/README.md`. |
| `services/decisao-agent` | `decisao_agent` | Executes `credit_core.evaluation` directly, cross-checks the result against `policy-mcp`'s catalog over the real MCP protocol, and best-effort drafts an LLM opinion narrative via `policy-model-router`/LiteLLM. The workspace's first real A2A agent, exposed both as a batch CLI and an A2A server over `a2a-sdk` - see `services/decisao-agent/README.md`. |
| `services/cadastral-agent` | `cadastral_agent` | Screens a company's KYC standing against `bureau-mcp`'s report via a small, deterministic policy (`APPROVED`/`COMMITTEE_REFERRAL`/`BLOCKED`). CLI only in its first milestone, no A2A surface yet - see `services/cadastral-agent/README.md`. |

`credit_core` may import only the standard library and itself; every third-party or other
workspace import is rejected by default, and dynamic import mechanisms (`importlib`, `__import__`)
are explicitly forbidden. This is enforced by `scripts/validate_architecture.py`, not just
documented - see `.claude/rules/credit-core.md` and
`docs/adr/0008-deterministic-core-without-llm.md`.

`services/policy-mcp` depends one-directionally on `credit_core` - its adapter layer reads
`credit_core.policy.DEMO_POLICY_V1` and `credit_core.domain.CriticalFlag` directly so its catalog
can never drift from what `credit_core` enforces, confined to a single adapter module and enforced
by a test that fails if any other layer imports `credit_core` - see
`docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`. `credit_core` itself stays
completely unaware of `policy-mcp` or any other consumer.

`services/bureau-mcp` has no equivalent system of record to depend on: no real credit-bureau
connection exists or is planned (see `docs/adr/0009-reuse-existing-mcp-servers.md`). Its adapter,
`bureau_mcp.adapters.synthetic_bureau_source.SyntheticBureauSource`, *is* the system of record - a
fixed, in-memory dataset of three demo personas - so `bureau-mcp` has no external workspace
dependency at all beyond `mcp` and `pydantic`.

`services/decisao-agent` depends one-directionally on both `credit_core` and `policy-mcp` -
`decisao_agent.adapters.credit_core_evaluation_adapter.CreditCoreEvaluationAdapter` is the only
module that imports `credit_core`, mirroring `policy-mcp`'s boundary, and
`decisao_agent.adapters.policy_mcp_client.PolicyMcpClient` is the only module that speaks the MCP
protocol - decisao-agent's first real MCP *client*, as opposed to the MCP *servers* built before
it. See `docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md`.

`services/decisao-agent` also depends on `a2a-sdk` (`a2a-sdk[http-server]`, pinned in
`services/decisao-agent/pyproject.toml`, not at the root - each `services/*` package that
implements an A2A surface declares this dependency itself, the same way each MCP-consuming
package declares `mcp` itself rather than pinning it at the root). Its A2A composition root
(`decisao_agent.entrypoints.a2a_server`) is a second, separate entrypoint alongside the batch CLI
- both call the same `EvaluateCreditApplicationUseCase`. See
`docs/adr/0013-decisao-agent-adopts-a2a-sdk.md`.

`EvaluateCreditApplicationUseCase` additionally depends on two optional ports,
`ModelRoutingPort`/`ChatCompletionPort`, implemented by `ModelRouterClient`/`LiteLLMClient`
(`httpx` against `policy-model-router`/LiteLLM). Unlike `credit_core`/`mcp`, `ModelRouterClient`
returns `credit_desk_contracts.routing.ModelRouteDecision` verbatim rather than translating it
into decisao-agent's own vocabulary - `credit_desk_contracts` is the workspace's shared,
versioned contract layer (ADR-0005), not a single-producer package. Narrative drafting is
strictly best-effort and never affects the deterministic decision - see
`docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md`.

`a2a-otel-kit==0.4.2` (https://github.com/brunovicco/a2a-otel-kit) is pinned in the root
`pyproject.toml` `[project.dependencies]` per ADR-0003 - a virtual project's dependencies are
still installed even though `tool.uv.package = false` means the root package itself is never
built. It still has no consumer: `credit_core` forbids third-party imports by design and
`contracts` is schema-only, so neither is a legitimate consumer, and `services/decisao-agent`'s
new A2A surface uses `a2a-sdk` directly without yet wiring `a2a-otel-kit`'s `Observability`
around it. `tests/unit/test_a2a_otel_kit_pin.py` and the workspace-validation `Dockerfile` image
remain the only proof that the pin resolves and its public API (`Observability`,
`ObservabilitySettings`) behaves as documented.

`services/cadastral-agent` depends one-directionally on `bureau-mcp` -
`cadastral_agent.adapters.bureau_mcp_client.BureauMcpClient` is the only module that speaks the
MCP protocol, mirroring `decisao_agent.adapters.policy_mcp_client.PolicyMcpClient`'s boundary.
Unlike `decisao_agent.application.ports.PolicyCatalogSnapshot`,
`cadastral_agent.domain.bureau_finding.BureauFinding` lives in the domain layer, not
`application`, since it is cadastral-agent's own business vocabulary (what the KYC policy
reasons over), not just a query result shape. `cadastral-agent`'s KYC policy
(`cadastral_agent.domain.kyc_policy`) is deliberately scoped to what `bureau-mcp` actually
provides, not the full "sócios, situação fiscal" screening `docs/architecture-blueprint.md`
describes, for which no data source exists in this workspace - see
`docs/adr/0016-cadastral-agent-kyc-screening-policy.md`.

Application entrypoints for the orchestrator do not exist yet. `services/policy-mcp` and
`services/bureau-mcp` remain standalone MCP servers with no A2A surface. `services/decisao-agent`
is the first `services/*` package with a real A2A surface; `services/cadastral-agent` has none yet
(CLI only). No orchestrator discovers or calls any agent yet - the orchestrator remains a future
`services/*` package.

## Layers

The layered Clean Architecture pattern below is instantiated by `services/policy-mcp` - the
workspace's first `services/*` package, followed by `services/bureau-mcp` and
`services/decisao-agent` - and is the required pattern for every `services/*` package built after
them. `scripts/validate_architecture.py` already discovers and enforces it under any
`services/*/src/` root (see `.claude/rules/architecture.md`).

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
  `credit_core` and `credit_desk_contracts`) - it is not an application runtime image. A future
  milestone replaces its `CMD` with a real `services/*` entrypoint.

## Diagrams

Add C4 context/container diagrams and sequence diagrams for critical flows.
