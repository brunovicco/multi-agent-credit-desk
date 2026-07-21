"""Stable, machine-readable error codes shared by every decisao-agent entrypoint.

Used by both ``entrypoints.__main__`` (the batch CLI) and ``entrypoints.a2a_executor`` (the A2A
surface) so the two transports report the same code for the same domain error, per
``.claude/rules/api-boundaries.md``'s "use a stable error envelope and machine-readable error
codes".
"""

from decisao_agent.domain.errors import (
    DecisaoAgentError,
    InvalidApplicationSnapshotError,
    PolicyCatalogUnavailableError,
    PolicyVersionMismatchError,
    UnknownCriticalFlagError,
)

INVALID_INPUT = "INVALID_INPUT"
EVALUATION_FAILED = "EVALUATION_FAILED"

_ERROR_CODES: dict[type[DecisaoAgentError], str] = {
    InvalidApplicationSnapshotError: "INVALID_APPLICATION_SNAPSHOT",
    UnknownCriticalFlagError: "UNKNOWN_CRITICAL_FLAG",
    PolicyVersionMismatchError: "POLICY_VERSION_MISMATCH",
    PolicyCatalogUnavailableError: "POLICY_CATALOG_UNAVAILABLE",
}


def error_code_for(exc: DecisaoAgentError) -> str:
    """Map a ``DecisaoAgentError`` to its stable, machine-readable error code.

    Args:
        exc: The domain error to map.

    Returns:
        The error's stable code, or ``EVALUATION_FAILED`` for an unmapped subtype.
    """
    return _ERROR_CODES.get(type(exc), EVALUATION_FAILED)
