# ADR-0013: `decisao-agent` adopts `a2a-sdk` for its A2A surface

- Status: Accepted
- Date: 2026-07-20
- Blueprint reference: ADR-002

## Context

`docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md` shipped `decisao-agent`'s
deterministic evaluation logic (`credit_core` + policy-mcp cross-check) as a batch CLI only,
deliberately deferring the A2A protocol surface: no A2A SDK was pinned anywhere in this workspace,
and choosing one is a dependency decision that needed its own review (maintenance, license,
provenance, vulnerabilities) before being pinned.

## Decision

### SDK choice: `a2a-sdk`

`a2a-sdk` (PyPI, `services/decisao-agent/pyproject.toml`'s `a2a-sdk[http-server]>=1.1,<2`) is
adopted over the independent community package `python-a2a`:

| Criterion | `a2a-sdk` | `python-a2a` |
|---|---|---|
| Provenance | Official SDK of the A2A project. Google donated the protocol to the Linux Foundation in June 2025; governed today by a Technical Steering Committee (AWS, Cisco, Google, IBM Research, Microsoft, Salesforce, SAP, ServiceNow). | Independent implementation by a single maintainer, not affiliated with the official project. |
| Version at adoption | 1.1.1 (2026-07-16), implements A2A Protocol Spec 1.0. | 0.5.10 (2025-09-06). |
| License | Apache 2.0. | MIT. |
| Known CVEs | None found (NVD, GitHub Advisory Database, PSF advisory database searched). | Not evaluated - not a serious candidate given the above. |

No other candidate was evaluated as seriously maintained or officially affiliated.

### Wire format: `TextPart`, not `DataPart`

The installed SDK's `DataPart` (`a2a.helpers.proto_helpers.new_data_part`) round-trips arbitrary
JSON through a protobuf `google.protobuf.Struct`, whose numeric fields are IEEE 754 double
(verified empirically: `new_data_part({"a": 1})` round-trips as `{"a": 1.0}` through
`get_data_parts`). This is unacceptable for this project's `Decimal`-typed monetary and score
fields (`.claude/rules/python.md`: "Use `Decimal` for monetary values"). `entrypoints.schemas`
already serializes `Decimal` fields as JSON strings via Pydantic's `model_dump_json()` (verified:
`Decimal("1000000.123456789012345")` serializes to the string `"1000000.123456789012345"`, not a
JSON number), matching the batch CLI's existing wire format exactly.

`decisao_agent.entrypoints.a2a_executor` therefore carries the identical JSON document the CLI
already reads/writes as a `TextPart` with `media_type="application/json"`
(`a2a.helpers.proto_helpers.new_text_message`/`get_message_text`), never a `DataPart`. A plain
protobuf string field is transported verbatim with no precision loss.

### Execution pattern: immediate `Message`, not `Task` + `TaskUpdater` (superseded)

`AgentExecutor.execute()`'s own contract documents two allowed workflows: "Immediate response:
Enqueue a SINGLE `Message` object" or "Asynchronous/long-running: Enqueue a `Task`... emit
`TaskStatusUpdateEvent`/`TaskArtifactUpdateEvent` over time." At adoption, `credit_core` evaluation
was a fast, synchronous, in-process computation with no genuine work phases, no I/O to await beyond
the policy-mcp cross-check, and nothing to report incrementally - so `DecisaoAgentExecutor` used
the immediate-`Message` pattern, and `cancel()` always raised
`a2a.types.UnsupportedOperationError` since no `Task` ever existed to target.

**Superseded by `docs/adr/0015-decisao-agent-migrates-to-task-taskupdater.md`**: once
`docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md` added a genuine,
non-trivial latency phase (two network round-trips), the executor migrated to `Task`/`TaskUpdater`
as this section already anticipated below.

### Two composition roots, not one selectable transport

Unlike `policy-mcp`/`bureau-mcp`, whose single `python -m <pkg>` entrypoint selects an MCP
transport (`stdio`/`sse`/`streamable-http`) via an environment variable, `decisao-agent` keeps its
existing batch CLI (`python -m decisao_agent`, one-shot, reads stdin once and exits) and its new
A2A server (`python -m decisao_agent.entrypoints.a2a_server`, a long-running daemon bound to a
host/port) as two separate composition roots. These are different process shapes, not different
transports of the same process, so unifying them behind one entrypoint would obscure rather than
clarify the difference.

## Consequences

`decisao-agent` is now reachable as a real A2A agent, advertising one skill
(`evaluate_credit_application`) via its Agent Card, while remaining exactly as deterministic and
precision-safe as the batch CLI it wraps - both entrypoints share the same
`EvaluateCreditApplicationUseCase`, `CreditCoreEvaluationAdapter`, and `PolicyMcpClient` built in
ADR-0012, and the same stable error codes (`decisao_agent.entrypoints.errors`).

`a2a-sdk[http-server]` pulls in `google-api-core`, `httpx`, `json-rpc`, and `protobuf` as new
transitive dependencies. `uvicorn` was already a transitive dependency of `mcp` (which
`decisao-agent` already depended on), so no new server runtime was introduced.

No orchestrator exists yet to discover or call this Agent Card. The LLM-drafted parecer
(`opinion_drafting` workload) shipped in ADR-0014; `json_repair` remains a separate, future
milestone.
