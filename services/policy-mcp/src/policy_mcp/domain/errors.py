"""Domain-specific exceptions raised by the policy-mcp catalog."""


class PolicyCatalogError(Exception):
    """Base exception for every policy-mcp catalog error."""


class PolicyNotFoundError(PolicyCatalogError):
    """Raised when a requested policy version is not present in the catalog."""

    def __init__(self, version: str) -> None:
        """Initialize the error with the unknown policy version that was requested.

        Args:
            version: The policy version identifier that could not be found.
        """
        self.version = version
        super().__init__(f"No policy found for version {version!r}.")
