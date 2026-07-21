"""decisao-agent's own vocabulary for a credit application snapshot.

A frozen, immutable Value Object: a plain data holder with no behavior beyond structural
equality, no I/O, and no framework types. It intentionally mirrors the shape of
``credit_core.domain.CreditApplicationSnapshot`` without importing that type - the translation
happens once, at the adapter boundary in
``decisao_agent.adapters.credit_core_evaluation_adapter``, per
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``.

``critical_flags`` holds flag *names* (e.g. ``"FRAUD_ALERT"``) rather than a decisao-agent-owned
enum: the closed set of valid names is policy-mcp's catalog
(``credit_core.domain.CriticalFlag``, translated), not something decisao-agent should duplicate
as a third copy of the same taxonomy. ``application.EvaluateCreditApplicationUseCase`` validates
every name against policy-mcp before evaluating.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    """Immutable, pre-validated financial and bureau snapshot of a credit applicant.

    Attributes:
        annual_revenue: Reported annual revenue.
        total_debt: Total outstanding debt.
        monthly_debt_service: Monthly debt service obligation.
        monthly_operating_cash_flow: Monthly operating cash flow.
        bureau_score: External bureau score on a 0-1000 scale.
        years_in_operation: Whole years the applicant has been operating.
        requested_amount: Requested credit amount.
        critical_flags: Critical red-flag names reported for the applicant, validated against
            policy-mcp's catalog before evaluation. An empty frozenset means none were reported.
    """

    annual_revenue: Decimal
    total_debt: Decimal
    monthly_debt_service: Decimal
    monthly_operating_cash_flow: Decimal
    bureau_score: Decimal
    years_in_operation: int
    requested_amount: Decimal
    critical_flags: frozenset[str]
