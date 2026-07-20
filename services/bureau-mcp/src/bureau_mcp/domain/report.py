"""bureau-mcp's own vocabulary for the synthetic credit-bureau report it serves.

These are frozen, immutable Value Objects: plain data holders with no behavior beyond
structural equality, no I/O, and no framework types. ``external_score`` uses the same 0-1000
scale as ``credit_core.domain.CreditApplicationSnapshot.bureau_score`` so a report can be fed
into ``credit_core`` unchanged by a future consumer, without bureau-mcp importing
``credit_core`` itself - unlike policy-mcp, bureau-mcp has no real system of record to read
from (see ``docs/adr/0009-reuse-existing-mcp-servers.md``), so this vocabulary is not a
translation of another package's types.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class NegativeRecordKind(Enum):
    """Closed set of synthetic negative-record categories a bureau report may carry."""

    PROTEST = "PROTEST"
    LAWSUIT = "LAWSUIT"
    BOUNCED_CHECK = "BOUNCED_CHECK"
    OVERDUE_DEBT = "OVERDUE_DEBT"


@dataclass(frozen=True, slots=True)
class NegativeRecord:
    """One synthetic adverse record (negativação) against a company.

    Attributes:
        kind: The record's category.
        amount: The monetary amount associated with the record, expected non-negative. Not
            enforced here: the only producer today is the fixed dataset in
            ``adapters.synthetic_bureau_source``, which satisfies this by construction.
        registered_days_ago: How many whole days ago the record was registered, expected
            non-negative. Not enforced here, for the same reason as ``amount``.
    """

    kind: NegativeRecordKind
    amount: Decimal
    registered_days_ago: int


@dataclass(frozen=True, slots=True)
class BureauReport:
    """A synthetic credit-bureau report for one company.

    Attributes:
        cnpj: The company's canonical, digits-only, 14-character CNPJ.
        external_score: External bureau score on a 0-1000 scale, expected to fall within that
            range. Not enforced here: the only producer today is the fixed dataset in
            ``adapters.synthetic_bureau_source``, which satisfies this by construction.
        negative_records: Every adverse record on file for this company, in no particular
            order. An empty tuple means a clean record.
    """

    cnpj: str
    external_score: Decimal
    negative_records: tuple[NegativeRecord, ...]
