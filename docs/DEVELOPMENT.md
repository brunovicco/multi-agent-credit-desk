# Development guide

## Setup

```bash
uv sync --frozen
```

## Run checks

```bash
uv run ruff check .
uv run ruff format --check .
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

`Dockerfile` is a multi-stage, uv-based build: a `builder` stage installs the locked
dependencies and builds the package, then only the resulting virtualenv and source are copied
into a slim, non-root runtime image. The shipped `CMD` is a placeholder — this harness is
framework-agnostic and does not assume an ASGI app, CLI, or worker loop. Replace it with the
project's real entrypoint. Adjust `.dockerignore` if new top-level files or directories need to
be excluded from the build context.

## Local configuration

Copy `.env.example` only when the application supports local dotenv loading. Never commit `.env` or real credentials.

## Claude Code

- Run `/memory` to confirm loaded instructions.
- Run `/hooks` to inspect configured hooks.
- Run `/doctor` when configuration is not loading.
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
