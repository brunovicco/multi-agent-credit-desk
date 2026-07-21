# decisao-agent

Executes the deterministic `credit_core` evaluation for one application snapshot and
cross-checks the result against `policy-mcp`'s catalog, so a decision can never be trusted
against a critical flag name or policy version `policy-mcp` does not itself recognize.

## Current scope: deterministic core, exposed two ways

This is the workspace's first package to consume both `credit_core` (directly, for evaluation)
and `policy-mcp` (over the real MCP protocol, as a client), and the workspace's first real A2A
agent. Both entrypoints share the exact same application/domain/adapters layers - only the
transport differs:

- **Batch CLI** (`python -m decisao_agent`): one `ApplicationSnapshotInput` JSON document on
  stdin, one `CreditOpinion` JSON document on stdout. See
  `docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md`.
- **A2A server** (`python -m decisao_agent.entrypoints.a2a_server`): the same JSON document,
  carried as a `TextPart` over the A2A protocol's `send_message`, advertised via an Agent Card
  declaring one skill, `evaluate_credit_application`. See
  `docs/adr/0013-decisao-agent-adopts-a2a-sdk.md`.

No orchestrator calls this yet; it is built and tested standalone, the same way `policy-mcp` and
`bureau-mcp` were.

## Why it reads `credit_core` directly

`decisao_agent` calls `credit_core.evaluation.evaluate_credit_application` directly instead of
re-implementing scoring or alçada logic. Only one module,
`decisao_agent.adapters.credit_core_evaluation_adapter`, imports `credit_core`; a regression
test AST-walks `domain/`, `application/`, and `entrypoints/` to fail the build if that boundary
is ever crossed - the same pattern `policy-mcp` established for reading `credit_core.policy`
(`docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md`).

## Why it queries `policy-mcp` before trusting a result

`ApplicationSnapshot.critical_flags` holds flag *names* rather than a decisao-agent-owned enum:
the closed set of valid names is `policy-mcp`'s catalog, not a third copy of
`credit_core.domain.CriticalFlag`'s taxonomy. Before evaluating,
`EvaluateCreditApplicationUseCase` fetches `policy-mcp`'s current critical flag names and policy
versions and rejects an unknown flag name or an evaluation result whose policy version
`policy-mcp` does not recognize - an integrity check against the two packages silently drifting
to different `credit_core` builds.

## Architecture

Clean Architecture, consistent with `docs/ARCHITECTURE.md`:

```text
services/decisao-agent/src/decisao_agent/
├── domain/        # ApplicationSnapshot, CreditOpinion, errors - decisao-agent's own vocabulary
├── application/    # CreditEvaluationPort + PolicyCatalogPort (protocols) + the evaluation use case
├── adapters/       # CreditCoreEvaluationAdapter (only module importing credit_core)
│                   # PolicyMcpClient (only module speaking the MCP protocol)
│                   # ModelRouterClient, LiteLLMClient (standalone, no use case consumes them yet)
└── entrypoints/    # errors.py (shared error codes), schemas.py (Pydantic wire schemas)
                    # __main__.py (batch CLI composition root)
                    # agent_card.py, a2a_executor.py, a2a_server.py (A2A composition root)
```

Both entrypoints depend only on `application.evaluate.EvaluateCreditApplicationUseCase` and the
same two adapters - adding the A2A surface changed nothing in `domain/`, `application/`, or
`adapters/`.

## LLM-drafted opinion clients (built standalone, not wired in yet)

`ModelRouterClient` and `LiteLLMClient` are two further adapters, built and tested standalone
before any use case consumes them - the same way `PolicyMcpClient` was in the milestone before
this one. They exist to support a future LLM-drafted parecer (`opinion_drafting`/`json_repair`
workloads, `docs/architecture-blueprint.md` section 2.2), not wired into
`EvaluateCreditApplicationUseCase` yet.

- `ModelRouterClient.route(request)` calls `policy-model-router`'s `POST /route`
  (`http://localhost:8081` by default, `DECISAO_AGENT_MODEL_ROUTER_BASE_URL` to override) with
  `credit_desk_contracts.routing.ModelRouteRequest`, returning a `ModelRouteDecision`. Verified
  field-for-field against the real service's own OpenAPI schema, not assumed from the shared
  contracts package alone - `tests/integration/test_model_router_client_live.py` asserts real,
  live routing behavior (`opinion_drafting` → `reasoning-strong`, `json_repair` →
  `fast-structured-output`) against a running container.
