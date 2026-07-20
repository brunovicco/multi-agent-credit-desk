"""Behavior tests for PolicyCatalogQueries against a fake port, isolated from credit_core.

Per .claude/rules/testing.md, unit tests isolate external dependencies: this suite never imports
credit_core, only a hand-written fake that implements PolicyCatalogPort structurally.
"""

from decimal import Decimal

import pytest

from policy_mcp.application.queries import PolicyCatalogQueries
from policy_mcp.domain.catalog import (
    ApprovalAuthorityTier,
    CriticalFlagView,
    DecisionThresholds,
    PolicyDetail,
    ScoreBandView,
    ScoreComponentView,
)
from policy_mcp.domain.errors import PolicyNotFoundError

_THRESHOLDS = DecisionThresholds(
    approval_recommendation_minimum_score=Decimal("80"),
    conditional_approval_minimum_score=Decimal("60"),
    committee_referral_minimum_score=Decimal("40"),
)

_FAKE_DETAIL = PolicyDetail(
    version="fake-policy-v1",
    score_components=(
        ScoreComponentView(
            component="BUREAU_SCORE",
            weight=Decimal("1.00"),
            direction="HIGHER_IS_BETTER",
            bands=(ScoreBandView(boundary=Decimal("0"), score=Decimal("0")),),
        ),
    ),
    decision_thresholds=_THRESHOLDS,
    approval_authority_tiers=(
        ApprovalAuthorityTier(
            authority="ANALYST", minimum_amount=Decimal("0"), maximum_amount=Decimal("1000")
        ),
        ApprovalAuthorityTier(
            authority="EXECUTIVE_BOARD", minimum_amount=Decimal("1000"), maximum_amount=None
        ),
    ),
    zero_debt_service_metric_value=Decimal("999"),
)

_FAKE_CRITICAL_FLAGS = (
    CriticalFlagView(name="FRAUD_ALERT", value="FRAUD_ALERT"),
    CriticalFlagView(name="BANKRUPTCY_FILING", value="BANKRUPTCY_FILING"),
)


class _FakePolicyCatalogPort:
    """A hand-written test double implementing PolicyCatalogPort structurally."""

    def __init__(
        self,
        versions: tuple[str, ...] = (_FAKE_DETAIL.version,),
        detail: PolicyDetail = _FAKE_DETAIL,
        critical_flags: tuple[CriticalFlagView, ...] = _FAKE_CRITICAL_FLAGS,
    ) -> None:
        self._versions = versions
        self._detail = detail
        self._critical_flags = critical_flags

    def list_versions(self) -> tuple[str, ...]:
        return self._versions

    def get(self, version: str) -> PolicyDetail:
        if version not in self._versions:
            raise PolicyNotFoundError(version)
        return self._detail

    def list_critical_flags(self) -> tuple[CriticalFlagView, ...]:
        return self._critical_flags


def test_list_policies_summarizes_every_known_version() -> None:
    queries = PolicyCatalogQueries(_FakePolicyCatalogPort())

    summaries = queries.list_policies()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.version == "fake-policy-v1"
    assert summary.score_component_count == 1
    assert summary.approval_authority_tier_count == 2
    assert summary.decision_thresholds == _THRESHOLDS


def test_list_policies_returns_one_summary_per_version() -> None:
    queries = PolicyCatalogQueries(
        _FakePolicyCatalogPort(versions=("fake-policy-v1", "fake-policy-v1"))
    )

    summaries = queries.list_policies()

    assert len(summaries) == 2
    assert all(summary.version == "fake-policy-v1" for summary in summaries)


def test_get_policy_returns_the_port_detail_unchanged() -> None:
    queries = PolicyCatalogQueries(_FakePolicyCatalogPort())

    detail = queries.get_policy("fake-policy-v1")

    assert detail is _FAKE_DETAIL


def test_get_policy_raises_policy_not_found_for_unknown_version() -> None:
    queries = PolicyCatalogQueries(_FakePolicyCatalogPort())

    with pytest.raises(PolicyNotFoundError) as exc_info:
        queries.get_policy("unknown-version")

    assert exc_info.value.version == "unknown-version"


def test_list_critical_flags_returns_the_port_flags_unchanged() -> None:
    queries = PolicyCatalogQueries(_FakePolicyCatalogPort())

    flags = queries.list_critical_flags()

    assert flags == _FAKE_CRITICAL_FLAGS
