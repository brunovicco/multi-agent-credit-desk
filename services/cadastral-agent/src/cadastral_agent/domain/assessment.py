"""cadastral-agent's own KYC assessment outcome vocabulary."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class KycDecision(Enum):
    """The three possible outcomes of a cadastral-agent KYC assessment."""

    APPROVED = "APPROVED"
    COMMITTEE_REFERRAL = "COMMITTEE_REFERRAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class KycAssessment:
    """The structured, reproducible outcome of screening one company's KYC standing.

    Attributes:
        cnpj: The assessed company's canonical, digits-only CNPJ.
        external_score: The external bureau score the assessment was based on.
        decision: The KYC screening decision.
        reason_codes: Every stable reason code for an adverse signal found in the report
            (negative records on file, a low external score), sorted - a full audit trail, not
            only the signal(s) that determined ``decision``. Empty when ``decision`` is
            ``APPROVED`` on a clean record with a healthy score.
    """

    cnpj: str
    external_score: Decimal
    decision: KycDecision
    reason_codes: tuple[str, ...]
