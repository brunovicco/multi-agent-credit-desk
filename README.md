# multi-agent-credit-desk

Python 3.13 project using uv and the team Claude Code engineering harness.

## Development

```bash
uv sync --frozen
uv run pytest
```

## Quality gate

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run python scripts/validate_architecture.py
uv run python scripts/validate_mcp_config.py
uv run mypy src tests
uv run pytest
uv run bandit -c pyproject.toml -r src
uv run pip-audit
```

## Container

```bash
docker build -t multi-agent-credit-desk .
docker run --rm multi-agent-credit-desk
```

`Dockerfile` ships a placeholder `CMD`; replace it with the project's real entrypoint (an ASGI
server, a worker loop, etc.) once one exists.

See `AGENTS.md` for the engineering contract and `docs/ARCHITECTURE.md` for dependency rules.
