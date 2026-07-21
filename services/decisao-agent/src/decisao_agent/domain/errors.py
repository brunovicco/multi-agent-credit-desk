"""Domain-specific exceptions raised by decisao-agent's evaluation use case."""


class DecisaoAgentError(Exception):
    """Base exception for every decisao-agent domain error."""


class InvalidApplicationSnapshotError(DecisaoAgentError):
    """Raised when an ``ApplicationSnapshot`` violates an input invariant.

    Translates ``credit_core.errors.InvalidCreditApplicationError`` at the adapter boundary, per
    ``.claude/rules/architecture.md``'s "translate infrastructure exceptions at adapter
    boundaries" - no other layer ever needs to know a ``credit_core`` exception type exists.
    """

    def __init__(self, reason: str) -> None:
        """Initialize the error with the reason credit_core rejected the snapshot.

        Args:
            reason: The underlying ``credit_core`` validation failure message.
        """
        self.reason = reason
        super().__init__(f"Invalid application snapshot: {reason}")


class UnknownCriticalFlagError(DecisaoAgentError):
    """Raised when a snapshot names a critical flag policy-mcp does not recognize."""

    def __init__(self, flag_names: frozenset[str]) -> None:
        """Initialize the error with the unrecognized critical flag names.

        Args:
            flag_names: The critical flag names not present in policy-mcp's catalog.
        """
        self.flag_names = flag_names
        super().__init__(f"Unknown critical flag(s): {sorted(flag_names)!r}.")


class PolicyCatalogUnavailableError(DecisaoAgentError):
    """Raised when policy-mcp's catalog cannot be reached or returns an unexpected error."""

    def __init__(self, reason: str) -> None:
        """Initialize the error with why policy-mcp's catalog could not be read.

        Args:
            reason: A short, human-readable description of the failure.
        """
        self.reason = reason
        super().__init__(f"policy-mcp catalog unavailable: {reason}")


class PolicyVersionMismatchError(DecisaoAgentError):
    """Raised when credit_core applies a policy version policy-mcp does not know about.

    This is an integrity check, not an expected runtime path: it guards against
    decisao-agent and policy-mcp silently drifting to different ``credit_core`` builds.
    """

    def __init__(self, version: str) -> None:
        """Initialize the error with the unrecognized policy version.

        Args:
            version: The policy version ``credit_core`` applied, absent from policy-mcp's
                catalog.
        """
        self.version = version
        super().__init__(
            f"credit_core applied policy version {version!r}, which policy-mcp does not know."
        )
