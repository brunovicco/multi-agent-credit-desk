"""Consumer-defined ports for the policy catalog application layer.

Defined on the consumer side (``application``), near the use case that needs it, per
``.claude/rules/architecture.md``. ``PolicyCatalogPort`` is the seam that keeps this layer
independent of how the catalog is actually sourced; ``credit_core`` is never imported here.
"""

from typing import Protocol

from policy_mcp.domain.catalog import CriticalFlagView, PolicyDetail


class PolicyCatalogPort(Protocol):
    """Read-only access to a versioned catalog of credit policies.

    Implementations translate an external policy source into policy-mcp's own domain vocabulary
    (``policy_mcp.domain.catalog``). The only implementation shipped today,
    ``CreditCorePolicySource``, reads ``credit_core`` directly.
    """

    def list_versions(self) -> tuple[str, ...]:
        """Return every known policy version, in this catalog's canonical order.

        Returns:
            A tuple of policy version identifiers.
        """
        ...

    def get(self, version: str) -> PolicyDetail:
        """Return the full detail of one policy version.

        Args:
            version: The policy version identifier to look up.

        Returns:
            The full policy detail for ``version``.

        Raises:
            PolicyNotFoundError: If ``version`` is not present in this catalog.
        """
        ...

    def list_critical_flags(self) -> tuple[CriticalFlagView, ...]:
        """Return every synthetic critical flag that forces a deterministic block.

        Returns:
            A tuple of critical flag views, in this catalog's canonical order.
        """
        ...
