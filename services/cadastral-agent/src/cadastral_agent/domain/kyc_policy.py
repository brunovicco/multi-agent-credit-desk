"""cadastral-agent's deterministic KYC screening policy.

Pure, in-process rules over a ``BureauFinding`` - no I/O, no framework types. Plays the same role
``credit_core`` plays for decisao-agent: the one place business rules live, kept separate from how
bureau-mcp is actually reached. There is no external KYC/AML specification behind these
thresholds; they were defined for this milestone and are expected to be revisited once real
requirements exist - see ``docs/adr/0016-cadastral-agent-kyc-screening-policy.md``.
"""

from decimal import Decimal

from cadastral_agent.domain.assessment import KycAssessment, KycDecision
from cadastral_agent.domain.bureau_finding import BureauFinding, NegativeRecordKind

_BLOCKING_RECORD_KINDS = frozenset({NegativeRecordKind.LAWSUIT, NegativeRecordKind.PROTEST})
_REFERRAL_RECORD_KINDS = frozenset(
    {NegativeRecordKind.OVERDUE_DEBT, NegativeRecordKind.BOUNCED_CHECK}
)
_MIN_APPROVED_SCORE = Decimal("600")

_REASON_CODE_BY_RECORD_KIND: dict[NegativeRecordKind, str] = {
    NegativeRecordKind.LAWSUIT: "LAWSUIT_ON_FILE",
    NegativeRecordKind.PROTEST: "PROTEST_ON_FILE",
    NegativeRecordKind.OVERDUE_DEBT: "OVERDUE_DEBT_ON_FILE",
    NegativeRecordKind.BOUNCED_CHECK: "BOUNCED_CHECK_ON_FILE",
}
_LOW_EXTERNAL_SCORE_REASON_CODE = "LOW_EXTERNAL_SCORE"


def assess(finding: BureauFinding) -> KycAssessment:
    """Screen one bureau finding against cadastral-agent's deterministic KYC policy.

    Args:
        finding: The bureau finding to screen.

    Returns:
        ``BLOCKED`` if any ``LAWSUIT`` or ``PROTEST`` record is on file; otherwise
        ``COMMITTEE_REFERRAL`` if any ``OVERDUE_DEBT`` or ``BOUNCED_CHECK`` record is on file or
        ``external_score`` falls below the minimum approved score; otherwise ``APPROVED``.
    """
    record_kinds = {record.kind for record in finding.negative_records}
    low_score = finding.external_score < _MIN_APPROVED_SCORE

    if record_kinds & _BLOCKING_RECORD_KINDS:
        decision = KycDecision.BLOCKED
    elif record_kinds & _REFERRAL_RECORD_KINDS or low_score:
        decision = KycDecision.COMMITTEE_REFERRAL
    else:
        decision = KycDecision.APPROVED

    reason_codes = [_REASON_CODE_BY_RECORD_KIND[kind] for kind in record_kinds]
    if low_score:
        reason_codes.append(_LOW_EXTERNAL_SCORE_REASON_CODE)

    return KycAssessment(
        cnpj=finding.cnpj,
        external_score=finding.external_score,
        decision=decision,
        reason_codes=tuple(sorted(reason_codes)),
    )
