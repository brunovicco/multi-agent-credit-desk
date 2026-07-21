"""Table-driven behavior tests for cadastral-agent's deterministic KYC screening policy.

Includes bureau-mcp's three fixture personas (see
``services/bureau-mcp/src/bureau_mcp/adapters/synthetic_bureau_source.py``) to prove the policy
produces the three distinct decisions ``docs/adr/0016-cadastral-agent-kyc-screening-policy.md``
describes, using the same data the real bureau-mcp dataset would return for them.
"""

from decimal import Decimal

import pytest

from cadastral_agent.domain.assessment import KycDecision
from cadastral_agent.domain.bureau_finding import (
    BureauFinding,
    NegativeRecordFinding,
    NegativeRecordKind,
)
from cadastral_agent.domain.kyc_policy import assess

_CNPJ = "11222333000181"


def _finding(external_score: str, records: tuple[NegativeRecordFinding, ...] = ()) -> BureauFinding:
    return BureauFinding(
        cnpj=_CNPJ, external_score=Decimal(external_score), negative_records=records
    )


def _record(kind: NegativeRecordKind) -> NegativeRecordFinding:
    return NegativeRecordFinding(kind=kind, amount=Decimal("1000.00"), registered_days_ago=10)


def test_approves_a_clean_record_with_a_healthy_score() -> None:
    assessment = assess(_finding("850"))

    assert assessment.decision == KycDecision.APPROVED
    assert assessment.reason_codes == ()


def test_refers_to_committee_for_an_overdue_debt_record() -> None:
    assessment = assess(
        _finding("800", (_record(NegativeRecordKind.OVERDUE_DEBT),)),
    )

    assert assessment.decision == KycDecision.COMMITTEE_REFERRAL
    assert assessment.reason_codes == ("OVERDUE_DEBT_ON_FILE",)


def test_refers_to_committee_for_a_bounced_check_record() -> None:
    assessment = assess(
        _finding("800", (_record(NegativeRecordKind.BOUNCED_CHECK),)),
    )

    assert assessment.decision == KycDecision.COMMITTEE_REFERRAL
    assert assessment.reason_codes == ("BOUNCED_CHECK_ON_FILE",)


def test_refers_to_committee_for_a_low_score_alone() -> None:
    assessment = assess(_finding("599"))

    assert assessment.decision == KycDecision.COMMITTEE_REFERRAL
    assert assessment.reason_codes == ("LOW_EXTERNAL_SCORE",)


def test_approves_the_boundary_score() -> None:
    assessment = assess(_finding("600"))

    assert assessment.decision == KycDecision.APPROVED


def test_blocks_for_a_lawsuit_record_even_with_a_healthy_score() -> None:
    assessment = assess(
        _finding("900", (_record(NegativeRecordKind.LAWSUIT),)),
    )

    assert assessment.decision == KycDecision.BLOCKED
    assert assessment.reason_codes == ("LAWSUIT_ON_FILE",)


def test_blocks_for_a_protest_record() -> None:
    assessment = assess(
        _finding("900", (_record(NegativeRecordKind.PROTEST),)),
    )

    assert assessment.decision == KycDecision.BLOCKED
    assert assessment.reason_codes == ("PROTEST_ON_FILE",)


def test_blocking_takes_precedence_over_referral_signals() -> None:
    assessment = assess(
        _finding(
            "400",
            (_record(NegativeRecordKind.LAWSUIT), _record(NegativeRecordKind.OVERDUE_DEBT)),
        ),
    )

    assert assessment.decision == KycDecision.BLOCKED
    assert assessment.reason_codes == (
        "LAWSUIT_ON_FILE",
        "LOW_EXTERNAL_SCORE",
        "OVERDUE_DEBT_ON_FILE",
    )


def test_assessment_preserves_cnpj_and_score() -> None:
    assessment = assess(_finding("850"))

    assert assessment.cnpj == _CNPJ
    assert assessment.external_score == Decimal("850")


@pytest.mark.parametrize(
    ("external_score", "record_kinds", "expected_decision"),
    [
        pytest.param("850", (), KycDecision.APPROVED, id="healthy_persona"),
        pytest.param(
            "520",
            (NegativeRecordKind.OVERDUE_DEBT,),
            KycDecision.COMMITTEE_REFERRAL,
            id="leveraged_persona",
        ),
        pytest.param(
            "180",
            (NegativeRecordKind.PROTEST, NegativeRecordKind.LAWSUIT),
            KycDecision.BLOCKED,
            id="negative_history_persona",
        ),
    ],
)
def test_matches_bureau_mcp_fixture_personas(
    external_score: str,
    record_kinds: tuple[NegativeRecordKind, ...],
    expected_decision: KycDecision,
) -> None:
    finding = _finding(external_score, tuple(_record(kind) for kind in record_kinds))

    assert assess(finding).decision == expected_decision
