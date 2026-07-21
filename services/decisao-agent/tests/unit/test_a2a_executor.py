"""Behavior test for DecisaoAgentExecutor.cancel()'s defensive guard.

The success/error/cancel-of-a-completed-task paths are exercised through the real
request-handler machinery in ``tests/contract/test_a2a_message_contract.py`` rather than
hand-constructed fake ``RequestContext``/``EventQueue`` objects, per that module's docstring.
This test covers the one branch of ``cancel()`` that is both deterministic and meaningfully
testable in isolation: rejecting a request that carries no task/context ID to cancel, before it
ever touches the (real, SDK-managed) ``EventQueue``.
"""

from typing import Any, cast

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.types import UnsupportedOperationError

from decisao_agent.entrypoints.a2a_executor import DecisaoAgentExecutor

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_cancel_raises_unsupported_operation_error_without_a_task_id() -> None:
    executor = DecisaoAgentExecutor(use_case=cast(Any, None))
    context = RequestContext(call_context=ServerCallContext())

    with pytest.raises(UnsupportedOperationError):
        await executor.cancel(context, cast(EventQueue, None))
