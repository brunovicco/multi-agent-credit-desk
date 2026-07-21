"""``python -m cadastral_agent`` entrypoint: screen one company's KYC standing read from stdin.

This is a batch entrypoint, mirroring ``decisao_agent.entrypoints.__main__``'s shape: a one-shot
process that reads one ``CnpjInput`` JSON document from stdin, screens it against bureau-mcp's
report, and writes exactly one JSON document to stdout - a ``KycAssessmentOutput`` on success, or
a stable ``{"code": ..., "message": ...}`` error envelope on failure, distinguished by exit
status. stderr carries structured logs only, never protocol-level data, so nothing written there
needs to be machine-parsed - never a raw exception message or stack trace either way, per
``.claude/rules/api-boundaries.md``.
"""

import asyncio
import json
import logging
import os
import sys
import time

from pydantic import ValidationError

from cadastral_agent.adapters.bureau_mcp_client import BureauMcpClient
from cadastral_agent.application.assess import AssessCadastralApplicationUseCase
from cadastral_agent.domain.errors import CadastralAgentError
from cadastral_agent.entrypoints import schemas
from cadastral_agent.entrypoints.errors import INVALID_INPUT, error_code_for

logger = logging.getLogger(__name__)

_BUREAU_MCP_COMMAND_ENV_VAR = "CADASTRAL_AGENT_BUREAU_MCP_COMMAND"


def main() -> None:
    """Configure logging and run one KYC assessment read from stdin, writing the result to stdout.

    Raises:
        SystemExit: With status ``1`` if stdin is not valid ``CnpjInput`` JSON or the assessment
            use case raises a ``CadastralAgentError``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    started = time.monotonic()
    try:
        input_model = schemas.CnpjInput.model_validate_json(sys.stdin.read())
    except ValidationError as exc:
        _log_and_exit(INVALID_INPUT, "the input is not a valid CnpjInput", exc, started)

    use_case = AssessCadastralApplicationUseCase(
        bureau_report_port=BureauMcpClient(command=os.environ.get(_BUREAU_MCP_COMMAND_ENV_VAR)),
    )

    try:
        assessment = asyncio.run(use_case.execute(input_model.cnpj))
    except CadastralAgentError as exc:
        _log_and_exit(error_code_for(exc), str(exc), exc, started)

    duration_ms = (time.monotonic() - started) * 1000
    logger.info(
        "cadastral_agent.assessment_completed",
        extra={
            "outcome": "ok",
            "decision": assessment.decision.value,
            "duration_ms": round(duration_ms, 3),
        },
    )
    sys.stdout.write(schemas.to_kyc_assessment_output(assessment).model_dump_json())
    sys.stdout.write("\n")


def _log_and_exit(code: str, message: str, exc: Exception, started: float) -> None:
    """Log one structured failure line and raise ``SystemExit`` with a stable error envelope.

    Args:
        code: A stable, machine-readable error code.
        message: A short, human-readable description of the failure.
        exc: The exception that triggered the failure, logged by type only - never its full
            message, which may echo raw input.
        started: The ``time.monotonic()`` value captured when the run began.

    Raises:
        SystemExit: Always, with status ``1``.
    """
    duration_ms = (time.monotonic() - started) * 1000
    logger.error(
        "cadastral_agent.assessment_failed",
        extra={
            "outcome": code,
            "exception_type": type(exc).__name__,
            "duration_ms": round(duration_ms, 3),
        },
    )
    sys.stdout.write(json.dumps({"code": code, "message": message}))
    sys.stdout.write("\n")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
