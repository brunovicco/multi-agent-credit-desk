"""Pydantic wire schemas for decisao-agent's CLI, and explicit domain-to-wire mappings.

Every schema mirrors ``credit_desk_contracts._base.StrictContract``'s conventions: unknown
fields are rejected (``extra="forbid"``) and output instances are immutable once constructed
(``frozen=True``) - matching ``policy_mcp.entrypoints.schemas`` and
``bureau_mcp.entrypoints.schemas``. The input schema is not frozen, since
``ApplicationSnapshotInput`` exists only to validate and normalize raw JSON before it is mapped
to the domain layer. Mapping is explicit, one field at a time - never automatic dataclass
serialization, so a schema change is always a deliberate, reviewable edit.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from decisao_agent.domain import opinion, snapshot


class ApplicationSnapshotInput(BaseModel):
    """Wire schema for the CLI's JSON input.

    See ``decisao_agent.domain.snapshot.ApplicationSnapshot``.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    annual_revenue: Decimal
    total_debt: Decimal
    monthly_debt_service: Decimal
    monthly_operating_cash_flow: Decimal
    bureau_score: Decimal
    years_in_operation: Annotated[int, Field(ge=0)]
    requested_amount: Decimal
    critical_flags: tuple[str, ...] = ()


class _DecisaoAgentContract(BaseModel):
    """Base model for every decisao-agent output wire schema: immutable, closed to unknowns."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ComponentScore(_DecisaoAgentContract):
    """Wire schema for one scored component.

    See ``decisao_agent.domain.opinion.ComponentScoreView``.
    """

    component: str
    metric_value: Decimal
    raw_score: Decimal
    weight: Decimal
    weighted_score: Decimal


class CreditOpinion(_DecisaoAgentContract):
    """Wire schema for the CLI's JSON output.

    See ``decisao_agent.domain.opinion.CreditOpinion``.
    """

    policy_version: str
    total_score: Decimal
    component_scores: tuple[ComponentScore, ...]
    decision: str
    approval_authority: str
    reason_codes: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    narrative: str | None = None


def to_application_snapshot(
    input_model: ApplicationSnapshotInput,
) -> snapshot.ApplicationSnapshot:
    """Map a validated ``ApplicationSnapshotInput`` to the domain snapshot.

    Args:
        input_model: The validated wire input to map.

    Returns:
        The equivalent domain ``ApplicationSnapshot``.
    """
    return snapshot.ApplicationSnapshot(
        annual_revenue=input_model.annual_revenue,
        total_debt=input_model.total_debt,
        monthly_debt_service=input_model.monthly_debt_service,
        monthly_operating_cash_flow=input_model.monthly_operating_cash_flow,
        bureau_score=input_model.bureau_score,
        years_in_operation=input_model.years_in_operation,
        requested_amount=input_model.requested_amount,
        critical_flags=frozenset(input_model.critical_flags),
    )


def to_component_score(component_score: opinion.ComponentScoreView) -> ComponentScore:
    """Map a ``ComponentScoreView`` domain value to its wire schema.

    Args:
        component_score: The domain component score to map.

    Returns:
        The equivalent wire schema.
    """
    return ComponentScore(
        component=component_score.component,
        metric_value=component_score.metric_value,
        raw_score=component_score.raw_score,
        weight=component_score.weight,
        weighted_score=component_score.weighted_score,
    )


def to_credit_opinion(credit_opinion: opinion.CreditOpinion) -> CreditOpinion:
    """Map a ``CreditOpinion`` domain value to its wire schema.

    Args:
        credit_opinion: The domain credit opinion to map.

    Returns:
        The equivalent wire schema.
    """
    return CreditOpinion(
        policy_version=credit_opinion.policy_version,
        total_score=credit_opinion.total_score,
        component_scores=tuple(
            to_component_score(component_score)
            for component_score in credit_opinion.component_scores
        ),
        decision=credit_opinion.decision,
        approval_authority=credit_opinion.approval_authority,
        reason_codes=credit_opinion.reason_codes,
        blocking_reasons=credit_opinion.blocking_reasons,
        narrative=credit_opinion.narrative,
    )
