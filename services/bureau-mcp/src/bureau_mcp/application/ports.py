"""Consumer-defined port for the bureau report application layer.

Defined on the consumer side (``application``), near the use case that needs it, per
``.claude/rules/architecture.md``. ``BureauLookupPort`` is the seam that keeps this layer
independent of how a report is actually sourced; the only implementation shipped today,
``SyntheticBureauSource``, is a fixed in-memory dataset, not a real bureau connection.
"""

from typing import Protocol

from bureau_mcp.domain.report import BureauReport


class BureauLookupPort(Protocol):
    """Read-only access to a synthetic credit-bureau report catalog, keyed by CNPJ."""

    def get_report(self, cnpj: str) -> BureauReport:
        """Return the bureau report for one company.

        Args:
            cnpj: The company's canonical, digits-only, 14-character CNPJ.

        Returns:
            The bureau report for ``cnpj``.

        Raises:
            CnpjNotFoundError: If no report exists for ``cnpj``.
        """
        ...
