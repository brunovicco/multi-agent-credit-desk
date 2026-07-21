# multi-agent-credit-desk

A multi-agent platform that analyzes corporate credit applications for Brazilian legal entities
(pessoas jurídicas, PJ) and produces an auditable credit decision with reproducible evidence. Built
on Python 3.13, uv, and the team Claude Code engineering harness.

**All customer and Open Finance data used or planned for this project is synthetic.** No real Open
Finance, BCB, or credit bureau connection exists or is planned to exist without an explicit,
separately reviewed integration. See `docs/adr/0009-reuse-existing-mcp-servers.md` for the
transparency policy on the mock Open Finance MCP server.

## Current state: Milestone 6c-ii - best-effort LLM opinion narrative

`packages/contracts` provides versioned Pydantic v2 schemas for artifact envelopes, structured
events, and model-routing decisions (see `packages/contracts/README.md`). Agent-specific artifact
payload schemas are not implemented yet.

`packages/credit-core` implements a deterministic, policy-driven credit evaluation core (score,
blocking rules, approval-authority policy) behind a synthetic demo policy - see
`packages/credit-core/README.md`.

`services/policy-mcp` is the workspace's first `services/*` package: a small, read-only MCP server
(`import policy_mcp`) that exposes a versioned catalog of the credit policy `credit_core` enforces,
reading `credit_core.policy.DEMO_POLICY_V1` and `credit_core.domain.CriticalFlag` directly so the
catalog can never drift from what `credit_core` actually applies - see
`services/policy-mcp/README.md` and `docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`.

`services/bureau-mcp` is the second `services/*` package: a small, read-only MCP server
(`import bureau_mcp`) that exposes a synthetic credit-bureau report (external score, negative
records) for a fixed set of demo companies, keyed by CNPJ. Unlike `policy-mcp`, it has no real
system of record to read from - no real credit-bureau connection exists or is planned - so its
adapter *is* the system of record: a fixed, in-memory dataset of the three demo personas from
`docs/architecture-blueprint.md` - see `services/bureau-mcp/README.md` and
`docs/adr/0009-reuse-existing-mcp-servers.md`.

No agent consumes either MCP server directly yet (`cadastral-agent`/`risco-agent` are not
implemented in this repository); both are still built and tested standalone. No orchestrator is
implemented yet either.

`services/decisao-agent` is the workspace's first `services/*` package with application logic
beyond serving a catalog: it calls `credit_core.evaluation.evaluate_credit_application` directly
and cross-checks the result against `policy-mcp`'s catalog over the real MCP protocol (its first
real MCP *client*, not just a server), so a decision can never reference a critical flag or
policy version `policy-mcp` does not itself recognize - see
`docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md`. It is also the
workspace's **first real A2A agent**: `python -m decisao_agent.entrypoints.a2a_server` advertises
one skill, `evaluate_credit_application`, over the official `a2a-sdk` (Linux Foundation-governed,
chosen over the independent `python-a2a` package for provenance, maintenance, and license - see
`docs/adr/0013-decisao-agent-adopts-a2a-sdk.md`). The batch CLI (`python -m decisao_agent`) still
exists alongside it - both entrypoints share the same use case and adapters. See
`services/decisao-agent/README.md`.

`EvaluateCreditApplicationUseCase` now always computes the deterministic decision first, then
attempts to draft `CreditOpinion.narrative` via `ModelRouterClient`/`LiteLLMClient`
(`ModelRoutingPort`/`ChatCompletionPort` in `packages/decisao-agent`'s application layer) -
strictly best-effort: a routing or completion failure is caught and mapped to `narrative=None`,
never re-raised, and never affects the deterministic decision - see
`docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md`. **No real provider API
key (`GROQ_API_KEY`/`ANTHROPIC_API_KEY`) is available in this environment**, so `narrative` is
always `None` in practice today, even though real routing against a running
`policy-model-router` container has been verified to succeed - this resolves automatically once
real credentials are configured, no code change required. See `services/decisao-agent/README.md`.

`a2a-otel-kit==0.4.2` (https://github.com/brunovicco/a2a-otel-kit) is pinned as a root workspace
dependency per ADR-0003. It still has no consumer: `decisao-agent`'s new A2A surface uses
`a2a-sdk` directly and does not yet wire `a2a-otel-kit`'s `Observability` around it - so today the
pin is still only proven to install and initialize correctly, the same way `credit_core` and
`credit_desk_contracts` are proven in the workspace-validation `Dockerfile` image (see
`tests/unit/test_a2a_otel_kit_pin.py`).

`infra/docker-compose.yml` stands up `policy-model-router` (ADR-0003/0004 - a generic image
published from its own repo, github.com/brunovicco/policy-model-router, not built here), a LiteLLM
proxy (ADR-0004 - provider routing for the 4 model groups in `infra/litellm/config.yaml`, matching
`credit_desk_contracts.enums.ModelGroup`), and the OTel Collector + a self-hosted Langfuse stack
(ADR-0006), fanning traces out to Langfuse by default and to Datadog opt-in. See "Local
observability stack" in `docs/DEVELOPMENT.md`. `openfinance-br-mcp` is not wired into the compose
yet.

```text
multi-agent-credit-desk/
├── packages/
│   ├── contracts/      # import: credit_desk_contracts - envelope/event/routing schemas
│   └── credit-core/     # import: credit_core - deterministic scoring/policy core (implemented)
├── services/
│   ├── policy-mcp/      # import: policy_mcp - read-only MCP server, credit_core policy catalog
│   ├── bureau-mcp/      # import: bureau_mcp - read-only MCP server, synthetic bureau report catalog
│   └── decisao-agent/   # import: decisao_agent - credit_core evaluation + policy-mcp cross-check, CLI + A2A server
├── docs/adr/            # canonical architecture decisions (0001, 0002-0014)
└── pyproject.toml       # virtual workspace coordinator (tool.uv.package = false); no application code
```

The root `pyproject.toml` is a **virtual workspace coordinator** - it holds no application code and
is not itself installed. Future application entrypoints (agents, orchestrator) belong under
`services/`, alongside `policy-mcp`, `bureau-mcp`, and `decisao-agent`. See `docs/ARCHITECTURE.md`
and `docs/architecture-blueprint.md` for the full plan.

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
uv run mypy packages services tests
uv run pytest
uv run bandit -c pyproject.toml -r packages services
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
