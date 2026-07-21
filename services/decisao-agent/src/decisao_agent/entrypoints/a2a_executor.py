"""AgentExecutor wiring EvaluateCreditApplicationUseCase into the A2A protocol.

Uses the ``Task``/``TaskUpdater`` pattern documented on ``AgentExecutor.execute``: creates a
real, store-backed ``Task`` and reports ``TASK_STATE_WORKING`` while evaluating, rather than the
"immediate response" single-``Message`` pattern this executor originally used (see
``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``). Narrative drafting
(``docs/adr/0014-decisao-agent-drafts-an-optional-llm-opinion-narrative.md``) introduced a real,
non-trivial latency phase - two network round-trips, policy-model-router then LiteLLM - worth
reporting as genuine task progress, and a real ``Task`` makes ``tasks/get``/``tasks/cancel``
requests against this agent actually work, which ``DefaultRequestHandler`` already routes
generically.

The request/response body is the exact same JSON document the batch CLI
(``entrypoints.__main__``) reads from stdin and writes to stdout, transported as a ``TextPart``
with ``media_type="application/json"`` rather than a ``DataPart``: a2a-sdk's ``DataPart``
round-trips through a protobuf ``Struct`` (double-precision floats), which silently truncates
``Decimal`` precision - unacceptable for this project's monetary fields (see
``.claude/rules/python.md``'s "Use Decimal for monetary values").
"""

import json

from a2a.helpers.proto_helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import UnsupportedOperationError
from pydantic import ValidationError

from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.domain.errors import DecisaoAgentError
from decisao_agent.entrypoints import schemas
from decisao_agent.entrypoints.errors import INVALID_INPUT, error_code_for

_JSON_MEDIA_TYPE = "application/json"
_CREDIT_OPINION_ARTIFACT_NAME = "credit_opinion"


class DecisaoAgentExecutor(AgentExecutor):
    """Evaluates one credit application snapshot per incoming A2A task."""

    def __init__(self, use_case: EvaluateCreditApplicationUseCase) -> None:
        """Initialize the executor with the evaluation use case to run.

        Args:
            use_case: The evaluation use case to run for every incoming task.
        """
        self._use_case = use_case

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Evaluate the credit application snapshot carried in the incoming task's message.

        Args:
            context: The request context carrying the incoming message and, once created, the
                task.
            event_queue: The queue to publish task lifecycle events to.
        """
        task = context.current_task
        if task is None:
            if context.message is None:
                await self._respond_without_a_task(
                    event_queue, INVALID_INPUT, "the input is not a valid ApplicationSnapshotInput"
                )
                return
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)

        raw_text = get_message_text(context.message) if context.message else ""
        try:
            input_model = schemas.ApplicationSnapshotInput.model_validate_json(raw_text)
        except ValidationError:
            await self._fail(
                updater, INVALID_INPUT, "the input is not a valid ApplicationSnapshotInput"
            )
            return

        snapshot = schemas.to_application_snapshot(input_model)
        await updater.start_work()
        try:
            credit_opinion = await self._use_case.execute(
                snapshot, workflow_id=context.context_id, task_id=context.task_id
            )
        except DecisaoAgentError as exc:
            await self._fail(updater, error_code_for(exc), str(exc))
            return

        body = schemas.to_credit_opinion(credit_opinion).model_dump_json()
        await updater.add_artifact(
            parts=[new_text_part(body, media_type=_JSON_MEDIA_TYPE)],
            name=_CREDIT_OPINION_ARTIFACT_NAME,
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the task identified by the request context.

        Args:
            context: The request context carrying the task ID to cancel.
            event_queue: The queue to publish the cancellation status update to.

        Raises:
            UnsupportedOperationError: If the request carries no task/context ID to cancel.
        """
        if context.task_id is None or context.context_id is None:
            raise UnsupportedOperationError(
                "decisao-agent cannot cancel a task with no task/context ID."
            )
        updater = TaskUpdater(
            event_queue=event_queue, task_id=context.task_id, context_id=context.context_id
        )
        await updater.cancel()

    async def _fail(self, updater: TaskUpdater, code: str, message: str) -> None:
        """Transition the task to ``TASK_STATE_FAILED`` with a stable JSON error envelope.

        Args:
            updater: The task updater to publish the failure through.
            code: A stable, machine-readable error code.
            message: A short, human-readable description of the failure.
        """
        body = json.dumps({"code": code, "message": message})
        error_message = updater.new_agent_message(
            parts=[new_text_part(body, media_type=_JSON_MEDIA_TYPE)]
        )
        await updater.failed(message=error_message)

    async def _respond_without_a_task(
        self, event_queue: EventQueue, code: str, message: str
    ) -> None:
        """Enqueue a stable JSON error envelope directly, for a request with no message at all.

        No ``Task`` can be created without an incoming message
        (``new_task_from_user_message`` requires one), so this falls back to the "immediate
        response" pattern for this one degenerate case only.

        Args:
            event_queue: The queue to publish the response message to.
            code: A stable, machine-readable error code.
            message: A short, human-readable description of the failure.
        """
        body = json.dumps({"code": code, "message": message})
        await event_queue.enqueue_event(new_text_message(body, media_type=_JSON_MEDIA_TYPE))
