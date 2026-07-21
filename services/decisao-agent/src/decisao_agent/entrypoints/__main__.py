"""``python -m decisao_agent`` entrypoint: evaluate one credit application read from stdin.

This is a batch entrypoint, separate from the A2A server (``entrypoints.a2a_server``) - a
one-shot process that reads one ``ApplicationSnapshotInput`` JSON document from stdin, evaluates
it, and writes exactly one JSON document to stdout - a ``CreditOpinion`` on success, or a stable
``{"code": ..., "message": ...}`` error envelope on failure, distinguished by exit status. This
mirrors how ``policy-mcp`` and ``bureau-mcp`` return a tool error on the same channel as a tool
result rather than on a separate stream. stderr carries structured logs only, never
protocol-level data, so nothing written there needs to be machine-parsed - never a raw exception
message or stack trace either way, per ``.claude/rules/api-boundaries.md``. See
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md`` and
``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``.
"""

import asyncio
import json
import logging
import os
import sys
import time

from pydantic import ValidationError

from decisao_agent.adapters.credit_core_evaluation_adapter import CreditCoreEvaluationAdapter
from decisao_agent.adapters.policy_mcp_client import PolicyMcpClient
from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.domain.errors import DecisaoAgentError
from decisao_agent.entrypoints import schemas
from decisao_agent.entrypoints.errors import INVALID_INPUT, error_code_for

logger = logging.getLogger(__name__)

_POLICY_MCP_COMMAND_ENV_VAR = "DECISAO_AGENT_POLICY_MCP_COMMAND"


def main() -> None:
    """Configure logging and run one evaluation read from stdin, writing the result to stdout.

    Raises:
        SystemExit: With status ``1`` if stdin is not valid ``ApplicationSnapshotInput`` JSON
            or the evaluation use case raises a ``DecisaoAgentError``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    started = time.monotonic()
    try:
        input_model = schemas.ApplicationSnapshotInput.model_validate_json(sys.stdin.read())
    except ValidationError as exc:
        _log_and_exit(
            INVALID_INPUT, "the input is not a valid ApplicationSnapshotInput", exc, started
        )

    snapshot = schemas.to_application_snapshot(input_model)
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=CreditCoreEvaluationAdapter(),
        policy_catalog_port=PolicyMcpClient(command=os.environ.get(_POLICY_MCP_COMMAND_ENV_VAR)),
    )

    try:
        credit_opinion = asyncio.run(use_case.execute(snapshot))
    except DecisaoAgentError as exc:
        _log_and_exit(error_code_for(exc), str(exc), exc, started)

    duration_ms = (time.monotonic() - started) * 1000
    logger.info(
        "decisao_agent.evaluation_completed",
        extra={
            "outcome": "ok",
            "decision": credit_opinion.decision,
            "duration_ms": round(duration_ms, 3),
        },
    )
    sys.stdout.write(schemas.to_credit_opinion(credit_opinion).model_dump_json())
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
        "decisao_agent.evaluation_failed",
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
