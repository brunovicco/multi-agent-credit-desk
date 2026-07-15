---
name: quality-gate
description: Run the complete Python quality gate and summarize failures without changing configuration.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash
---

Run the quality gate in this order and stop only when continuing cannot provide useful evidence:

1. `uv lock --check`
2. `uv run ruff check .`
3. `uv run ruff format --check .`
4. `uv run python scripts/validate_architecture.py`
5. `uv run python scripts/validate_mcp_config.py`
6. `uv run mypy src tests`
7. `uv run pytest`
8. `uv run bandit -c pyproject.toml -r src`
9. `uv run pip-audit`

Do not edit files or weaken settings. Report command, status, key errors, whether each failure is related to the current diff, and the final gate result.
