"""Domain-specific exceptions raised by cadastral-agent's KYC assessment use case."""


class CadastralAgentError(Exception):
    """Base exception for every cadastral-agent domain error."""


class InvalidCnpjError(CadastralAgentError):
    """Raised when a CNPJ is not a validly formatted identifier.

    Translates bureau-mcp's own ``INVALID_CNPJ`` tool error at the adapter boundary, per
    ``.claude/rules/architecture.md``'s "translate infrastructure exceptions at adapter
    boundaries" - no other layer ever needs to know bureau-mcp's error code vocabulary. Carries
    no CNPJ, matching bureau-mcp's own error, which never echoes the raw input back since a CNPJ
    identifies a specific company.
    """

    def __init__(self) -> None:
        """Initialize the error with a fixed, input-independent message."""
        super().__init__("The provided CNPJ is not a valid identifier.")


class CnpjNotFoundError(CadastralAgentError):
    """Raised when bureau-mcp has no report on file for a CNPJ.

    Carries no CNPJ, for the same reason as ``InvalidCnpjError``.
    """

    def __init__(self) -> None:
        """Initialize the error with a fixed, input-independent message."""
        super().__init__("No bureau report was found for the provided CNPJ.")


class BureauReportUnavailableError(CadastralAgentError):
    """Raised when bureau-mcp's report cannot be reached or returns an unexpected response."""

    def __init__(self, reason: str) -> None:
        """Initialize the error with why bureau-mcp's report could not be read.

        Args:
            reason: A short, human-readable description of the failure.
        """
        self.reason = reason
        super().__init__(f"bureau-mcp report unavailable: {reason}")
