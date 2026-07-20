"""Pydantic wire schemas for the bureau-mcp MCP tool, and explicit domain-to-wire mappings.

Every schema mirrors ``credit_desk_contracts._base.StrictContract``'s conventions (see
``packages/contracts/src/credit_desk_contracts/_base.py``): unknown fields are rejected
(``extra="forbid"``) and instances are immutable once constructed (``frozen=True``). The
convention is reimplemented locally rather than imported, since ``StrictContract`` is a
private, unexported module of a sibling workspace package - matching
``policy_mcp.entrypoints.schemas``. Mapping from ``bureau_mcp.domain.report`` types to these
schemas is explicit, one field at a time - never automatic dataclass serialization, so a schema
change is always a deliberate, reviewable edit.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from bureau_mcp.domain import report


class _BureauMcpContract(BaseModel):
    """Base model for every bureau-mcp wire schema: immutable and closed to unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class NegativeRecord(_BureauMcpContract):
    """Wire schema for one adverse record. See ``bureau_mcp.domain.report.NegativeRecord``."""

    kind: str
    amount: Decimal
    registered_days_ago: int


class BureauReport(_BureauMcpContract):
    """Wire schema returned by the ``get_bureau_report`` tool.

    See ``bureau_mcp.domain.report.BureauReport``.
    """

    cnpj: str
    external_score: Decimal
    negative_records: tuple[NegativeRecord, ...]


def to_negative_record(record: report.NegativeRecord) -> NegativeRecord:
    """Map a ``NegativeRecord`` domain value to its wire schema.

    Args:
        record: The domain negative record to map.

    Returns:
        The equivalent wire schema.
    """
    return NegativeRecord(
        kind=record.kind.value,
        amount=record.amount,
        registered_days_ago=record.registered_days_ago,
    )


def to_bureau_report(bureau_report: report.BureauReport) -> BureauReport:
    """Map a ``BureauReport`` domain value to its wire schema.

    Args:
        bureau_report: The domain bureau report to map.

    Returns:
        The equivalent wire schema.
    """
    return BureauReport(
        cnpj=bureau_report.cnpj,
        external_score=bureau_report.external_score,
        negative_records=tuple(
            to_negative_record(record) for record in bureau_report.negative_records
        ),
    )
