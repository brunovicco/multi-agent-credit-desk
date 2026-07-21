"""Stable, machine-readable error codes for cadastral-agent's batch CLI entrypoint.

Mirrors ``decisao_agent.entrypoints.errors``'s shape, per ``.claude/rules/api-boundaries.md``'s
"use a stable error envelope and machine-readable error codes".
"""

from cadastral_agent.domain.errors import (
    BureauReportUnavailableError,
    CadastralAgentError,
    CnpjNotFoundError,
    InvalidCnpjError,
)

INVALID_INPUT = "INVALID_INPUT"
ASSESSMENT_FAILED = "ASSESSMENT_FAILED"

_ERROR_CODES: dict[type[CadastralAgentError], str] = {
    InvalidCnpjError: "INVALID_CNPJ",
    CnpjNotFoundError: "CNPJ_NOT_FOUND",
    BureauReportUnavailableError: "BUREAU_REPORT_UNAVAILABLE",
}


def error_code_for(exc: CadastralAgentError) -> str:
    """Map a ``CadastralAgentError`` to its stable, machine-readable error code.

    Args:
        exc: The domain error to map.

    Returns:
        The error's stable code, or ``ASSESSMENT_FAILED`` for an unmapped subtype.
    """
    return _ERROR_CODES.get(type(exc), ASSESSMENT_FAILED)
