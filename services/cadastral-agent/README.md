# cadastral-agent

Screens a company's KYC standing: fetches its bureau-mcp report and applies a small,
deterministic policy over the external score and any adverse records on file - `APPROVED`,
`COMMITTEE_REFERRAL`, or `BLOCKED`. It answers "is this company clean enough to proceed"; it does
not evaluate creditworthiness (`decisao-agent`'s job) and does not mutate anything.

## Current scope: deterministic core, CLI only

This package's first milestone, mirroring how `decisao-agent` itself started: a batch CLI reading
one CNPJ from stdin and writing one KYC assessment to stdout. No A2A surface yet.

## Why its KYC policy is not `sócios`/`situação fiscal` screening

`docs/architecture-blueprint.md` describes `cadastral-agent` as validating "dados cadastrais,
sócios, situação fiscal" (partners, fiscal status). No data source for that exists anywhere in
this workspace: `bureau-mcp`, the only real data source available, exposes a single tool,
`get_bureau_report(cnpj)`, returning only a CNPJ, an external score, and a list of adverse
records - see `services/bureau-mcp/README.md`. This package's KYC policy
(`cadastral_agent.domain.kyc_policy`) is scoped to what that data actually supports: a
`LAWSUIT`/`PROTEST` record blocks outright, an `OVERDUE_DEBT`/`BOUNCED_CHECK` record or a low
external score refers to committee review, otherwise the company is approved. There is no
external KYC/AML specification behind these thresholds; they were defined for this milestone and
are expected to be revisited once real requirements exist - see
`docs/adr/0016-cadastral-agent-kyc-screening-policy.md`. Document-based extraction
(`document_extraction`, the blueprint's LLM workload for this agent) is out of scope until a real
document input exists to extract from.

## Tool it consumes

| Server | Tool | Purpose |
|---|---|---|
| `bureau-mcp` | `get_bureau_report` | The sole source of KYC evidence: external score and adverse records. |

## Architecture

Clean Architecture, consistent with `docs/ARCHITECTURE.md`:

```text
services/cadastral-agent/src/cadastral_agent/
├── domain/        # BureauFinding, KycAssessment, kyc_policy - cadastral-agent's own vocabulary and rules
├── application/    # BureauReportPort (protocol) + AssessCadastralApplicationUseCase
├── adapters/       # BureauMcpClient: speaks the MCP protocol to a bureau-mcp subprocess
└── entrypoints/    # Pydantic wire schemas and the batch CLI composition root
```

`application` depends on a `BureauReportPort` protocol it defines, not on `BureauMcpClient`
directly - the same seam `decisao_agent.application.ports.PolicyCatalogPort` provides for
`PolicyMcpClient`. `domain.bureau_finding` is cadastral-agent's own copy of the vocabulary it
needs from bureau-mcp's report, not an import of `bureau_mcp.domain.report`: cadastral-agent
reaches bureau-mcp over the MCP protocol, as its own client, not as a Python dependency of its
domain layer.

## Running

```bash
echo '{"cnpj": "11.222.333/0001-81"}' | python -m cadastral_agent
```

Reads one `CnpjInput` JSON document from stdin, writes one JSON document to stdout: a
`KycAssessmentOutput` on success (exit `0`), or a stable
`{"code": ..., "message": ...}` error envelope on failure (exit `1`) - never a raw exception
message or stack trace either way. `BUREAU_MCP` is spawned as `python -m bureau_mcp` per call by
default; override the command via `CADASTRAL_AGENT_BUREAU_MCP_COMMAND`. stderr carries structured
logs only.

## Testing

```bash
uv run pytest services/cadastral-agent
uv run pytest -m integration services/cadastral-agent/tests/integration --no-cov
```

`tests/unit` covers the KYC policy (table-driven, including bureau-mcp's three fixture personas),
the use case against a fake port, the adapter's JSON-parsing helpers against hand-built
`CallToolResult`s, the wire schemas, and the Clean Architecture import boundary. `tests/integration`
spawns the packaged `python -m cadastral_agent` CLI over a real `python -m bureau_mcp` subprocess,
and proves `BureauMcpClient` translates real subprocess/transport failures.