- `LiteLLMClient.complete(model, messages)` calls LiteLLM's OpenAI-compatible
  `POST /chat/completions` (`http://localhost:4000` by default,
  `DECISAO_AGENT_LITELLM_BASE_URL`/`LITELLM_MASTER_KEY` to override/authenticate), returning a
  `ChatCompletionResult`. **No real provider API key
  (`GROQ_API_KEY`/`ANTHROPIC_API_KEY`) is available in this environment**, so unlike
  `ModelRouterClient`, this adapter has no live-container integration test - only
  `tests/unit/test_litellm_client.py` against a fake `httpx` transport. A real completion has not
  been exercised end to end.

Both adapters translate every transport/HTTP/response-shape failure into a stable domain error
(`ModelRoutingUnavailableError`, `ChatCompletionUnavailableError`) - never a raw exception or
stack trace - the same translation discipline `PolicyMcpClient` established.

## Running: batch CLI

```bash
echo '{
  "annual_revenue": "5000000",
  "total_debt": "1200000",
  "monthly_debt_service": "40000",
  "monthly_operating_cash_flow": "180000",
  "bureau_score": "780",
  "years_in_operation": 6,
  "requested_amount": "500000",
  "critical_flags": []
}' | python -m decisao_agent
```

Prints exactly one JSON document to stdout: a `CreditOpinion` on success (exit `0`), or a stable
`{"code": ..., "message": ...}` error envelope on failure (exit `1`) - never a raw exception
message or stack trace either way. This mirrors how `policy-mcp` and `bureau-mcp` return a tool
error on the same channel as a tool result. stderr carries structured logs only.

## Running: A2A server

```bash
python -m decisao_agent.entrypoints.a2a_server
```

Binds `127.0.0.1:9999` by default (`DECISAO_AGENT_A2A_HOST`/`DECISAO_AGENT_A2A_PORT` to
override), serves the Agent Card at `/.well-known/agent-card.json`, and accepts `send_message`
requests carrying the same `ApplicationSnapshotInput` JSON document as a `TextPart` with
`media_type="application/json"` - not a `DataPart`, since `a2a-sdk`'s `DataPart` round-trips
through a protobuf `Struct` (double-precision floats), which would silently truncate `Decimal`
precision. See `docs/adr/0013-decisao-agent-adopts-a2a-sdk.md`.

Uses the "immediate response" execution pattern (a single `Message`, not a long-running `Task`
with status updates): credit evaluation is fast and synchronous, with no genuine work phases to
report. `cancel()` always raises `UnsupportedOperationError`, since no `Task` is ever created for
a cancellation request to target.

`PolicyMcpClient` (shared by both entrypoints) spawns `python -m policy_mcp` per call with a
30-second overall timeout by default; every failure mode (bad command, crashed or hung
subprocess, malformed response) is translated into `POLICY_CATALOG_UNAVAILABLE`, never a raw
exception or an unhandled traceback. Set `DECISAO_AGENT_POLICY_MCP_COMMAND` to override the
spawned command, e.g. for testing against a broken policy-mcp deliberately.

## Testing

```bash
uv run pytest services/decisao-agent
uv run pytest -m integration services/decisao-agent/tests/integration --no-cov
```

`tests/unit` covers the domain value objects, the `credit_core`-sourced adapter (a drift
regression against `evaluate_credit_application`), the `policy-mcp` MCP client against a fake
tool-call transport, `ModelRouterClient`/`LiteLLMClient` against a fake `httpx` transport, the
use case against fake ports, the schema mapping, the Agent Card, the architecture boundary (no
`credit_core` import outside its adapter), and `DecisaoAgentExecutor.cancel()`. `tests/contract`
exercises `DecisaoAgentExecutor` through the real `a2a-sdk` client/server machinery in-process
over an ASGI transport (no socket, no subprocess) - the same style as
`services/policy-mcp/tests/contract`. `tests/integration` spawns real subprocesses and real
containers: the CLI test spawns a real `policy-mcp` subprocess; the A2A test spawns the real
`python -m decisao_agent.entrypoints.a2a_server` bound to a real TCP port, which in turn spawns
its own real `policy-mcp` subprocess when a request arrives; `test_model_router_client_live.py`
requires `docker compose -f infra/docker-compose.yml up -d policy-model-router` beforehand (see
`docs/DEVELOPMENT.md`).
