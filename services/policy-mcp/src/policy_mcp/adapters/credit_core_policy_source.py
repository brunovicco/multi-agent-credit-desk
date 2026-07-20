"""Adapter that sources the policy catalog directly from ``credit_core``.

This is the **only** module in ``policy_mcp`` allowed to import ``credit_core`` - see
``docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md``. Reading
``credit_core.policy.DEMO_POLICY_V1`` and ``credit_core.domain.CriticalFlag`` directly, instead of
re-authoring the policy as an independent document, guarantees what agents are told the policy is
can never drift from what ``credit_core`` actually enforces. The boundary is enforced by
``services/policy-mcp/tests/unit/test_architecture_boundary.py``, which AST-walks ``domain/``,
``application/``, and ``entrypoints/`` to fail the build if any of them import ``credit_core``.
"""

from decimal import Decimal

from credit_core.domain import ApprovalAuthority, CriticalFlag
from credit_core.policy import DEMO_POLICY_V1, CreditPolicy, ScoreBand, ScoreComponentPolicy
from policy_mcp.domain.catalog import (
    ApprovalAuthorityTier,
    CriticalFlagView,
    DecisionThresholds,
    PolicyDetail,
    ScoreBandView,
    ScoreComponentView,
)
from policy_mcp.domain.errors import PolicyNotFoundError

_CATALOG: dict[str, CreditPolicy] = {DEMO_POLICY_V1.version: DEMO_POLICY_V1}


class CreditCorePolicySource:
    """``PolicyCatalogPort`` implementation backed directly by ``credit_core``'s own policy.

    Translates ``credit_core.policy.CreditPolicy`` (and its nested ``ScoreComponentPolicy`` /
    ``ScoreBand``) and ``credit_core.domain.CriticalFlag`` into policy-mcp's own
    ``policy_mcp.domain.catalog`` vocabulary at this single boundary.
    """

    def list_versions(self) -> tuple[str, ...]:
        """Return every policy version ``credit_core`` currently ships.

        Returns:
            A tuple of policy version identifiers.
        """
        return tuple(_CATALOG.keys())

    def get(self, version: str) -> PolicyDetail:
        """Return the full detail of one ``credit_core`` policy version.

        Args:
            version: The policy version identifier to look up.

        Returns:
            The translated policy detail.

        Raises:
            PolicyNotFoundError: If ``version`` is not one ``credit_core`` ships.
        """
        policy = _CATALOG.get(version)
        if policy is None:
            raise PolicyNotFoundError(version)
        return _to_policy_detail(policy)

    def list_critical_flags(self) -> tuple[CriticalFlagView, ...]:
        """Return every synthetic critical flag defined by ``credit_core``.

        Returns:
            A tuple of critical flag views, one per ``credit_core.domain.CriticalFlag`` member,
            in declaration order.
        """
        return tuple(CriticalFlagView(name=flag.name, value=flag.value) for flag in CriticalFlag)


def _to_policy_detail(policy: CreditPolicy) -> PolicyDetail:
    """Translate a ``credit_core`` ``CreditPolicy`` into a ``PolicyDetail``.

    Args:
        policy: The ``credit_core`` policy to translate.

    Returns:
        The translated policy detail, covering every ``CreditPolicy`` field.
    """
    return PolicyDetail(
        version=policy.version,
        score_components=tuple(
            _to_score_component_view(component_policy)
            for component_policy in policy.score_components
        ),
        decision_thresholds=DecisionThresholds(
            approval_recommendation_minimum_score=policy.approval_recommendation_minimum_score,
            conditional_approval_minimum_score=policy.conditional_approval_minimum_score,
            committee_referral_minimum_score=policy.committee_referral_minimum_score,
        ),
        approval_authority_tiers=_to_approval_authority_tiers(policy),
        zero_debt_service_metric_value=policy.zero_debt_service_metric_value,
    )


def _to_score_component_view(component_policy: ScoreComponentPolicy) -> ScoreComponentView:
    """Translate a ``credit_core`` ``ScoreComponentPolicy`` into a ``ScoreComponentView``.

    Args:
        component_policy: The ``credit_core`` component policy to translate.

    Returns:
        The translated score component view.
    """
    return ScoreComponentView(
        component=component_policy.component.value,
        weight=component_policy.weight,
        direction=component_policy.direction.value,
        bands=tuple(_to_score_band_view(band) for band in component_policy.bands),
    )


def _to_score_band_view(band: ScoreBand) -> ScoreBandView:
    """Translate a ``credit_core`` ``ScoreBand`` into a ``ScoreBandView``.

    Args:
        band: The ``credit_core`` score band to translate.

    Returns:
        The translated score band view.
    """
    return ScoreBandView(boundary=band.boundary, score=band.score)


def _to_approval_authority_tiers(policy: CreditPolicy) -> tuple[ApprovalAuthorityTier, ...]:
    """Derive the four approval-authority tiers from a policy's amount thresholds.

    Uses only the public ``CreditPolicy`` amount-threshold fields and the public
    ``credit_core.domain.ApprovalAuthority`` enum - never
    ``credit_core.evaluation._authority``, which is private and not meant for reuse.

    Args:
        policy: The ``credit_core`` policy whose thresholds define the tiers.

    Returns:
        The four approval-authority tiers, ordered from the smallest to the largest
        requested-amount range. The last tier's ``maximum_amount`` is ``None`` (no upper bound).
    """
    return (
        ApprovalAuthorityTier(
            authority=ApprovalAuthority.ANALYST.value,
            minimum_amount=Decimal("0"),
            maximum_amount=policy.analyst_maximum_amount,
        ),
        ApprovalAuthorityTier(
            authority=ApprovalAuthority.SENIOR_ANALYST.value,
            minimum_amount=policy.analyst_maximum_amount,
            maximum_amount=policy.senior_analyst_maximum_amount,
        ),
        ApprovalAuthorityTier(
            authority=ApprovalAuthority.CREDIT_COMMITTEE.value,
            minimum_amount=policy.senior_analyst_maximum_amount,
            maximum_amount=policy.credit_committee_maximum_amount,
        ),
        ApprovalAuthorityTier(
            authority=ApprovalAuthority.EXECUTIVE_BOARD.value,
            minimum_amount=policy.credit_committee_maximum_amount,
            maximum_amount=None,
        ),
    )
