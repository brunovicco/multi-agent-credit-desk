# policy-mcp

A small, read-only MCP server that exposes a versioned catalog of the credit policy enforced by
`credit_core`. It answers "what does the current credit policy say" for any MCP-capable client; it
does not evaluate applications and does not mutate anything - see
`docs/adr/0009-reuse-existing-mcp-servers.md` and
`docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`.

No agent consumes this server yet (`risco-agent`/`decisao-agent` do not exist in this repository
today). It is built and tested standalone so the catalog it exposes is already correct and
verifiably in sync with `credit_core` before any consumer is wired to it.

## Why it reads `credit_core` directly

`policy_mcp` reads `credit_core.policy.DEMO_POLICY_V1` and `credit_core.domain.CriticalFlag`
directly instead of re-authoring the policy as an independent document. This guarantees what
agents are told the policy is can never drift from what `credit_core` actually enforces. Only one
module in this package, `policy_mcp.adapters.credit_core_policy_source`, imports `credit_core`; a
regression test AST-walks `domain/`, `application/`, and `entrypoints/` to fail the build if that
boundary is ever crossed. `credit_core` itself remains a pure, stdlib-only package with zero
awareness of `policy_mcp`.

## ⚠️ `DEMO_POLICY_V1` is a synthetic demo policy, not a production credit policy

Every weight, score band, decision threshold, and approval-authority amount this server reports
comes from `credit_core.policy.DEMO_POLICY_V1`, which is **invented for this project's tests and
demonstrations**. Nothing served by `policy-mcp` should be read, copied, or deployed as an actual
credit risk policy - see `packages/credit-core/README.md` for the full rationale.

## Tools

| Tool | Input | Output |
|---|---|---|
| `list_policies` | none | `PolicyListResult`: every known policy version (currently one: `credit-core-demo-policy-v1`) with a short summary each. |
| `get_policy` | `version: str` | `PolicyDetail`: the full policy - score components and bands, decision thresholds, and approval-authority tiers - for the requested version. Returns a machine-readable `POLICY_NOT_FOUND` tool error for an unknown version. |
| `list_critical_flags` | none | `CriticalFlagCatalog`: every synthetic critical flag (`credit_core.domain.CriticalFlag`) that forces a deterministic block, with its reason-code mapping. |

## Architecture

Clean Architecture, consistent with `docs/ARCHITECTURE.md`:

```text
services/policy-mcp/src/policy_mcp/
├── domain/        # PolicySummary, PolicyDetail, ScoreBandView, ... - policy-mcp's own vocabulary
├── application/    # PolicyCatalogPort (protocol) + PolicyCatalogQueries (use cases)
├── adapters/       # CreditCorePolicySource: the only module allowed to import credit_core
└── entrypoints/    # Pydantic wire schemas, the MCP server composition root, and the CLI entrypoint
```

`application` depends on a `PolicyCatalogPort` protocol it defines, not on `credit_core` directly;
`adapters.credit_core_policy_source.CreditCorePolicySource` implements that port. This keeps the
current single adapter swappable and keeps the drift-avoidance guarantee enforceable by a static
check rather than only documented.

## Running

```bash
python -m policy_mcp
```

Transport is selected via `POLICY_MCP_TRANSPORT` (default `stdio`); an unrecognized value fails
fast at startup rather than silently defaulting.

## Testing

```bash
uv run pytest services/policy-mcp
uv run pytest -m integration services/policy-mcp/tests/integration --no-cov
```

`tests/unit` covers the domain-to-wire-schema mapping, the `credit_core`-sourced adapter (a
field-for-field drift regression against `DEMO_POLICY_V1` and `CriticalFlag`), the application
queries against a fake port, and the architecture boundary (no `credit_core` import outside the
adapter). `tests/contract` exercises all three tools through the MCP SDK's in-process client/server
session machinery. `tests/integration` spawns the packaged `python -m policy_mcp` CLI over stdio
for one real MCP handshake and tool call end to end.
