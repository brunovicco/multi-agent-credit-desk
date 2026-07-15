# ADR-0009: Reuse existing MCP servers

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-007

## Decision

Do not write MCP servers from scratch when a mature option exists:

- **openfinance-br-mcp** (own, open-sourced) — customer banking data;
- **bureau-mcp** (new, small) — mock credit bureau (external score, negative records), justified
  because no equivalent exists;
- **policy-mcp** (new, small) — versioned catalog of credit policies queryable by agents.

**Mock transparency.** `openfinance-br-mcp` does not access the real Open Finance ecosystem (no
query account). Honest positioning in the README: "MCP protocol implementation over synthetic data
in the Open Finance BR format." The demonstrable value is the protocol implementation plus the BR
data model — and it becomes a point in favor: the full demo runs without any credential (neither
BCB nor Datadog).

## Consequences

Reuse demonstrates seniority; the two new MCP servers are small and domain-specific, not
reinvented infrastructure.
