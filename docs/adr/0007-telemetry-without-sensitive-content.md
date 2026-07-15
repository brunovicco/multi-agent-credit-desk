# ADR-0007: Telemetry without sensitive content by default

- Status: Accepted
- Date: 2026-07-15
- Blueprint reference: ADR-005

## Decision

Prompts, responses, documents, and customer data are not sent in full to telemetry. What is
recorded: hashes, sizes, token counts, data classification, metadata, and a reference to the
artifact stored under controlled access. Full content capture is configurable per environment
(`TELEMETRY_CAPTURE_CONTENT`), disabled by default.

## Consequences

Consistent with LGPD/LC 105 even in a demo. Deep debugging uses the artifact store, not telemetry.
