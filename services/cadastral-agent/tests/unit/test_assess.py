"""Behavior tests for AssessCadastralApplicationUseCase against a fake BureauReportPort.

Per .claude/rules/testing.md, unit tests isolate external processes: this suite never spawns
bureau-mcp. The real subprocess roundtrip is covered by
``tests/integration/test_cadastral_agent_cli_stdio_roundtrip.py``.
"""

from decimal import Decimal

import pytest

from cadastral_agent.application.assess import AssessCadastralApplicationUseCase
from cadastral_agent.domain.assessment import KycDecision
from cadastral_agent.domain.bureau_finding import BureauFinding
from cadastral_agent.domain.errors import CnpjNotFoundError

pytestmark = pytest.mark.anyio

_CNPJ = "11222333000181"


@pytest.fixture
def anyio_backend() -> str:
    """Run this suite's async tests on asyncio only (no trio dependency)."""
    return "asyncio"


class _FakeBureauReportPort:
    def __init__(
        self, finding: BureauFinding | None = None, error: Exception | None = None
    ) -> None:
        self._finding = finding
        self._error = error

    async def get_report(self, cnpj: str) -> BureauFinding:
        if self._error is not None:
            raise self._error
        assert self._finding is not None
        return self._finding


async def test_execute_returns_the_policy_outcome_for_the_fetched_finding() -> None:
    finding = BureauFinding(cnpj=_CNPJ, external_score=Decimal("850"), negative_records=())
    use_case = AssessCadastralApplicationUseCase(bureau_report_port=_FakeBureauReportPort(finding))

    assessment = await use_case.execute(_CNPJ)

    assert assessment.decision == KycDecision.APPROVED
    assert assessment.cnpj == _CNPJ


async def test_execute_propagates_the_port_s_error() -> None:
    use_case = AssessCadastralApplicationUseCase(
        bureau_report_port=_FakeBureauReportPort(error=CnpjNotFoundError())
    )

    with pytest.raises(CnpjNotFoundError):
        await use_case.execute(_CNPJ)
