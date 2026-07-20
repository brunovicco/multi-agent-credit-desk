"""Application service exposing the bureau report catalog to bureau-mcp's entrypoints.

A single small application service, per the plan: no transaction coordination, no
authorization decisions - the catalog is read-only and unauthenticated at this layer.
Entrypoints translate this service's return values into wire schemas; this module never
imports a transport or serialization library.
"""

from bureau_mcp.application.ports import BureauLookupPort
from bureau_mcp.domain.cnpj import validate_cnpj
from bureau_mcp.domain.report import BureauReport


class BureauReportQueries:
    """Read-only use cases over a ``BureauLookupPort``."""

    def __init__(self, port: BureauLookupPort) -> None:
        """Initialize the query service with a bureau lookup port.

        Args:
            port: The bureau lookup port to query.
        """
        self._port = port

    def get_report(self, cnpj: str) -> BureauReport:
        """Get the bureau report for one company, validating the CNPJ first.

        Args:
            cnpj: The CNPJ to look up, as provided (punctuated or digits-only).

        Returns:
            The bureau report for the normalized CNPJ.

        Raises:
            InvalidCnpjError: If ``cnpj`` fails format or checksum validation.
            CnpjNotFoundError: If ``cnpj`` is well-formed but no report exists for it.
        """
        normalized_cnpj = validate_cnpj(cnpj)
        return self._port.get_report(normalized_cnpj)
