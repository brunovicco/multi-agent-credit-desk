"""Behavior test for DecisaoAgentExecutor.cancel().

The success/error message paths are exercised through the real request-handler machinery in
``tests/contract/test_a2a_message_contract.py`` rather than hand-constructed fake
``RequestContext``/``EventQueue`` objects, per that module's docstring. ``cancel()`` never
touches its arguments, so it is safe and simpler to unit test in isolation.
"""

from typing import Any, cast

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import UnsupportedOperationError

from decisao_agent.entrypoints.a2a_executor import DecisaoAgentExecutor

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_cancel_always_raises_unsupported_operation_error() -> None:
    executor = DecisaoAgentExecutor(use_case=cast(Any, None))

    with pytest.raises(UnsupportedOperationError):
        await executor.cancel(cast(RequestContext, None), cast(EventQueue, None))
