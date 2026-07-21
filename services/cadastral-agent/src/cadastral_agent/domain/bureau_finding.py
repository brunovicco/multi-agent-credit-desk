"""cadastral-agent's own vocabulary for a bureau-mcp report, translated at the adapter boundary.

Mirrors ``bureau_mcp.domain.report``'s shape but is not imported from ``bureau_mcp``: cadastral-
agent reaches bureau-mcp over the MCP protocol, not as a Python dependency of its domain layer,
so this is its own copy of the vocabulary it needs - the same pattern
``decisao_agent.application.ports.PolicyCatalogSnapshot`` uses instead of importing policy-mcp's
domain types directly.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class NegativeRecordKind(Enum):
    """Closed set of adverse record categories a bureau finding may carry."""

    PROTEST = "PROTEST"
    LAWSUIT = "LAWSUIT"
    BOUNCED_CHECK = "BOUNCED_CHECK"
    OVERDUE_DEBT = "OVERDUE_DEBT"


@dataclass(frozen=True, slots=True)
class NegativeRecordFinding:
    """One adverse record (negativação) against a company, as reported by bureau-mcp.

    Attributes:
        kind: The record's category.
        amount: The monetary amount associated with the record.
        registered_days_ago: How many whole days ago the record was registered.
    """

    kind: NegativeRecordKind
    amount: Decimal
    registered_days_ago: int


@dataclass(frozen=True, slots=True)
class BureauFinding:
    """The bureau-mcp report for one company, as cadastral-agent's KYC policy assesses it.

    Attributes:
        cnpj: The company's canonical, digits-only CNPJ.
        external_score: The external bureau score, on bureau-mcp's 0-1000 scale.
        negative_records: Every adverse record on file for this company, in no particular order.
            An empty tuple means a clean record.
    """

    cnpj: str
    external_score: Decimal
    negative_records: tuple[NegativeRecordFinding, ...]
