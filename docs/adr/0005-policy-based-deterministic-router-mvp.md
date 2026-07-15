# ADR-0005: Policy-based deterministic router for the MVP

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-003

## Context

The original proposal included a weighted score function
(`capability_fit × 0.35 + expected_quality × 0.25 + ...`). Terms such as `expected_quality` and
`historical_success` require evaluation data that does not exist on day 1.

## Decision

The MVP routes in two steps:

1. **Mandatory (eliminatory) constraints:** data classification, processing location, local vs.
   external, structured output, tool calling, context window, maximum cost, maximum latency,
   availability, per-agent allowlist.
2. **Declarative `workload → model_group` table** (versioned YAML).

The decision-record format (with `rejected_candidates` and reasons) is in place from day 1. The
weighted score function is deferred to Phase 3, once per-workload evaluation data exists.

## Consequences

A router that is 100% explainable and testable via a truth table. No invented numbers pretending
to be engineering.
