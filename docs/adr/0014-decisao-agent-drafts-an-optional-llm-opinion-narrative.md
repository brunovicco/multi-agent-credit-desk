# ADR-0014: `decisao-agent` drafts an optional, best-effort LLM opinion narrative

- Status: Accepted
- Date: 2026-07-21
- Blueprint reference: ADR-006

## Context

`ModelRouterClient` and `LiteLLMClient` (built standalone, no consumer, in the milestone before
this one) exist to support the LLM-drafted parecer described in
`docs/architecture-blueprint.md` section 2.2: `decisao-agent`'s `opinion_drafting` workload,
routed to `reasoning-strong`. This milestone wires them into
`EvaluateCreditApplicationUseCase`.

Two constraints shaped the design:

1. `docs/adr/0008-deterministic-core-without-llm.md` requires the credit decision to stay fully
   deterministic and reproducible; the blueprint's own framing is explicit: "LLM atua apenas nas
   bordas... redação do parecer" (LLM acts only at the edges - drafting the opinion). Whatever is
   built here must never let LLM availability, latency, or cost affect the deterministic
   `decision`, `total_score`, or any other field `CreditCoreEvaluationAdapter` already produces.
2. No real provider API key (`GROQ_API_KEY`/`ANTHROPIC_API_KEY`) is available in this
   environment (confirmed with the user before starting this milestone). Every code path that
   depends on a real completion must degrade gracefully, and no test can assert real generated
   prose - only the orchestration logic around a completion.

## Decision

### Best-effort, never blocking

`EvaluateCreditApplicationUseCase.execute()` computes the deterministic `CreditOpinion` exactly
as before, then attempts narrative drafting as a final, separate step. Drafting failure -
`ModelRoutingUnavailableError` or `ChatCompletionUnavailableError`, the same domain errors
`ModelRouterClient`/`LiteLLMClient` already raised in the prior milestone - is caught inside
`_draft_narrative()` and mapped to `narrative=None`. It is never re-raised, never logged as an
evaluation failure, and never changes `decision`, `total_score`, or any other field.
`CreditOpinion.narrative: str | None = None` makes "no narrative" an explicit, always-valid
state, not an error condition callers must special-case.

### Two new ports, defined now that a real consumer exists

`docs/adr/0013-decisao-agent-adopts-a2a-sdk.md` deferred defining `application/ports.py`
Protocols for `ModelRouterClient`/`LiteLLMClient` because no use case existed yet to shape the
real method signature. `EvaluateCreditApplicationUseCase` is now that consumer, so
`ModelRoutingPort`/`ChatCompletionPort` are added, matching `ModelRouterClient.route`/
`LiteLLMClient.complete` exactly. `ChatMessage`/`ChatCompletionResult` move from
`adapters.litellm_client` (where they were first defined, with no consumer) into
`application.ports` (where `ChatCompletionPort` now references them) - they are decisao-agent's
own generic chat vocabulary, unlike `ModelRouteRequest`/`ModelRouteDecision`, which remain
`credit_desk_contracts` types used verbatim (per the precedent already accepted in the prior
milestone's review: `credit_desk_contracts` is the workspace's shared, versioned contract layer,
not a single-producer package requiring translation).

Both new ports are optional constructor parameters on `EvaluateCreditApplicationUseCase`
(`model_routing_port: ModelRoutingPort | None = None`, `chat_completion_port: ChatCompletionPort
| None = None`). Providing neither (the default) skips drafting entirely - this keeps every
existing call site and test from the prior two milestones valid unchanged, and lets a caller
that has no routing/completion infrastructure available (e.g. a future automated test
environment) opt out cleanly rather than always paying two extra network round-trips that will
fail.

### Deriving the routing request without an orchestrator

`ModelRouteRequest` requires fields `decisao-agent` cannot get from a real workflow context
today, since no orchestrator exists yet:

- `workflow_id`/`task_id`: `EvaluateCreditApplicationUseCase.execute()` accepts them as optional
  keyword arguments, generating fresh ones (`uuid4()`) only when absent. The A2A server
  (`entrypoints.a2a_executor`) passes its real `RequestContext.context_id`/`task_id` - it already
  has genuine correlation IDs today, unlike the batch CLI, which has no workflow context at all
  and always falls back to fresh ones. A future orchestrator milestone would thread its own IDs
  through the same optional parameters, unchanged.
- `risk_level`: derived deterministically from `opinion.decision` (`APPROVAL_RECOMMENDED` ->
  `LOW`, ..., `BLOCKED`/`DECLINE` -> `CRITICAL`), defaulting to `HIGH` for any unmapped value -
  grounded in the actual evaluation outcome rather than a placeholder constant.
- `data_classification`: fixed at `CONFIDENTIAL`. Credit application financial data for a PJ
  applicant is sensitive by nature; no finer-grained classification input exists yet.
- `context_tokens_estimated`: computed from the actual prompt character length (`chars // 4`,
  a standard rough heuristic), not a fixed constant.
- `max_latency_ms`: fixed at 30s, matching the blueprint's own example routing-request metadata.
- `max_cost_usd`: fixed at $0.50, **not** the blueprint's generic $0.15 example. `opinion_drafting`
  always maps to `reasoning-strong` (policy-model-router's own workload table), its most
  expensive group; verified live against a real `policy-model-router` container that $0.15 makes
  every routing request fail with `no_viable_model_group` (`reasoning-strong`'s estimated cost
  already exceeds it), even with real infrastructure and real API keys. $0.50 was verified live
  to route successfully (`200 OK`, `selected_model_group: reasoning-strong`).

### Prompt design and `json_repair`

The prompt (`_build_opinion_messages`) instructs the model to draft prose from the
already-computed opinion's fields (score, decision, authority, reason codes, component
breakdown) without inventing or altering figures. Because no real completion can be exercised in
this environment, the exact wording is expected to need tuning once real credentials are
available - this is a first pass, not a validated prompt.

`json_repair` (`fast-structured-output`) is deliberately out of scope here: this milestone's
narrative is free text, not structured output requiring repair. It remains for a future
increment where structured LLM output is actually produced.

### Testing without real credentials

`tests/unit/test_evaluate.py` covers the use case's orchestration with fakes: narrative
attached on success, `None` when either port is unset, `None` when routing fails, `None` when
completion fails - and asserts the deterministic `decision` is unaffected in every failure case.
No new live integration test asserts real generated prose, consistent with
`LiteLLMClient`'s existing limitation from the prior milestone.

## Consequences

`decisao-agent`'s two entrypoints (CLI, A2A server) now always attempt narrative drafting -
`CreditCoreEvaluationAdapter`/`PolicyMcpClient` wiring is unchanged, and
`ModelRouterClient()`/`LiteLLMClient()` are constructed with their own defaults (real local
compose URLs). In this environment, both entrypoints will produce `narrative=None` for every
request, because no real provider key is configured - this is expected, not a defect, and will
resolve automatically once real credentials and the compose stack are both present, with zero
code changes.

`DecisaoAgentExecutor` has since migrated from the immediate-`Message` pattern to
`Task`/`TaskUpdater` (`docs/adr/0015-decisao-agent-migrates-to-task-taskupdater.md`), reporting
`TASK_STATE_WORKING` during the latency this milestone introduced.
