"""Drift-regression tests: the adapter must match credit_core field-for-field, not spot checks.

This is the executable form of the core architectural decision recorded in
``docs/adr/0011-policy-mcp-sources-credit-core-policy-directly.md``: what policy-mcp reports can
never silently drift from what ``credit_core`` actually enforces.
"""

from decimal import Decimal

import pytest

from credit_core.domain import CriticalFlag
from credit_core.policy import DEMO_POLICY_V1
from policy_mcp.adapters.credit_core_policy_source import CreditCorePolicySource
from policy_mcp.domain.errors import PolicyNotFoundError


@pytest.fixture
def source() -> CreditCorePolicySource:
    return CreditCorePolicySource()


def test_list_versions_returns_exactly_the_demo_policy_version(
    source: CreditCorePolicySource,
) -> None:
    assert source.list_versions() == (DEMO_POLICY_V1.version,)


def test_get_returns_the_canonical_demo_policy_version_string(
    source: CreditCorePolicySource,
) -> None:
    detail = source.get(DEMO_POLICY_V1.version)

    assert detail.version == DEMO_POLICY_V1.version == "credit-core-demo-policy-v1"


def test_get_matches_every_score_component_field_for_field(
    source: CreditCorePolicySource,
) -> None:
    detail = source.get(DEMO_POLICY_V1.version)

    assert len(detail.score_components) == len(DEMO_POLICY_V1.score_components)
    for view, component_policy in zip(
        detail.score_components, DEMO_POLICY_V1.score_components, strict=True
    ):
        assert view.component == component_policy.component.value
        assert view.weight == component_policy.weight
        assert view.direction == component_policy.direction.value
        assert len(view.bands) == len(component_policy.bands)
        for band_view, band in zip(view.bands, component_policy.bands, strict=True):
            assert band_view.boundary == band.boundary
            assert band_view.score == band.score


def test_get_matches_decision_thresholds_field_for_field(source: CreditCorePolicySource) -> None:
    detail = source.get(DEMO_POLICY_V1.version)
    thresholds = detail.decision_thresholds

    assert (
        thresholds.approval_recommendation_minimum_score
        == DEMO_POLICY_V1.approval_recommendation_minimum_score
    )
    assert (
        thresholds.conditional_approval_minimum_score
        == DEMO_POLICY_V1.conditional_approval_minimum_score
    )
    assert (
        thresholds.committee_referral_minimum_score
        == DEMO_POLICY_V1.committee_referral_minimum_score
    )


def test_get_matches_zero_debt_service_metric_value(source: CreditCorePolicySource) -> None:
    detail = source.get(DEMO_POLICY_V1.version)

    assert detail.zero_debt_service_metric_value == DEMO_POLICY_V1.zero_debt_service_metric_value


def test_get_derives_four_approval_authority_tiers_from_the_amount_thresholds(
    source: CreditCorePolicySource,
) -> None:
    detail = source.get(DEMO_POLICY_V1.version)
    tiers = detail.approval_authority_tiers

    assert [tier.authority for tier in tiers] == [
        "ANALYST",
        "SENIOR_ANALYST",
        "CREDIT_COMMITTEE",
        "EXECUTIVE_BOARD",
    ]

    analyst, senior_analyst, credit_committee, executive_board = tiers

    assert analyst.minimum_amount == Decimal("0")
    assert analyst.maximum_amount == DEMO_POLICY_V1.analyst_maximum_amount

    assert senior_analyst.minimum_amount == DEMO_POLICY_V1.analyst_maximum_amount
    assert senior_analyst.maximum_amount == DEMO_POLICY_V1.senior_analyst_maximum_amount

    assert credit_committee.minimum_amount == DEMO_POLICY_V1.senior_analyst_maximum_amount
    assert credit_committee.maximum_amount == DEMO_POLICY_V1.credit_committee_maximum_amount

    assert executive_board.minimum_amount == DEMO_POLICY_V1.credit_committee_maximum_amount
    assert executive_board.maximum_amount is None


def test_get_raises_policy_not_found_for_an_unknown_version(
    source: CreditCorePolicySource,
) -> None:
    with pytest.raises(PolicyNotFoundError) as exc_info:
        source.get("nonexistent-version")

    assert exc_info.value.version == "nonexistent-version"


def test_list_critical_flags_matches_every_credit_core_critical_flag_field_for_field(
    source: CreditCorePolicySource,
) -> None:
    views = source.list_critical_flags()

    assert len(views) == len(list(CriticalFlag))
    for view, flag in zip(views, CriticalFlag, strict=True):
        assert view.name == flag.name
        assert view.value == flag.value
