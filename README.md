# multi-agent-credit-desk

A multi-agent platform that analyzes corporate credit applications for Brazilian legal entities
(pessoas jurídicas, PJ) and produces an auditable credit decision with reproducible evidence. Built
on Python 3.13, uv, and the team Claude Code engineering harness.

**All customer and Open Finance data used or planned for this project is synthetic.** No real Open
Finance, BCB, or credit bureau connection exists or is planned to exist without an explicit,
separately reviewed integration. See `docs/adr/0009-reuse-existing-mcp-servers.md` for the
transparency policy on the mock Open Finance MCP server.

## Current state: Milestone 3 - deterministic credit core

`packages/contracts` provides versioned Pydantic v2 schemas for artifact envelopes, structured
events, and model-routing decisions (see `packages/contracts/README.md`). Agent-specific artifact
payload schemas are not implemented yet.

`packages/credit-core` now implements a deterministic, policy-driven credit evaluation core
(score, blocking rules, approval-authority policy) behind a synthetic demo policy - see
`packages/credit-core/README.md`. No agents, orchestrator, or MCP servers are implemented yet.

`a2a-otel-kit==0.4.2` (https://github.com/brunovicco/a2a-otel-kit) is pinned as a root workspace
dependency per ADR-0003. It has no consumer yet - that lands with the first `services/*` package -
so today it is only proven to install and initialize correctly, the same way `credit_core` and
`credit_desk_contracts` are proven in the workspace-validation `Dockerfile` image (see
`tests/unit/test_a2a_otel_kit_pin.py`).

`infra/docker-compose.yml` stands up the OTel Collector + a self-hosted Langfuse stack (ADR-0006),
fanning traces out to Langfuse by default and to Datadog opt-in. See "Local observability stack"
in `docs/DEVELOPMENT.md`. LiteLLM and `openfinance-br-mcp` are not wired into the compose yet.

```text
multi-agent-credit-desk/
├── packages/
│   ├── contracts/      # import: credit_desk_contracts - envelope/event/routing schemas
│   └── credit-core/     # import: credit_core - deterministic scoring/policy core (implemented)
├── docs/adr/            # canonical architecture decisions (0001, 0002-0010)
└── pyproject.toml       # virtual workspace coordinator (tool.uv.package = false); no application code
```

The root `pyproject.toml` is a **virtual workspace coordinator** - it holds no application code and
is not itself installed. Future application entrypoints (agents, orchestrator) belong under
`services/`, which does not exist yet. See `docs/ARCHITECTURE.md` and `docs/architecture-blueprint.md`
for the full plan.

`packages/credit-core` enforces a default-deny import policy (standard library and self only, no
LLM/A2A/MCP/HTTP/dynamic imports) via `scripts/validate_architecture.py` - see
`docs/adr/0008-deterministic-core-without-llm.md`.

## Development

```bash
uv sync --frozen --all-packages
uv run pytest
```

`--all-packages` is required because the workspace root is virtual and installs nothing by default.

## Quality gate

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run python scripts/validate_architecture.py
uv run python scripts/validate_mcp_config.py
uv run mypy packages tests
uv run pytest
uv run bandit -c pyproject.toml -r packages
uv run pip-audit
```

## Container

```bash
docker build -t multi-agent-credit-desk .
docker run --rm multi-agent-credit-desk
```

`Dockerfile` currently builds a **workspace-validation image** only - it imports `credit_core`,
`credit_desk_contracts`, and `a2a_otel_kit` to prove the workspace builds and installs cleanly. It
is not an application runtime image; a future milestone replaces its `CMD` with a real `services/*`
entrypoint.

See `AGENTS.md` for the engineering contract and `docs/ARCHITECTURE.md` for dependency rules.
