"""Behavior tests for decisao_agent's ApplicationSnapshot value object."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from decisao_agent.domain.snapshot import ApplicationSnapshot


def _snapshot(critical_flags: frozenset[str] = frozenset()) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        annual_revenue=Decimal("5000000"),
        total_debt=Decimal("1200000"),
        monthly_debt_service=Decimal("40000"),
        monthly_operating_cash_flow=Decimal("180000"),
        bureau_score=Decimal("780"),
        years_in_operation=6,
        requested_amount=Decimal("500000"),
        critical_flags=critical_flags,
    )


def test_application_snapshot_is_frozen() -> None:
    snapshot = _snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.annual_revenue = Decimal("0")  # type: ignore[misc]


def test_application_snapshot_equality_is_structural() -> None:
    first = _snapshot()
    second = _snapshot()

    assert first == second
    assert first is not second


def test_application_snapshot_holds_critical_flag_names() -> None:
    snapshot = _snapshot(critical_flags=frozenset({"FRAUD_ALERT"}))

    assert snapshot.critical_flags == frozenset({"FRAUD_ALERT"})
