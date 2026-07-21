"""AgentExecutor wiring EvaluateCreditApplicationUseCase into the A2A protocol.

Uses the "immediate response" pattern documented on ``AgentExecutor.execute``: enqueues a
single ``Message`` and returns, rather than a long-running ``Task`` driven by ``TaskUpdater``
status transitions - credit evaluation is a fast, synchronous, in-process computation with no
genuine work phases to report, per
``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``.

The request/response body is the exact same JSON document the batch CLI
(``entrypoints.__main__``) reads from stdin and writes to stdout, transported as a ``TextPart``
with ``media_type="application/json"`` rather than a ``DataPart``: a2a-sdk's ``DataPart``
round-trips through a protobuf ``Struct`` (double-precision floats), which silently truncates
``Decimal`` precision - unacceptable for this project's monetary fields (see
``.claude/rules/python.md``'s "Use Decimal for monetary values").
"""

import json

from a2a.helpers.proto_helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import UnsupportedOperationError
from pydantic import ValidationError

from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.domain.errors import DecisaoAgentError
from decisao_agent.entrypoints import schemas
from decisao_agent.entrypoints.errors import INVALID_INPUT, error_code_for

_JSON_MEDIA_TYPE = "application/json"


class DecisaoAgentExecutor(AgentExecutor):
    """Evaluates one credit application snapshot per incoming A2A message."""

    def __init__(self, use_case: EvaluateCreditApplicationUseCase) -> None:
        """Initialize the executor with the evaluation use case to run.

        Args:
            use_case: The evaluation use case to run for every incoming message.
        """
        self._use_case = use_case

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Evaluate the credit application snapshot carried in the incoming message.

        Args:
            context: The request context carrying the incoming message.
            event_queue: The queue to publish the response message to.
        """
        raw_text = get_message_text(context.message) if context.message else ""
        try:
            input_model = schemas.ApplicationSnapshotInput.model_validate_json(raw_text)
        except ValidationError:
            await self._respond_with_error(
                event_queue,
                context,
                INVALID_INPUT,
                "the input is not a valid ApplicationSnapshotInput",
            )
            return

        snapshot = schemas.to_application_snapshot(input_model)
        try:
            credit_opinion = await self._use_case.execute(
                snapshot, workflow_id=context.context_id, task_id=context.task_id
            )
        except DecisaoAgentError as exc:
            await self._respond_with_error(event_queue, context, error_code_for(exc), str(exc))
            return

        body = schemas.to_credit_opinion(credit_opinion).model_dump_json()
        await event_queue.enqueue_event(
            new_text_message(
                body,
                media_type=_JSON_MEDIA_TYPE,
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Reject cancellation: evaluations complete synchronously and are never in flight.

        Args:
            context: The request context carrying the task ID to cancel.
            event_queue: Unused - no status update is published.

        Raises:
            UnsupportedOperationError: Always.
        """
        raise UnsupportedOperationError(
            "decisao-agent evaluations complete synchronously and cannot be canceled mid-flight."
        )

    async def _respond_with_error(
        self, event_queue: EventQueue, context: RequestContext, code: str, message: str
    ) -> None:
        """Enqueue a stable JSON error envelope as a text message.

        Args:
            event_queue: The queue to publish the response message to.
            context: The request context, for context/task correlation.
            code: A stable, machine-readable error code.
            message: A short, human-readable description of the failure.
        """
        body = json.dumps({"code": code, "message": message})
        await event_queue.enqueue_event(
            new_text_message(
                body,
                media_type=_JSON_MEDIA_TYPE,
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )
