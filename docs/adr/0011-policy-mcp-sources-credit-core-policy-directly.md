# ADR-0011: `policy-mcp` sources the credit policy directly from `credit_core`

- Status: Accepted
- Date: 2026-07-20
- Blueprint reference: ADR-007

## Context

`policy-mcp` (`docs/adr/0009-reuse-existing-mcp-servers.md`) is a small, read-only MCP server that
exposes a versioned catalog of the credit policy `packages/credit-core` enforces, so `risco-agent`
and `decisao-agent` can query "what does the current credit policy say" without re-deriving it.
Nothing consumes it yet - those agents do not exist in this repository today - so it is built and
tested standalone.

The catalog could have been authored as an independent document (YAML, a hand-written Python
module, or a database row) describing the same weights, bands, and thresholds. That approach
creates a second source of truth: nothing prevents the catalog from silently drifting from what
`credit_core.evaluation.evaluate_credit_application` actually applies, and a drifted catalog is
worse than no catalog, because agents would trust a description of a policy that is not the one
being enforced.

## Decision

`policy-mcp` reads `credit_core.policy.DEMO_POLICY_V1` and `credit_core.domain.CriticalFlag`
directly and translates them into its own read-only vocabulary
(`policy_mcp.domain.catalog`) at a single, tested boundary. `CreditPolicy.version`
(`"credit-core-demo-policy-v1"`) is reused verbatim as the canonical version string; `policy-mcp`
never assigns its own parallel version scheme.

Only one module, `policy_mcp.adapters.credit_core_policy_source.CreditCorePolicySource`, is
allowed to import `credit_core`. It implements a consumer-defined
`policy_mcp.application.ports.PolicyCatalogPort` protocol so `policy_mcp.application` depends on
an interface it owns, not on `credit_core` directly - the documented seam for a future alternative
policy source (e.g. a real policy service), should one ever replace `credit_core` as the system of
record. The boundary is enforced by
`services/policy-mcp/tests/unit/test_architecture_boundary.py`, which AST-walks `domain/`,
`application/`, and `entrypoints/` and fails the build if any of them import `credit_core`, and by
`services/policy-mcp/tests/unit/test_credit_core_policy_source.py`, which asserts the adapter
matches `DEMO_POLICY_V1` and `CriticalFlag` field for field, not with spot checks.

The approval-authority tiers (`ANALYST`, `SENIOR_ANALYST`, `CREDIT_COMMITTEE`,
`EXECUTIVE_BOARD`) are derived only from `CreditPolicy`'s public amount-threshold fields and the
public `credit_core.domain.ApprovalAuthority` enum. The adapter never imports
`credit_core.evaluation._authority`, which is private and not meant for reuse outside
`credit_core.evaluation`.

`credit_core` itself is unaffected and unaware of `policy-mcp`: the dependency is one-directional
(`policy-mcp -> credit_core`), and `credit_core` remains a pure, stdlib-only package per
`docs/adr/0008-deterministic-core-without-llm.md`. `scripts/validate_architecture.py` already
discovers and enforces Clean Architecture layering under any `services/*/src/` root with zero
configuration, so it began checking `policy-mcp`'s layering automatically once the package was
added, with no change to the validator itself.

## Consequences

What agents are told the credit policy is can never drift from what `credit_core` actually
enforces - a catalog entry and an evaluation outcome are always backed by the same
`CreditPolicy` instance. The cost is a hard dependency from `policy-mcp` on `credit_core`'s public
API shape: a breaking change to `CreditPolicy`, `ScoreComponentPolicy`, `ScoreBand`, or
`CriticalFlag` must update the adapter's translation functions, and the drift-regression test
fails loudly if it does not. This is judged preferable to maintaining a second, independently
authored policy document that could silently fall out of sync.
