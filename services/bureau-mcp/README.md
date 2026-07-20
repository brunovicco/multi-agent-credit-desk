# bureau-mcp

A small, read-only MCP server that exposes a synthetic credit-bureau report (external score,
negative records) for a fixed set of demo companies. It answers "what does the bureau say about
this CNPJ" for any MCP-capable client; it does not evaluate applications and does not mutate
anything - see `docs/adr/0009-reuse-existing-mcp-servers.md`.

No agent consumes this server yet (`cadastral-agent`/`risco-agent` do not exist in this
repository today). It is built and tested standalone, the same way `services/policy-mcp` was.

## Why its data is synthetic and fixed

Unlike `policy-mcp`, which reads `credit_core` directly so its catalog can never drift from a
real system of record, bureau-mcp has no equivalent: **no real credit-bureau connection exists
or is planned to exist without an explicit, separately reviewed integration.** This server's
adapter, `bureau_mcp.adapters.synthetic_bureau_source.SyntheticBureauSource`, *is* bureau-mcp's
system of record - a small, fixed, in-memory dataset of three demo personas from
`docs/architecture-blueprint.md`, keyed by a synthetic, structurally valid (Receita Federal
mod-11 checksum) CNPJ that does not identify a real company:

| Persona | CNPJ | External score | Negative records |
|---|---|---|---|
| Saudável (healthy) | `11.222.333/0001-81` | 850 | none |
| Alavancada (leveraged) | `22.333.444/0001-81` | 520 | one overdue debt |
| Negativada (negative-history) | `33.444.555/0001-81` | 180 | one protest, one lawsuit |

## ⚠️ This is a synthetic demo dataset, not a real credit-bureau feed

Every score and negative record this server reports is **invented for this project's tests and
demonstrations**. Nothing served by `bureau-mcp` should be read, copied, or treated as an actual
credit-bureau lookup for a real company.

## Tool

| Tool | Input | Output |
|---|---|---|
| `get_bureau_report` | `cnpj: str` (punctuated or digits-only) | `BureauReport`: the CNPJ, external score, and every negative record on file. Returns `INVALID_CNPJ` for a CNPJ that fails format/checksum validation, or `CNPJ_NOT_FOUND` for a well-formed CNPJ outside the fixed dataset - neither error echoes the raw input back, since a CNPJ identifies a specific company. |

## Architecture

Clean Architecture, consistent with `docs/ARCHITECTURE.md`:

```text
services/bureau-mcp/src/bureau_mcp/
├── domain/        # BureauReport, NegativeRecord, CNPJ mod-11 validation - bureau-mcp's own vocabulary
├── application/    # BureauLookupPort (protocol) + BureauReportQueries (use case)
├── adapters/       # SyntheticBureauSource: the fixed synthetic dataset, bureau-mcp's system of record
└── entrypoints/    # Pydantic wire schemas, the MCP server composition root, and the CLI entrypoint
```

`application` depends on a `BureauLookupPort` protocol it defines, not on `SyntheticBureauSource`
directly, keeping the current single adapter swappable for a real bureau integration later,
should one ever be reviewed and approved.

## Running

```bash
python -m bureau_mcp
```

Transport is selected via `BUREAU_MCP_TRANSPORT` (default `stdio`); an unrecognized value fails
fast at startup rather than silently defaulting.

## Testing

```bash
uv run pytest services/bureau-mcp
uv run pytest -m integration services/bureau-mcp/tests/integration --no-cov
```

`tests/unit` covers CNPJ validation, the domain-to-wire-schema mapping, the synthetic dataset (all
three personas plus an unknown-CNPJ path), and the application queries against a fake port.
`tests/contract` exercises the tool through the MCP SDK's in-process client/server session
machinery. `tests/integration` spawns the packaged `python -m bureau_mcp` CLI over stdio for one
real MCP handshake and tool call end to end.
