# decisao-agent

Executes the deterministic `credit_core` evaluation for one application snapshot and
cross-checks the result against `policy-mcp`'s catalog, so a decision can never be trusted
against a critical flag name or policy version `policy-mcp` does not itself recognize.

## Current scope: deterministic core only, no A2A surface yet

This is the workspace's first package to consume both `credit_core` (directly, for evaluation)
and `policy-mcp` (over the real MCP protocol, as a client) - but it is **not yet an A2A agent**.
No A2A protocol SDK is pinned anywhere in this workspace today; adding one is a separate,
explicitly reviewed dependency decision deferred to a later milestone. Until then,
`decisao-agent` exposes a batch CLI: one `ApplicationSnapshotInput` JSON document on stdin, one
`CreditOpinion` JSON document on stdout. See
`docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md`.

No orchestrator or other agent calls this yet; it is built and tested standalone, the same way
`policy-mcp` and `bureau-mcp` were.

## Why it reads `credit_core` directly

`decisao_agent` calls `credit_core.evaluation.evaluate_credit_application` directly instead of
re-implementing scoring or alçada logic. Only one module,
`decisao_agent.adapters.credit_core_evaluation_adapter`, imports `credit_core`; a regression
test AST-walks `domain/`, `application/`, and `entrypoints/` to fail the build if that boundary
is ever crossed - the same pattern `policy-mcp` established for reading `credit_core.policy`
(`docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`).

## Why it queries `policy-mcp` before trusting a result

`ApplicationSnapshot.critical_flags` holds flag *names* rather than a decisao-agent-owned enum:
the closed set of valid names is `policy-mcp`'s catalog, not a third copy of
`credit_core.domain.CriticalFlag`'s taxonomy. Before evaluating,
`EvaluateCreditApplicationUseCase` fetches `policy-mcp`'s current critical flag names and policy
versions and rejects an unknown flag name or an evaluation result whose policy version
`policy-mcp` does not recognize - an integrity check against the two packages silently drifting
to different `credit_core` builds.

## Architecture

Clean Architecture, consistent with `docs/ARCHITECTURE.md`:

```text
services/decisao-agent/src/decisao_agent/
├── domain/        # ApplicationSnapshot, CreditOpinion, errors - decisao-agent's own vocabulary
├── application/    # CreditEvaluationPort + PolicyCatalogPort (protocols) + the evaluation use case
├── adapters/       # CreditCoreEvaluationAdapter (only module importing credit_core)
│                   # PolicyMcpClient (only module speaking the MCP protocol)
└── entrypoints/    # Pydantic wire schemas and the CLI composition root
```

## Running

```bash
echo '{
  "annual_revenue": "5000000",
  "total_debt": "1200000",
  "monthly_debt_service": "40000",
  "monthly_operating_cash_flow": "180000",
  "bureau_score": "780",
  "years_in_operation": 6,
  "requested_amount": "500000",
  "critical_flags": []
}' | python -m decisao_agent
```

Prints exactly one JSON document to stdout: a `CreditOpinion` on success (exit `0`), or a stable
`{"code": ..., "message": ...}` error envelope on failure (exit `1`) - never a raw exception
message or stack trace either way. This mirrors how `policy-mcp` and `bureau-mcp` return a tool
error on the same channel as a tool result. stderr carries structured logs only.

`PolicyMcpClient` spawns `python -m policy_mcp` per call with a 30-second overall timeout by
default; every failure mode (bad command, crashed or hung subprocess, malformed response) is
translated into `POLICY_CATALOG_UNAVAILABLE`, never a raw exception or an unhandled traceback.
Set `DECISAO_AGENT_POLICY_MCP_COMMAND` to override the spawned command, e.g. for testing against
a broken policy-mcp deliberately.

## Testing

```bash
uv run pytest services/decisao-agent
uv run pytest -m integration services/decisao-agent/tests/integration --no-cov
```

`tests/unit` covers the domain value objects, the `credit_core`-sourced adapter (a drift
regression against `evaluate_credit_application`), the `policy-mcp` MCP client against a fake
tool-call transport, the use case against fake ports, the schema mapping, and the architecture
boundary (no `credit_core` import outside the adapter). `tests/integration` spawns a real
`policy-mcp` subprocess and runs the full `python -m decisao_agent` CLI end to end over stdin/stdout.
