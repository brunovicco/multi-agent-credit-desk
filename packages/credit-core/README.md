# credit-core

Deterministic credit scoring, approval-authority policy, and blocking rules for the Multi-Agent
Credit Desk. Zero LLM in the decision path - see `docs/adr/0008-deterministic-core-without-llm.md`.

## Import policy

`credit_core` allows only standard-library imports and imports of itself. Every third-party
import, every other workspace package, and dynamic import mechanisms (`importlib`, `__import__`)
are rejected by default. This is enforced by `scripts/validate_architecture.py` and documented in
`.claude/rules/credit-core.md` - it is not a convention to remember, it is a build-breaking check.
This package also uses only absolute imports (`from credit_core.module import Member`), never
relative imports, and never `from __future__ import annotations`; both are covered by a regression
test in `tests/test_import_isolation.py` in addition to the shared architecture check.

## ⚠️ `DEMO_POLICY_V1` is a synthetic demonstration policy, not a production credit policy

Every weight, score band, decision threshold, and approval-authority amount shipped in
`credit_core.policy.DEMO_POLICY_V1` is **invented for this project's tests and demonstrations**.
The architecture blueprint deliberately does not specify numeric thresholds or weights for a real
credit policy - see `docs/architecture-blueprint.md`. Nothing in this package should be read,
copied, or deployed as an actual credit risk policy. The name `credit-core-demo-policy-v1`
(`DEMO_POLICY_V1.version`) is chosen specifically so it cannot be mistaken for a production policy
version in a trace, a log, or an evidence bundle.

## Domain model

| Type | Kind | Purpose |
|---|---|---|
| `CreditApplicationSnapshot` | frozen dataclass | Immutable input: revenue, debt, debt service, cash flow, bureau score, years in operation, requested amount, critical flags. |
| `CreditPolicy` | frozen dataclass | Versioned policy configuration: component weights/bands, decision thresholds, authority thresholds. Holds no logic. |
| `ScoreComponentPolicy` / `ScoreBand` / `ScoreDirection` | frozen dataclass / enum | One component's weight, direction (`HIGHER_IS_BETTER` / `LOWER_IS_BETTER`), and ordered boundary→score bands. |
| `ComponentScore` | frozen dataclass | One component's metric value, raw score, weight, and weighted score. |
| `CreditEvaluationResult` | frozen dataclass | The full evaluation outcome: policy version, total score, component breakdown, decision, approval authority, reason codes, blocking reasons. |
| `ScoreComponent` | enum | `BUREAU_SCORE`, `LEVERAGE_RATIO`, `DEBT_SERVICE_COVERAGE`, `OPERATING_HISTORY`. |
| `Decision` | enum | `APPROVAL_RECOMMENDED`, `CONDITIONAL_APPROVAL`, `COMMITTEE_REFERRAL`, `DECLINE`, `BLOCKED`. |
| `ApprovalAuthority` | enum | `NONE`, `ANALYST`, `SENIOR_ANALYST`, `CREDIT_COMMITTEE`, `EXECUTIVE_BOARD`. |
| `CriticalFlag` | enum | `BANKRUPTCY_FILING`, `SEVERE_PAYMENT_DEFAULT`, `FRAUD_ALERT` - synthetic red flags. |
| `ReasonCode` | enum | Stable, deterministic reason codes for every decision, authority, and block outcome. |

The single pure entrypoint is `evaluate_credit_application(snapshot, policy=DEMO_POLICY_V1)` in
`credit_core.evaluation`. Given an equal snapshot and policy, it always returns an equal result:
no I/O, no clock, no randomness, no logging.

All monetary, ratio-bearing, weight, score, threshold, and sentinel values are validated at
runtime as finite `Decimal` instances before evaluation. `float`, `NaN`, and positive or negative
infinity are rejected with domain-specific errors. `years_in_operation` must be an actual `int`
(not `bool`), and `critical_flags` must be a `frozenset` containing only `CriticalFlag` members.

## Decision precedence

1. **Critical blocking rules always take precedence.** If `snapshot.critical_flags` is non-empty,
   `decision` is `BLOCKED` and `approval_authority` is `NONE`, regardless of the total score - a
   perfect score does not override a critical flag. The score and its full component breakdown
   are still computed and returned, so the result stays fully auditable.
2. Otherwise, the total score decides `decision` via `DEMO_POLICY_V1`'s thresholds (all
   minimum-inclusive): `>= 80` approval recommended, `>= 60` conditional approval, `>= 40`
   committee referral, below `40` decline. `APPROVAL_RECOMMENDED` is a score outcome, not a claim
   that human authority is bypassed; `approval_authority` remains the separate authorization axis.
3. For approval decisions, `approval_authority` is derived from `snapshot.requested_amount` (all
   maximum-inclusive): `<= 50,000` analyst, `<= 250,000` senior analyst, `<= 1,000,000` credit
   committee, above that executive board. `COMMITTEE_REFERRAL` always requires at least
   `CREDIT_COMMITTEE`, even when the requested amount would otherwise fall within analyst or senior
   analyst authority; amounts above the committee limit require `EXECUTIVE_BOARD`. `decision` in
   `{DECLINE, BLOCKED}` always yields `ApprovalAuthority.NONE`.

## Scoring

Each of the four components produces a raw score in `{0, 20, 40, 60, 80, 100}` from an ordered
set of bands, then is weighted (weights sum to exactly `Decimal("1.00")`):

| Component | Weight | Direction | Metric |
|---|---|---|---|
| Bureau score | 0.40 | higher is better | `bureau_score`, 0–1000 scale |
| Leverage ratio | 0.25 | lower is better | `total_debt / annual_revenue` |
| Debt-service coverage | 0.25 | higher is better | `monthly_operating_cash_flow / monthly_debt_service` |
| Operating history | 0.10 | higher is better | `years_in_operation` |

