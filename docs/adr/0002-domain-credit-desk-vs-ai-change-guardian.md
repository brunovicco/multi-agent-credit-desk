# ADR-0002: Choose the credit desk domain over an AI change guardian

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-000

## Context

Two candidate domains offered the same engineering content (A2A, MCP, model routing,
observability): software change review ("AI Change Guardian") and credit analysis for Brazilian
legal entities (pessoas jurídicas, PJ) ("Credit Desk").

## Decision

Credit Desk.

Rationale:

1. Alignment with the author's professional narrative (20+ years in banking/financial services in
   Brazil) and target roles (BTG, EY, regulated institutions).
2. Direct reuse of the already open-sourced Open Finance BR MCP Server - a differentiator no
   generic demo has.
3. The credit domain forces the most interesting requirements: data classification (LGPD, LC
   105/2001), local-vs-external model constraints, deterministic approval-authority decisions, and
   an audit trail.
4. AI code review is a saturated space; a credit desk with A2A and distributed tracing is
   practically unprecedented as a public demo.

## Consequences

Customer data will be synthetic (mock BCB Open Finance). The README must state explicitly that
this is a demonstration environment. The ease of demoing against real GitHub PRs is lost -
accepted.
