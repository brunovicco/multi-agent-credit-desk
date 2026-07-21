# ADR-0015: `decisao-agent` migrates its A2A executor to `Task`/`TaskUpdater`

- Status: Accepted
- Date: 2026-07-21
- Blueprint reference: ADR-002
- Supersedes: the "Execution pattern" section of
  `docs/adr/0013-decisao-agent-adopts-a2a-sdk.md`

## Context

ADR-0013 chose the immediate-`Message` pattern over `Task`/`TaskUpdater` because, at the time,
`credit_core` evaluation was the executor's only work: a fast, synchronous, in-process
computation with no genuine phases worth reporting incrementally. That ADR already anticipated
this decision would need revisiting: "The `Task`/`TaskUpdater` pattern is expected to become
necessary once a future milestone adds the `opinion_drafting` LLM workload."

`docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md` shipped that workload:
`EvaluateCreditApplicationUseCase.execute()` now performs two network round-trips (policy-model-
router, then LiteLLM) on the way to a completed evaluation. This is a real latency phase, not a
call that "completes in milliseconds" (ADR-0013's stated reasoning for immediate-`Message`), so
that reasoning no longer holds.

## Decision

`DecisaoAgentExecutor.execute()` (`services/decisao-agent/src/decisao_agent/entrypoints/
a2a_executor.py`) now follows the `Task`/`TaskUpdater` pattern:

- On the first message for a context, it creates a real `Task` via
  `new_task_from_user_message` and enqueues it.
- It reports `TASK_STATE_WORKING` (`TaskUpdater.start_work()`) before invoking the evaluation use
  case.
- On success, it attaches the `CreditOpinion` JSON body as a `credit_opinion` artifact and
  transitions to `TASK_STATE_COMPLETED` (`TaskUpdater.complete()`).
- On a domain error (invalid input, unknown critical flag, or any other
  `DecisaoAgentError`), it transitions to `TASK_STATE_FAILED` (`TaskUpdater.failed()`) with the
  same stable JSON error envelope (`{"code": ..., "message": ...}`) the batch CLI and the prior
  immediate-`Message` executor already used, carried in the task's terminal status message rather
  than a standalone `Message`.
- `cancel()` no longer unconditionally raises `UnsupportedOperationError`: a real, cancellable
  `Task` now exists, so `cancel()` publishes a cancellation through `TaskUpdater.cancel()` when the
  request carries a task/context ID, and only raises when it does not (a request with nothing to
  cancel). `DefaultRequestHandler` already short-circuits `tasks/cancel` for a task in a terminal
  state before this method is even reached (verified empirically: cancelling an already-completed
  task returns the unchanged, still-`TASK_STATE_COMPLETED` task without invoking the executor) -
  this ADR does not change or rely on that framework behavior, only on it being safe.

One degenerate case has no `Task` to report through: a request that carries no message at all
(`new_task_from_user_message` requires one). `execute()` falls back to enqueueing a standalone
error `Message` for that case only, unchanged from the immediate-`Message` pattern.

The request/response wire format (`TextPart` with `media_type="application/json"`, never
`DataPart`) is unchanged from ADR-0013; only the task lifecycle wrapping it changed.

## Consequences

`tasks/get` and `tasks/cancel` requests against `decisao-agent` - already generically routed by
`DefaultRequestHandler` - now behave meaningfully instead of targeting a task that never existed.
A client that only cares about the final result observes no behavior change: with
`ClientConfig(streaming=False, ...)`, `send_message` still yields exactly one response, now
carrying the completed `Task` instead of a bare `Message`, so the response body moves from
`response.message.parts` to `response.task.artifacts[...].parts` (success) or
`response.task.status.message.parts` (failure) - a breaking change for any existing caller that
inspected the raw protocol response shape, though none exists yet (no orchestrator is wired up).

Genuine mid-flight cancellation (cancelling a task while it is still `TASK_STATE_WORKING`, racing
the policy-model-router/LiteLLM round-trips) is not covered by an automated test. This was
investigated, not just assumed impractical: an event-gated fake `ModelRoutingPort` (blocking on an
`asyncio.Event` instead of sleeping, deterministic by construction) reliably drives
`DecisaoAgentExecutor.execute()` into `TASK_STATE_WORKING`, but observing that state
*client-side* through `a2a-sdk`'s streaming (`ClientConfig(streaming=True, ...)`) over
`httpx.ASGITransport` takes several seconds of wall-clock polling regardless of when the fake port
unblocks - the in-process ASGI transport does not appear to flush the first SSE chunk until the
event loop has idled through a number of scheduling passes. Pinning a test to that behavior would
substitute the fake port's determinism for a dependency on `ASGITransport`'s internal scheduling,
which is exactly the flakiness this project's testing guidance warns against
(`AGENTS.md`: "Avoid sleep-based synchronization and flaky retry loops"), not an improvement over
skipping the test. A real-subprocess variant (real TCP, real uvicorn, matching
`tests/integration/test_decisao_agent_a2a_server_roundtrip.py`'s pattern) might not share this
limitation but was not attempted, given the cost/value tradeoff for one already-narrow branch.

`cancel()`'s one deterministic, meaningfully-testable-in-isolation branch - rejecting a request
with no task/context ID - has a unit test; the terminal-task no-op path has a contract test against
the real SDK client/server machinery. The `TaskUpdater.cancel()` call itself
(`services/decisao-agent/src/decisao_agent/entrypoints/a2a_executor.py`'s `cancel()`, past the
guard) is unverified by this package's own tests and relies on `a2a-sdk`'s own test suite for
correctness - tracked as follow-up work, not a defect in this migration.

Separately, and generic to the `Task`/`TaskUpdater` pattern rather than specific to this
executor: `execute()` and `cancel()` each construct their own `TaskUpdater` for the same task,
so a `cancel()` that arrives after `execute()`'s coroutine has passed its last
cancellation-checkpoint `await` (i.e. after the use case returned but before
`updater.complete()` runs) could still enqueue a `TASK_STATE_COMPLETED` event after a
`TASK_STATE_CANCELED` one was already recorded. This is an SDK-level race inherent to the
pattern, not something this diff introduces or can resolve, but it is newly reachable now that a
real, persisted `Task` exists for it to affect.
