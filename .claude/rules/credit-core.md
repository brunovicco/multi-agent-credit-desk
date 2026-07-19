---
paths:
  - "packages/credit-core/**/*.py"
---

# credit-core determinism rules

- `credit_core` is a pure deterministic package: it may import only the Python standard library
  and itself. Every third-party import and every other workspace package is rejected by default -
  this is not an enumerated denylist, it is default-deny.
- Dynamic import mechanisms (`importlib`, `__import__`) are explicitly forbidden, even though
  `importlib` is part of the standard library, because both exist to bypass static import
  analysis.
- Enforced by `scripts/validate_architecture.py`; do not bypass or narrow that check without
  explicit approval. See `docs/adr/0008-deterministic-core-without-llm.md`.
- No network calls, no filesystem I/O beyond what tests explicitly isolate, no wall-clock or
  random calls without injected determinism.
- Prefer stdlib and `Decimal`/`dataclass` value objects; treat any perceived need for a new
  dependency as a signal to stop and confirm scope before adding one.
