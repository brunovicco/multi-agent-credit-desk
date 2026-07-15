# LLM observability policy

This document states the project's policy for tracing LLM calls to Langfuse and for structured
application logging. As of Milestone 1 (workspace foundation), neither is implemented in this
repository: the concrete tracing adapter and logging bootstrap described below are planned for
`a2a-otel-kit`, a sibling library repository (see `docs/adr/0003-monorepo-with-extracted-libraries.md`
and `docs/adr/0010-claude-code-harness-as-base.md`), not yet built. This policy is recorded now so
that implementation follows it from the first line of code.

## Design principle

Tracing is opt-in and defaults to metadata only. The future observer implementation must return a
no-op observer whenever the tracing dependency is not installed or Langfuse credentials are not
set, so application code never needs to branch on whether tracing is enabled.

## Default behavior

- No prompt or completion content is sent to Langfuse unless `LANGFUSE_CAPTURE_CONTENT=true` is
  set explicitly.
- Only metadata is recorded by default: call name, model, latency, token counts, and a bounded
  allowlisted set of fields. Unknown, nested, content-bearing, and oversized metadata must be
  discarded.

## Enabling tracing

1. Confirm a business need for prompt/response-level debugging or evaluation that latency and
   token metrics alone do not satisfy.
2. Choose a Langfuse deployment: cloud (`https://cloud.langfuse.com` EU,
   `https://us.cloud.langfuse.com` US, `https://jp.cloud.langfuse.com` Japan,
   or the HIPAA-eligible region) or self-hosted.
3. Install the tracing dependency once `a2a-otel-kit` (or an equivalent local implementation) is
   consumed by this workspace.
4. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` from a secret manager
   or environment injection - never commit real values; `.env.example` documents the variable
   names only.
5. Keep `LANGFUSE_CAPTURE_CONTENT=false` unless the approval checklist below has been completed
   for this project.
6. Record the decision (scope, data classes, retention) in `docs/PRIVACY.md`.

## Approval checklist before enabling `LANGFUSE_CAPTURE_CONTENT=true`

- Named business and technical owner for the tracing data.
- Data classification of what a prompt or completion is expected to contain (PII, credentials,
  regulated data must not appear; if they can, redact at the call site before recording).
- Retention period configured in Langfuse and a deletion procedure.
- Access control for who can read traces in the Langfuse project.
- Non-production data used for any test or staging traces.
- Confirmation that no MCP tool output, secrets, or credentials can reach `prompt`/`completion`
  fields. The tracing adapter must allowlist metadata; when content capture is enabled the caller
  remains responsible for redacting the explicit `prompt` and `completion` values.

## Configuration reference

| Variable | Required | Purpose |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | to enable tracing | Project public key |
| `LANGFUSE_SECRET_KEY` | to enable tracing | Project secret key; environment-injected only |
| `LANGFUSE_BASE_URL` | no (defaults to EU cloud) | Cloud region or self-hosted URL |
| `LANGFUSE_CAPTURE_CONTENT` | no (defaults to `false`) | Set `true` only after the approval checklist |

## Uninstrumented by default

Leaving all four variables unset must keep the project fully untraced. This matches the harness's
MCP governance model: nothing external is connected until a project deliberately opts in.
