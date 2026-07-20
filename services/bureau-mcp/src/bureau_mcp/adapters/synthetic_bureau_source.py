"""Adapter that sources bureau reports from a fixed, in-memory synthetic dataset.

Unlike ``policy-mcp``, which reads ``credit_core`` directly to avoid drifting from a real
system of record, bureau-mcp has no equivalent: no real credit-bureau connection exists or is
planned (see ``docs/adr/0009-reuse-existing-mcp-servers.md``). This adapter *is* bureau-mcp's
system of record - a small, fixed set of synthetic company profiles matching the three demo
personas from ``docs/architecture-blueprint.md`` (saudável / healthy, alavancada / leveraged,
negativada / negative-history), keyed by CNPJ. Every CNPJ below is a synthetic, structurally
valid (Receita Federal mod-11 checksum) identifier invented for this project; none identifies a
real company.
"""

from decimal import Decimal

from bureau_mcp.domain.errors import CnpjNotFoundError
from bureau_mcp.domain.report import BureauReport, NegativeRecord, NegativeRecordKind

_HEALTHY_CNPJ = "11222333000181"
_LEVERAGED_CNPJ = "22333444000181"
_NEGATIVE_HISTORY_CNPJ = "33444555000181"

_CATALOG: dict[str, BureauReport] = {
    _HEALTHY_CNPJ: BureauReport(
        cnpj=_HEALTHY_CNPJ,
        external_score=Decimal("850"),
        negative_records=(),
    ),
    _LEVERAGED_CNPJ: BureauReport(
        cnpj=_LEVERAGED_CNPJ,
        external_score=Decimal("520"),
        negative_records=(
            NegativeRecord(
                kind=NegativeRecordKind.OVERDUE_DEBT,
                amount=Decimal("15000.00"),
                registered_days_ago=120,
            ),
        ),
    ),
    _NEGATIVE_HISTORY_CNPJ: BureauReport(
        cnpj=_NEGATIVE_HISTORY_CNPJ,
        external_score=Decimal("180"),
        negative_records=(
            NegativeRecord(
                kind=NegativeRecordKind.PROTEST,
                amount=Decimal("42000.00"),
                registered_days_ago=45,
            ),
            NegativeRecord(
                kind=NegativeRecordKind.LAWSUIT,
                amount=Decimal("120000.00"),
                registered_days_ago=200,
            ),
        ),
    ),
}


class SyntheticBureauSource:
    """``BureauLookupPort`` implementation backed by a fixed synthetic dataset."""

    def get_report(self, cnpj: str) -> BureauReport:
        """Return the synthetic bureau report for one company.

        Args:
            cnpj: The company's canonical, digits-only, 14-character CNPJ.

        Returns:
            The bureau report for ``cnpj``.

        Raises:
            CnpjNotFoundError: If ``cnpj`` is not one of this dataset's known CNPJs.
        """
        report = _CATALOG.get(cnpj)
        if report is None:
            raise CnpjNotFoundError(cnpj)
        return report
