"""Pydantic wire schemas for the policy-mcp MCP tools, and explicit domain-to-wire mappings.

Every schema mirrors ``credit_desk_contracts._base.StrictContract``'s conventions (see
``packages/contracts/src/credit_desk_contracts/_base.py``): unknown fields are rejected
(``extra="forbid"``) and instances are immutable once constructed (``frozen=True``). The
convention is reimplemented locally rather than imported, since ``StrictContract`` is a private,
unexported module of a sibling workspace package. Mapping from ``policy_mcp.domain.catalog``
types to these schemas is explicit, one field at a time - never automatic dataclass
serialization, so a schema change is always a deliberate, reviewable edit.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from policy_mcp.domain import catalog


class _PolicyMcpContract(BaseModel):
    """Base model for every policy-mcp wire schema: immutable and closed to unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ScoreBand(_PolicyMcpContract):
    """Wire schema for one boundary/score pair. See ``policy_mcp.domain.catalog.ScoreBandView``.

    ``boundary`` allows infinite values: credit_core's own ``ScoreBand`` requires the last band
    of a ``LOWER_IS_BETTER`` component to have an infinite boundary (see
    ``credit_core.policy._validate_ascending_bands``), and this schema must report that value
    faithfully rather than reject or silently alter it.
    """

    boundary: Annotated[Decimal, Field(allow_inf_nan=True)]
    score: Decimal


class ScoreComponent(_PolicyMcpContract):
    """Wire schema for one scored component.

    See ``policy_mcp.domain.catalog.ScoreComponentView``.
    """

    component: str
    weight: Decimal
    direction: str
    bands: tuple[ScoreBand, ...]


class DecisionThresholds(_PolicyMcpContract):
    """Wire schema for the score-based decision thresholds.

    See ``policy_mcp.domain.catalog.DecisionThresholds``.
    """

    approval_recommendation_minimum_score: Decimal
    conditional_approval_minimum_score: Decimal
    committee_referral_minimum_score: Decimal


class ApprovalAuthorityTier(_PolicyMcpContract):
    """Wire schema for one approval-authority tier.

    See ``policy_mcp.domain.catalog.ApprovalAuthorityTier``.
    """

    authority: str
    minimum_amount: Decimal
    maximum_amount: Decimal | None


class PolicySummary(_PolicyMcpContract):
    """Wire schema for a short policy summary. See ``policy_mcp.domain.catalog.PolicySummary``."""

    version: str
    score_component_count: int
    approval_authority_tier_count: int
    decision_thresholds: DecisionThresholds


class PolicyListResult(_PolicyMcpContract):
    """Wire schema returned by the ``list_policies`` tool."""

    policies: tuple[PolicySummary, ...]


class PolicyDetail(_PolicyMcpContract):
    """Wire schema returned by the ``get_policy`` tool.

    See ``policy_mcp.domain.catalog.PolicyDetail``.
    """

    version: str
    score_components: tuple[ScoreComponent, ...]
    decision_thresholds: DecisionThresholds
    approval_authority_tiers: tuple[ApprovalAuthorityTier, ...]
    zero_debt_service_metric_value: Decimal


class CriticalFlag(_PolicyMcpContract):
    """Wire schema for one critical flag. See ``policy_mcp.domain.catalog.CriticalFlagView``."""

    name: str
    value: str


class CriticalFlagCatalog(_PolicyMcpContract):
    """Wire schema returned by the ``list_critical_flags`` tool."""

    critical_flags: tuple[CriticalFlag, ...]


def to_score_band(band: catalog.ScoreBandView) -> ScoreBand:
    """Map a ``ScoreBandView`` to its wire schema.

    Args:
        band: The domain score band to map.

    Returns:
        The equivalent wire schema.
    """
    return ScoreBand(boundary=band.boundary, score=band.score)


def to_score_component(component: catalog.ScoreComponentView) -> ScoreComponent:
    """Map a ``ScoreComponentView`` to its wire schema.

    Args:
        component: The domain score component to map.

    Returns:
        The equivalent wire schema.
    """
    return ScoreComponent(
        component=component.component,
        weight=component.weight,
        direction=component.direction,
        bands=tuple(to_score_band(band) for band in component.bands),
    )


def to_decision_thresholds(thresholds: catalog.DecisionThresholds) -> DecisionThresholds:
    """Map a ``DecisionThresholds`` domain value to its wire schema.

    Args:
        thresholds: The domain decision thresholds to map.

    Returns:
        The equivalent wire schema.
    """
    return DecisionThresholds(
        approval_recommendation_minimum_score=thresholds.approval_recommendation_minimum_score,
        conditional_approval_minimum_score=thresholds.conditional_approval_minimum_score,
        committee_referral_minimum_score=thresholds.committee_referral_minimum_score,
    )


def to_approval_authority_tier(tier: catalog.ApprovalAuthorityTier) -> ApprovalAuthorityTier:
    """Map an ``ApprovalAuthorityTier`` domain value to its wire schema.

    Args:
        tier: The domain approval-authority tier to map.

    Returns:
        The equivalent wire schema.
    """
    return ApprovalAuthorityTier(
        authority=tier.authority,
        minimum_amount=tier.minimum_amount,
        maximum_amount=tier.maximum_amount,
    )


def to_policy_summary(summary: catalog.PolicySummary) -> PolicySummary:
    """Map a ``PolicySummary`` domain value to its wire schema.

    Args:
        summary: The domain policy summary to map.

    Returns:
        The equivalent wire schema.
    """
    return PolicySummary(
        version=summary.version,
        score_component_count=summary.score_component_count,
        approval_authority_tier_count=summary.approval_authority_tier_count,
        decision_thresholds=to_decision_thresholds(summary.decision_thresholds),
    )


def to_policy_list_result(summaries: Sequence[catalog.PolicySummary]) -> PolicyListResult:
    """Map every known policy summary to the ``list_policies`` tool's wire result.

    Args:
        summaries: The domain policy summaries to map, in catalog order.

    Returns:
        The wire result carrying every mapped summary.
    """
    return PolicyListResult(policies=tuple(to_policy_summary(summary) for summary in summaries))


def to_policy_detail(detail: catalog.PolicyDetail) -> PolicyDetail:
    """Map a ``PolicyDetail`` domain value to the ``get_policy`` tool's wire result.

    Args:
        detail: The domain policy detail to map.

    Returns:
        The equivalent wire schema.
    """
    return PolicyDetail(
        version=detail.version,
        score_components=tuple(
            to_score_component(component) for component in detail.score_components
        ),
        decision_thresholds=to_decision_thresholds(detail.decision_thresholds),
        approval_authority_tiers=tuple(
            to_approval_authority_tier(tier) for tier in detail.approval_authority_tiers
        ),
        zero_debt_service_metric_value=detail.zero_debt_service_metric_value,
    )


def to_critical_flag(flag: catalog.CriticalFlagView) -> CriticalFlag:
    """Map a ``CriticalFlagView`` domain value to its wire schema.

    Args:
        flag: The domain critical flag view to map.

    Returns:
        The equivalent wire schema.
    """
    return CriticalFlag(name=flag.name, value=flag.value)


def to_critical_flag_catalog(flags: Sequence[catalog.CriticalFlagView]) -> CriticalFlagCatalog:
    """Map every critical flag to the ``list_critical_flags`` tool's wire result.

    Args:
        flags: The domain critical flag views to map, in catalog order.

    Returns:
        The wire result carrying every mapped critical flag.
    """
    return CriticalFlagCatalog(critical_flags=tuple(to_critical_flag(flag) for flag in flags))
