"""Domain-specific exceptions raised by the bureau-mcp report catalog."""


class BureauReportError(Exception):
    """Base exception for every bureau-mcp report error."""


class InvalidCnpjError(BureauReportError):
    """Raised when a CNPJ fails format or checksum validation."""

    def __init__(self, raw: str) -> None:
        """Initialize the error with the malformed CNPJ that was provided.

        Args:
            raw: The CNPJ value, as provided, that failed validation.
        """
        self.raw = raw
        super().__init__(f"{raw!r} is not a valid CNPJ.")


class CnpjNotFoundError(BureauReportError):
    """Raised when no bureau report exists for a well-formed CNPJ."""

    def __init__(self, cnpj: str) -> None:
        """Initialize the error with the CNPJ that could not be found.

        Args:
            cnpj: The canonical, digits-only CNPJ that could not be found.
        """
        self.cnpj = cnpj
        super().__init__(f"No bureau report found for CNPJ {cnpj!r}.")
