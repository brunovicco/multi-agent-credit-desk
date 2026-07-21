"""Consumer-defined port for cadastral-agent's KYC assessment application layer.

Defined on the consumer side (``application``), near the use case that needs it, per
``.claude/rules/architecture.md``. ``BureauReportPort`` is the seam that keeps this layer
independent of how bureau-mcp is actually reached (MCP over stdio today).
"""

from typing import Protocol

from cadastral_agent.domain.bureau_finding import BureauFinding


class BureauReportPort(Protocol):
    """Read-only access to bureau-mcp's report for one company.

    The only implementation shipped today, ``BureauMcpClient``, speaks the MCP protocol to a
    ``bureau-mcp`` server process over stdio.
    """

    async def get_report(self, cnpj: str) -> BureauFinding:
        """Fetch the bureau finding for one company.

        Args:
            cnpj: The company's CNPJ, punctuated or digits-only.

        Returns:
            The bureau finding for ``cnpj``.

        Raises:
            InvalidCnpjError: If ``cnpj`` is not a validly formatted identifier.
            CnpjNotFoundError: If bureau-mcp has no report on file for ``cnpj``.
            BureauReportUnavailableError: If bureau-mcp cannot be reached or returns an
                unexpected response.
        """
        ...
