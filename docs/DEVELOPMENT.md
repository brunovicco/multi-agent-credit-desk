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

`infra/docker-compose.yml` stands up `policy-model-router` (ADR-0003/0004) plus the OTel Collector
and a self-hosted Langfuse v3 stack (Postgres, ClickHouse, MinIO, Redis, Langfuse worker/web), per
ADR-0006. Every credential in it is a fixed, local-only demo default from `.env.example` - never
real secrets, never meant to leave a local machine.

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

LiteLLM and `openfinance-br-mcp` are not part of this compose file yet - they land in a future step
once `litellm/config.yaml` has real content. (The workload -> model group routing table lives in
`policy-model-router`'s own repo as `config/routing_policy.yaml`, not in this monorepo - see
ADR-0003.)

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
