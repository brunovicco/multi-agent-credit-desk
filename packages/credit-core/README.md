# credit-core

Deterministic credit scoring, approval-authority policy, and blocking rules for the Multi-Agent
Credit Desk. Zero LLM in the decision path — see `docs/adr/0008-deterministic-core-without-llm.md`.

## Import policy

`credit_core` allows only standard-library imports and imports of itself. Every third-party import,
every other workspace package, and dynamic import mechanisms (`importlib`, `__import__`) are
rejected by default. This is enforced by `scripts/validate_architecture.py` and documented in
`.claude/rules/credit-core.md` — it is not a convention to remember, it is a build-breaking check.

This is a scaffolded, empty package as of Milestone 1 (workspace foundation) — no scoring or policy
logic is implemented yet.
