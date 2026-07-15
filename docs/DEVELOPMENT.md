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
