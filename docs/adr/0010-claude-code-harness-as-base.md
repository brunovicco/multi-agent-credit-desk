# ADR-0010: `claude-python-engineering-harness` as the base for every repository

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-008

## Context

A custom, publicly available harness (`bootstrap.py`, CLAUDE.md/AGENTS.md scaffold, path-conditional
rules, fail-closed hooks, agents, skills, CI with Ruff/Mypy/Pytest/Bandit/pip-audit, MCP
governance, `validate_architecture.py` with a forbidden-dependency list).

## Decision

All project repositories are born from the harness:

1. **Extracted libraries** (`a2a-otel-kit`, `policy-model-router`): direct `bootstrap.py`
   (`--git-init --lock`).
2. **Monorepo**: bootstrap at the root once, plus conversion of `pyproject.toml` to a uv workspace.
   A single `.claude/` at the root, using path-conditional rules per package (e.g., a rule in
   `packages/credit-core/` forbidding LLM imports). Do not bootstrap per service — that would
   duplicate `.claude/` eight times.
3. **Deterministic-core guard**: implemented as an entry in the harness's
   `validate_architecture.py` forbidden-dependency list — not as a new script.
4. **Harness MCP governance active** (`guard_mcp.py`, `validate_mcp_config.py`, `/review-mcp`): the
   project consumes 3 MCP servers, and MCP governance becomes part of the demo.
5. **Python 3.13** (harness default; `a2a-sdk`, LiteLLM, and OTel support it).

## Consequences

Standardization across the 4 repositories becomes part of the narrative: the harness is validated
by real consumption and becomes the 5th portfolio item. The harness's opt-in observability
philosophy (`docs/LLM_OBSERVABILITY.md`) is already consistent with ADR-0007.
