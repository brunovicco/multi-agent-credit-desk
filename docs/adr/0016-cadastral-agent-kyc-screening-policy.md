# ADR-0016: `cadastral-agent`'s KYC screening policy is scoped to what bureau-mcp actually provides

- Status: Accepted
- Date: 2026-07-21
- Blueprint reference: ADR-002

## Context

`docs/architecture-blueprint.md` section 2.2 describes `cadastral-agent` as: "KYC/KYB: valida
dados cadastrais, sócios, situação fiscal" (validates registration data, partners, fiscal
status), consuming `bureau-mcp`. No data source for "sócios" (partners/shareholders) or "situação
fiscal" (tax/fiscal status) exists anywhere in this workspace: `bureau-mcp`
(`docs/adr/0009-reuse-existing-mcp-servers.md`) exposes exactly one tool,
`get_bureau_report(cnpj)`, returning only `{cnpj, external_score, negative_records}` - a company's
external bureau score and a list of adverse records (`PROTEST`, `LAWSUIT`, `BOUNCED_CHECK`,
`OVERDUE_DEBT`). Building `cadastral-agent` against the blueprint's full aspirational scope would
mean inventing not just a policy but entire data model and source that nothing else in the
project has ever specified or validated.

## Decision

`cadastral-agent`'s first milestone screens KYC standing using only what `bureau-mcp` provides:
a small, deterministic policy (`cadastral_agent.domain.kyc_policy`) over the external score and
adverse-record categories, producing one of three decisions:

- `BLOCKED`: any `LAWSUIT` or `PROTEST` record on file - the two record kinds representing an
  active, unresolved legal/financial dispute serious enough that no further screening should
  proceed.
- `COMMITTEE_REFERRAL`: any `OVERDUE_DEBT` or `BOUNCED_CHECK` record on file, or
  `external_score` below `600` (bureau-mcp's 0-1000 scale) - adverse signals that warrant human
  review rather than an outright block.
- `APPROVED`: a clean record and a score at or above `600`.

These thresholds have no external KYC/AML specification behind them - they were defined for this
milestone, deliberately mirroring `credit_core`'s pattern of a small, explicit, table-testable
rule set rather than a scoring formula. Every reason code the policy can emit
(`LAWSUIT_ON_FILE`, `PROTEST_ON_FILE`, `OVERDUE_DEBT_ON_FILE`, `BOUNCED_CHECK_ON_FILE`,
`LOW_EXTERNAL_SCORE`) is verified against bureau-mcp's three fixture personas
(`services/bureau-mcp/src/bureau_mcp/adapters/synthetic_bureau_source.py`): the healthy persona
resolves to `APPROVED` with no reason codes, the leveraged persona to `COMMITTEE_REFERRAL`, and
the negative-history persona to `BLOCKED`.

`document_extraction` (the blueprint's LLM workload for this agent, presumably for extracting
`sócios`/fiscal data from an uploaded document) is out of scope: no document input source or
format exists anywhere in this project to extract from, unlike `decisao-agent`'s narrative
drafting (ADR-0014), which had a concrete, already-computed input (the deterministic
`CreditOpinion`) to describe. Adding it now would mean inventing both the extraction target and
its data source with no real requirement driving either.

Architecturally, `cadastral-agent` mirrors `decisao-agent`'s established shape: `application`
depends on a consumer-defined `BureauReportPort` protocol, implemented by `BureauMcpClient`
(spawns `python -m bureau_mcp` over stdio per call, translating bureau-mcp's own `INVALID_CNPJ`/
`CNPJ_NOT_FOUND` tool-error codes into domain errors, and any other transport/subprocess failure
into `BureauReportUnavailableError`). `domain.bureau_finding` is cadastral-agent's own copy of the
report vocabulary it needs, not an import of `bureau_mcp.domain.report` - the same reasoning
`decisao_agent.application.ports.PolicyCatalogSnapshot` follows for policy-mcp: an MCP client
reaches its server over the protocol, not as a Python dependency of its own domain layer.

## Consequences

`cadastral-agent` ships a real, testable KYC screening core and a batch CLI
(`python -m cadastral_agent`), consistent with how `decisao-agent` itself began (CLI first, A2A
surface deferred). The gap between this policy and the blueprint's "sócios, situação fiscal"
language is real and intentional, not an oversight: closing it would require a new, separately
reviewed data source (a real or synthetic system of record for partners/fiscal status), which does
not exist today and is not implied by any other work in this repository. No agent or orchestrator
consumes `cadastral-agent` yet; it is built and tested standalone, the same way `bureau-mcp` and
`decisao-agent`'s first milestones were.