**Zero debt-service edge case:** the coverage ratio is undefined when `monthly_debt_service` is
zero. The policy defines this explicitly as "no debt service obligation ⇒ maximum favorable
coverage": the metric is set to `DEMO_POLICY_V1.zero_debt_service_metric_value` (`999`), which
lands in the top coverage band. This sentinel value is reported transparently in
`ComponentScore.metric_value`, never hidden.

Policy validation requires `zero_debt_service_metric_value` to be finite, positive, and greater
than or equal to the top debt-service-coverage band boundary. A custom policy cannot silently map
the zero-debt-service edge case to a less favorable band.

### Decimal quantization strategy

All monetary amounts, ratios, weights, and scores are `Decimal`; no `float` appears in the
decision path. Evaluation runs inside a private local decimal context with precision `28` and
`ROUND_HALF_EVEN`, so caller changes to the process or task's decimal context cannot change a
score. The global decimal context is never modified. Every weighted component score is quantized
to `credit_core.policy.SCORE_QUANTUM` (`Decimal("0.01")`) using `ROUND_HALF_EVEN` (banker's
rounding). `total_score` is the exact sum of those already-quantized weighted scores, re-quantized
once more with the same unit and rounding mode as a defensive final step. There is no other
rounding anywhere in the evaluation path, and
`sum(component.weighted_score for component in result.component_scores) == result.total_score`
holds exactly for every result.

## Reason codes

`reason_codes` (populated unless blocked) always contains exactly two codes: one explaining the
score-based decision, one explaining the approval-authority assignment (or the absence of one).
`blocking_reasons` (populated only when blocked) contains one code per critical flag present on
the snapshot, sorted by flag name for determinism.

| Reason code | Meaning |
|---|---|
| `SCORE_MEETS_APPROVAL_RECOMMENDATION_THRESHOLD` | Total score `>= 80`; approval is recommended, subject to the reported authority. |
| `SCORE_MEETS_CONDITIONAL_APPROVAL_THRESHOLD` | Total score `>= 60` and `< 80`. |
| `SCORE_MEETS_COMMITTEE_REFERRAL_THRESHOLD` | Total score `>= 40` and `< 60`. |
| `SCORE_BELOW_COMMITTEE_REFERRAL_THRESHOLD` | Total score `< 40`; decision is decline. |
| `REQUESTED_AMOUNT_WITHIN_ANALYST_AUTHORITY` | Requested amount `<= 50,000`. |
| `REQUESTED_AMOUNT_WITHIN_SENIOR_ANALYST_AUTHORITY` | Requested amount `<= 250,000`. |
| `REQUESTED_AMOUNT_WITHIN_CREDIT_COMMITTEE_AUTHORITY` | Requested amount `<= 1,000,000`. |
| `REQUESTED_AMOUNT_REQUIRES_EXECUTIVE_BOARD_AUTHORITY` | Requested amount `> 1,000,000`. |
| `COMMITTEE_REFERRAL_REQUIRES_CREDIT_COMMITTEE_AUTHORITY` | Score-based committee referral raises the minimum authority to credit committee. |
| `NO_APPROVAL_AUTHORITY_DECISION_NOT_APPROVED` | Decision is decline or blocked. |
| `CRITICAL_FLAG_BANKRUPTCY_FILING` | `CriticalFlag.BANKRUPTCY_FILING` present. |
| `CRITICAL_FLAG_SEVERE_PAYMENT_DEFAULT` | `CriticalFlag.SEVERE_PAYMENT_DEFAULT` present. |
| `CRITICAL_FLAG_FRAUD_ALERT` | `CriticalFlag.FRAUD_ALERT` present. |

## Example

```python
from decimal import Decimal

from credit_core import CreditApplicationSnapshot, evaluate_credit_application

snapshot = CreditApplicationSnapshot(
    annual_revenue=Decimal("1000000"),
    total_debt=Decimal("300000"),
    monthly_debt_service=Decimal("10000"),
    monthly_operating_cash_flow=Decimal("25000"),
    bureau_score=Decimal("850"),
    years_in_operation=12,
    requested_amount=Decimal("30000"),
)

result = evaluate_credit_application(snapshot)  # uses DEMO_POLICY_V1 by default
result.decision            # Decision.APPROVAL_RECOMMENDED
result.approval_authority  # ApprovalAuthority.ANALYST
result.total_score          # Decimal("100.00")
```

A critically flagged applicant, even with the same inputs, is blocked regardless of score:

```python
from dataclasses import replace

from credit_core import CriticalFlag

flagged = replace(snapshot, critical_flags=frozenset({CriticalFlag.FRAUD_ALERT}))
result = evaluate_credit_application(flagged)
result.decision            # Decision.BLOCKED
result.approval_authority  # ApprovalAuthority.NONE
result.total_score          # Decimal("100.00") - still computed, still auditable
```

## Testing

```bash
uv run pytest packages/credit-core
```

`tests/` covers the full decision truth table (healthy, leveraged, critically flagged, and
critical-block-overrides-perfect-score scenarios), exact score and approval-authority boundaries,
the zero-debt-service edge case, invalid inputs and invalid policy configurations, determinism,
immutability, Decimal-only calculation, component-breakdown-sums-to-total, policy version
presence, runtime rejection of non-Decimal and non-finite values, coherent committee-referral
authority, zero-debt-service sentinel validation, and import isolation (no
third-party/cross-workspace imports, no relative imports, no `from __future__ import annotations`).
