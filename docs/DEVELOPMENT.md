# Development guide

## Setup

```bash
uv sync --frozen --all-packages
```

`--all-packages` is required: the root of this workspace is a virtual coordinator
(`tool.uv.package = false`), so a plain `uv sync` installs nothing from `packages/*` unless told to
sync the whole workspace.

## Run checks

```bash
uv run ruff check .
uv run ruff format --check .
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

`Dockerfile` is a multi-stage, uv-based build. As of Milestone 1 (workspace foundation) it produces
a **workspace-validation image**, not an application runtime image: the `builder` stage runs
`uv sync --frozen --all-packages --no-dev`, and the runtime stage's `CMD` only imports `credit_core`
and `credit_desk_contracts` to prove the workspace builds and installs cleanly. Replace the `CMD`
with a real `services/*` entrypoint once one exists.

## Local configuration

Copy `.env.example` only when the application supports local dotenv loading. Never commit `.env` or real credentials.

## Local infra stack

`infra/docker-compose.yml` stands up `policy-model-router` (ADR-0003/0004), a LiteLLM proxy
(ADR-0004), and the OTel Collector plus a self-hosted Langfuse v3 stack (Postgres, ClickHouse,
MinIO, Redis, Langfuse worker/web), per ADR-0006. Every credential in it is a fixed, local-only
demo default from `.env.example` - never real secrets, never meant to leave a local machine.

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps   # wait until every service is healthy
```

`policy-model-router` is a generic image published from its own repo
(github.com/brunovicco/policy-model-router) - this monorepo only references it, per the
extraction criterion in ADR-0003. It answers `POST /route` at http://localhost:8081 (mapped from
its container port 8000); pin the image with `POLICY_MODEL_ROUTER_VERSION` in `.env.example` when
bumping to a newer released tag.

Langfuse UI: http://localhost:3000, login `demo@credit-desk.local` / `demo-password-local-dev`
(from `.env.example`'s `LANGFUSE_INIT_USER_*`, auto-provisioned on first boot - no manual setup).

Datadog fan-out is opt-in (ADR-0006): set `OTEL_COLLECTOR_CONFIG=collector.datadog.yaml` plus
`DD_API_KEY`/`DD_SITE` before starting the stack.

Run the infrastructure-dependent test once the stack is healthy:

```bash
uv run pytest -m integration --no-cov
```

`--no-cov` avoids a spurious coverage-threshold failure: the repo's coverage gate (80%) is
calibrated for the full suite, and running only this one test naturally covers a small fraction of
`packages/*`. This test is excluded from the default `uv run pytest` (part of the quality gate) via
the `not integration` marker filter, so the gate never requires the compose stack to be running.

Tear down, including volumes:

```bash
docker compose -f infra/docker-compose.yml down -v
```

LiteLLM answers OpenAI-compatible completions at http://localhost:4000, proxying the 4 model groups
defined in `infra/litellm/config.yaml` (`fast-small`, `fast-structured-output`, `reasoning-medium`,
`reasoning-strong` - matches `credit_desk_contracts.enums.ModelGroup`, enforced by
`tests/unit/test_litellm_config.py`) to Groq and Anthropic. Set `GROQ_API_KEY`/`ANTHROPIC_API_KEY`
locally to make completions actually work; without them the proxy still starts and answers
`/health/liveliness`. No local vLLM deployment exists yet - this compose file does not stand up a
vLLM service, so the confidential-data local path from the blueprint is not built yet.

(The workload -> model group routing table itself lives in `policy-model-router`'s own repo as
`config/routing_policy.yaml`, not in this monorepo - see ADR-0003. `infra/litellm/config.yaml` only
handles provider routing *within* an already-selected group, per ADR-0004.)

`openfinance-br-mcp` (github.com/brunovicco/openfinance-br-mcp) is deliberately **not** wired into
this compose file yet, and it isn't a copy-paste of the `policy-model-router` pattern when it does
land:

- No published container image exists for it (unlike `policy-model-router`) - only a PyPI package
  (`uvx openfinance-br-mcp`) and its own `Dockerfile`. Wiring it here would need a pinned git-context
  `build:` (e.g. `https://github.com/brunovicco/openfinance-br-mcp.git#v0.2.0`), not an `image:`
  reference.
- Its default transport is `stdio`, meant to be spawned by an MCP client process, not run as a
  standing daemon. It also supports `MCP_TRANSPORT=streamable-http`, but `mcp_http_host` defaults to
  `127.0.0.1` *inside the container* - unreachable via Docker's published ports - so making it
  reachable at all requires `MCP_HTTP_HOST=0.0.0.0`. That in turn trips the server's own fail-closed
  config validator, which then requires either MCP client OAuth
  (`mcp_oauth_issuer_url`/`mcp_oauth_resource_server_url`) or a non-empty `MCP_HTTP_ALLOWED_ORIGINS`
  DNS-rebinding allowlist before the process will even start.

Neither OAuth nor a real origin allowlist has an honest value today - both describe a real MCP
client (an agent), and no `services/*` package exists yet. Wire this in once the first agent that
actually calls it exists, so those values are real instead of placeholders.

## Claude Code

- Run `/memory` to confirm loaded instructions.
- Run `/hooks` to inspect configured hooks.
- Run `claude doctor` from the shell for a read-only installation and configuration check. Reserve
  interactive `/doctor` for cases that may need guided repair, and review its requested commands.
- Use `/plan-change` before complex work.
- Use `/quality-gate` before completion.
- Use `/prepare-pr` to produce a reviewable PR description.

### Isolating riskier changes in a worktree

For a larger or harder-to-reverse change, add `isolation: worktree` to
`.claude/agents/python-implementer.md`'s frontmatter before delegating the change. The subagent
then works from a temporary git worktree branched off the default branch instead of editing the
working tree directly; the worktree is cleaned up automatically if it makes no changes. This is
not the harness default because it changes where edits land - add it deliberately for a specific
change you want to inspect before merging into your working tree, then remove it again, rather
than leaving it on for routine, well-scoped work.
