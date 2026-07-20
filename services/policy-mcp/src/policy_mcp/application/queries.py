"""Application service exposing the policy catalog to policy-mcp's entrypoints.

A single small application service, per the plan: no transaction coordination, no authorization
decisions - the catalog is read-only and unauthenticated at this layer. Entrypoints translate this
service's return values into wire schemas; this module never imports ``credit_core`` or a
transport/serialization library.
"""

from policy_mcp.application.ports import PolicyCatalogPort
from policy_mcp.domain.catalog import CriticalFlagView, PolicyDetail, PolicySummary


class PolicyCatalogQueries:
    """Read-only use cases over a ``PolicyCatalogPort``."""

    def __init__(self, port: PolicyCatalogPort) -> None:
        """Initialize the query service with a policy catalog port.

        Args:
            port: The policy catalog port to query.
        """
        self._port = port

    def list_policies(self) -> tuple[PolicySummary, ...]:
        """List a short summary of every known policy version.

        Returns:
            A tuple of policy summaries, one per known version, in the port's canonical order.
        """
        return tuple(_summarize(self._port.get(version)) for version in self._port.list_versions())

    def get_policy(self, version: str) -> PolicyDetail:
        """Get the full detail of one policy version.

        Args:
            version: The policy version identifier to look up.

        Returns:
            The full policy detail for ``version``.

        Raises:
            PolicyNotFoundError: If ``version`` is not present in the catalog.
        """
        return self._port.get(version)

    def list_critical_flags(self) -> tuple[CriticalFlagView, ...]:
        """List every synthetic critical flag that forces a deterministic block.

        Returns:
            A tuple of critical flag views, in the port's canonical order.
        """
        return self._port.list_critical_flags()


def _summarize(detail: PolicyDetail) -> PolicySummary:
    """Derive a short ``PolicySummary`` from a full ``PolicyDetail``.

    Args:
        detail: The full policy detail to summarize.

    Returns:
        A ``PolicySummary`` covering ``detail``'s version, component and tier counts, and
        decision thresholds.
    """
    return PolicySummary(
        version=detail.version,
        score_component_count=len(detail.score_components),
        approval_authority_tier_count=len(detail.approval_authority_tiers),
        decision_thresholds=detail.decision_thresholds,
    )
