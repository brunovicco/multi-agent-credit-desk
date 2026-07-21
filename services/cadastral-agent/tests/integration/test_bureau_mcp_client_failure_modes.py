"""Proves BureauMcpClient translates real subprocess/transport failures, not just tool errors.

Spawns a real (deliberately broken) subprocess - no in-process fake - to prove
``BureauMcpClient.get_report()`` never lets an untranslated exception escape, and that the
timeout actually bounds a hung process. Complements
``tests/unit/test_bureau_mcp_client.py``, which only exercises the pure JSON-parsing helpers.
"""

import sys

import pytest

from cadastral_agent.adapters.bureau_mcp_client import BureauMcpClient
from cadastral_agent.domain.errors import BureauReportUnavailableError

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

_SHORT_TIMEOUT_SECONDS = 5.0
_CNPJ = "11222333000181"


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


async def test_get_report_raises_bureau_report_unavailable_for_a_nonexistent_command() -> None:
    client = BureauMcpClient(
        command="/no/such/executable-cadastral-agent-test",
        timeout_seconds=_SHORT_TIMEOUT_SECONDS,
    )

    with pytest.raises(BureauReportUnavailableError):
        await client.get_report(_CNPJ)


async def test_get_report_raises_bureau_report_unavailable_when_the_process_never_responds() -> (
    None
):
    client = BureauMcpClient(
        command=sys.executable,
        args=("-c", "import time; time.sleep(60)"),
        timeout_seconds=1.0,
    )

    with pytest.raises(BureauReportUnavailableError):
        await client.get_report(_CNPJ)
