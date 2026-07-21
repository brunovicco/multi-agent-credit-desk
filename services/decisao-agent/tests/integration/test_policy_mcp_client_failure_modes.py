"""Proves PolicyMcpClient translates real subprocess/transport failures, not just tool errors.

Spawns a real (deliberately broken) subprocess - no in-process fake - to prove
``PolicyMcpClient.snapshot()`` never lets an untranslated exception escape, and that the timeout
actually bounds a hung process. Complements
``tests/unit/test_policy_mcp_client.py``, which only exercises the pure JSON-parsing helper.
"""

import sys

import pytest

from decisao_agent.adapters.policy_mcp_client import PolicyMcpClient
from decisao_agent.domain.errors import PolicyCatalogUnavailableError

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

_SHORT_TIMEOUT_SECONDS = 5.0


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_snapshot_raises_policy_catalog_unavailable_for_a_nonexistent_command() -> None:
    client = PolicyMcpClient(
        command="/no/such/executable-decisao-agent-test",
        timeout_seconds=_SHORT_TIMEOUT_SECONDS,
    )

    with pytest.raises(PolicyCatalogUnavailableError):
        await client.snapshot()


async def test_snapshot_raises_policy_catalog_unavailable_when_the_process_never_responds() -> None:
    client = PolicyMcpClient(
        command=sys.executable,
        args=("-c", "import time; time.sleep(60)"),
        timeout_seconds=1.0,
    )

    with pytest.raises(PolicyCatalogUnavailableError):
        await client.snapshot()
