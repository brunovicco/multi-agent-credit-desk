# Privacy and data handling

Complete this document before processing personal or regulated data.

## Data inventory

| Data category | Source | Purpose | Legal/contractual basis | Destination | Retention | Deletion method |
|---|---|---|---|---|---|---|
| None documented | | | | | | |

## Controls

- Data minimization:
- Access control:
- Encryption in transit:
- Encryption at rest:
- Masking/tokenization:
- Non-production data strategy:
- Logging and tracing restrictions: see `docs/LLM_OBSERVABILITY.md` for the Langfuse opt-in policy; record here whether this project has enabled `LANGFUSE_CAPTURE_CONTENT` and the approval date.
- Data-subject deletion/anonymization:
- External processors:
- Incident-response owner:

## Prohibited logging

Secrets, authentication headers, personal identifiers, full financial identifiers, complete request/response payloads, prompts, and model outputs containing sensitive data.
