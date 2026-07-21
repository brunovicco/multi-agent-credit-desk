# ADR-0012: `decisao-agent` sources `credit_core` evaluation directly, and defers an A2A SDK

- Status: Accepted
- Date: 2026-07-20
- Blueprint reference: ADR-002

## Context

`decisao-agent` (`docs/architecture-blueprint.md` section 2.2) is the agent that "executes
`credit-core` (score + alçada determinísticos) and redige o parecer." Nothing consumes it yet -
no orchestrator or other agent exists in this repository today - so it is built and tested
standalone, the same way `services/policy-mcp` and `services/bureau-mcp` were.

Two questions had to be settled before writing any code:

1. How does `decisao-agent` reach `credit_core`'s scoring and alçada logic without re-implementing
   it or creating a second, independently authored copy that could drift?
2. Is `decisao-agent` an A2A agent yet, given the blueprint's topology (section 2.1) puts every
   agent behind an orchestrator reachable over the A2A protocol (Agent Cards, tasks, artifacts)?

On the second question: no A2A protocol SDK is pinned anywhere in this workspace. `a2a-otel-kit`
(`docs/adr/0003-monorepo-with-extracted-libraries.md`), the only `a2a`-prefixed dependency
present, is an observability kit (OTel init, structlog JSON, trace propagation, sanitization) -
its public API (`Observability`, `ObservabilitySettings`, `start_span`, `emit_event`) has no
Agent Card, task, or artifact types. Adding a real A2A SDK is a new third-party dependency that
needs its own review (maintenance, vulnerabilities, license, provenance) per `AGENTS.md`, not a
decision to fold into evaluation logic.

## Decision

**Sourcing `credit_core`.** `decisao_agent` reads `credit_core.evaluation.evaluate_credit_application`
and `credit_core.domain` directly and translates them into its own vocabulary
(`decisao_agent.domain.snapshot`, `decisao_agent.domain.opinion`) at a single, tested boundary -
the same pattern `policy-mcp` established in
`docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`. Only one module,
`decisao_agent.adapters.credit_core_evaluation_adapter.CreditCoreEvaluationAdapter`, is allowed
to import `credit_core`. It implements a consumer-defined
`decisao_agent.application.ports.CreditEvaluationPort` protocol, enforced by
`services/decisao-agent/tests/unit/test_architecture_boundary.py`, which AST-walks `domain/`,
`application/`, and `entrypoints/` and fails the build if any of them import `credit_core`.

`ApplicationSnapshot.critical_flags` holds flag *names* (plain strings) rather than a
decisao-agent-owned enum mirroring `credit_core.domain.CriticalFlag`: the closed set of valid
names is policy-mcp's catalog, already the canonical translation of that taxonomy. Before
evaluating, `application.evaluate.EvaluateCreditApplicationUseCase` fetches policy-mcp's current
critical flag names and policy versions (via a second port, `PolicyCatalogPort`, implemented by
`decisao_agent.adapters.policy_mcp_client.PolicyMcpClient`, a real MCP client speaking to a
`policy-mcp` subprocess over stdio) and rejects an unknown flag name or a `credit_core`-applied
policy version policy-mcp does not itself recognize. This is an integrity check against
decisao-agent and policy-mcp silently drifting to different `credit_core` builds - not
duplicating validation `credit_core` already performs.

**Deferring the A2A surface.** This milestone ships `decisao-agent` as a batch CLI only
(`python -m decisao_agent`, one `ApplicationSnapshotInput` JSON document on stdin, one
`CreditOpinion` JSON document on stdout) - no Agent Card, no A2A task lifecycle, no
`a2a-otel-kit` integration yet. Adding a real A2A protocol SDK, and wiring `a2a-otel-kit`'s
`Observability` around task execution, is deferred to a follow-up milestone once that dependency
has been explicitly reviewed. This keeps the diff that establishes the `credit_core` +
`policy-mcp` integration reviewable on its own, without conflating it with a new third-party
protocol dependency.

## Consequences

What `decisao-agent` reports as a credit decision can never drift from what `credit_core`
actually computes, and can never reference a critical flag or policy version policy-mcp itself
does not know about - the same drift-avoidance guarantee ADR-0011 established for policy-mcp's
catalog, extended to an actual evaluation. The cost is the same as ADR-0011's: a hard dependency
on `credit_core`'s public API shape, with a drift-regression test that fails loudly on a
breaking change.

`decisao-agent` is not yet an A2A agent despite the blueprint's naming; `services/decisao-agent/README.md`
states this explicitly. A follow-up ADR will record the A2A SDK choice when that milestone starts,
including its dependency review. Until then, no orchestrator or other agent can call
`decisao-agent` except by invoking its CLI directly.
