"""Adapter that evaluates credit applications directly through ``credit_core``.

This is the **only** module in ``decisao_agent`` allowed to import ``credit_core`` - see
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``, which mirrors
``docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md``'s single-adapter-import
boundary. The boundary is enforced by
``services/decisao-agent/tests/unit/test_architecture_boundary.py``, which AST-walks
``domain/``, ``application/``, and ``entrypoints/`` to fail the build if any of them import
``credit_core``.
"""

from credit_core.domain import CreditApplicationSnapshot, CreditEvaluationResult, CriticalFlag
from credit_core.errors import InvalidCreditApplicationError
from credit_core.evaluation import evaluate_credit_application
from decisao_agent.domain.errors import InvalidApplicationSnapshotError
from decisao_agent.domain.opinion import ComponentScoreView, CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot


class CreditCoreEvaluationAdapter:
    """``CreditEvaluationPort`` implementation backed directly by ``credit_core``."""

    def evaluate(self, snapshot: ApplicationSnapshot) -> CreditOpinion:
        """Evaluate one application snapshot through ``credit_core``.

        Args:
            snapshot: The applicant financial and bureau snapshot to evaluate.

        Returns:
            The translated, structured evaluation outcome.

        Raises:
            InvalidApplicationSnapshotError: If ``snapshot`` names a critical flag credit_core
                does not define, or otherwise violates an input invariant credit_core enforces.
        """
        credit_core_snapshot = _to_credit_core_snapshot(snapshot)
        try:
            result = evaluate_credit_application(credit_core_snapshot)
        except InvalidCreditApplicationError as exc:
            raise InvalidApplicationSnapshotError(str(exc)) from exc
        return _to_credit_opinion(result)


def _to_credit_core_snapshot(snapshot: ApplicationSnapshot) -> CreditApplicationSnapshot:
    """Translate an ``ApplicationSnapshot`` into a ``credit_core`` snapshot.

    Args:
        snapshot: The decisao-agent snapshot to translate.

    Returns:
        The equivalent ``credit_core.domain.CreditApplicationSnapshot``.

    Raises:
        InvalidApplicationSnapshotError: If ``snapshot.critical_flags`` names a flag
            ``credit_core.domain.CriticalFlag`` does not define.
    """
    try:
        critical_flags = frozenset(CriticalFlag[name] for name in snapshot.critical_flags)
    except KeyError as exc:
        raise InvalidApplicationSnapshotError(f"unknown critical flag name: {exc}") from exc
    return CreditApplicationSnapshot(
        annual_revenue=snapshot.annual_revenue,
        total_debt=snapshot.total_debt,
        monthly_debt_service=snapshot.monthly_debt_service,
        monthly_operating_cash_flow=snapshot.monthly_operating_cash_flow,
        bureau_score=snapshot.bureau_score,
        years_in_operation=snapshot.years_in_operation,
        requested_amount=snapshot.requested_amount,
        critical_flags=critical_flags,
    )


def _to_credit_opinion(result: CreditEvaluationResult) -> CreditOpinion:
    """Translate a ``credit_core`` ``CreditEvaluationResult`` into a ``CreditOpinion``.

    Args:
        result: The ``credit_core`` evaluation result to translate.

    Returns:
        The translated credit opinion, covering every ``CreditEvaluationResult`` field.
    """
    return CreditOpinion(
        policy_version=result.policy_version,
        total_score=result.total_score,
        component_scores=tuple(
            ComponentScoreView(
                component=component_score.component.value,
                metric_value=component_score.metric_value,
                raw_score=component_score.raw_score,
                weight=component_score.weight,
                weighted_score=component_score.weighted_score,
            )
            for component_score in result.component_scores
        ),
        decision=result.decision.value,
        approval_authority=result.approval_authority.value,
        reason_codes=tuple(reason_code.value for reason_code in result.reason_codes),
        blocking_reasons=tuple(reason_code.value for reason_code in result.blocking_reasons),
    )
