# ADR-0008: Deterministic core with no LLM (guarded in CI)

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-006

## Decision

Credit score, approval-authority policy, and blocking rules live in `packages/credit-core`, a
pure Python module with no LLM/provider-SDK imports. The forbidden-dependency list in
`scripts/validate_architecture.py` fails the build if it detects a disallowed import — see
`docs/adr/0010-claude-code-harness-as-base.md` for why this is an entry in the harness's existing
check rather than a new script.

LLM is used only at the edges: document extraction, qualitative cash-flow analysis, opinion
drafting.

## Consequences

The credit decision is reproducible and auditable by construction. `policy.decision` in the trace
points to the applied policy version.
