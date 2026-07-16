"""Shared fixtures for credit_core tests."""

from decimal import Decimal

import pytest

from credit_core import CreditApplicationSnapshot


@pytest.fixture
def healthy_snapshot() -> CreditApplicationSnapshot:
    """A synthetic, financially healthy applicant: every component scores at its maximum."""
    return CreditApplicationSnapshot(
        annual_revenue=Decimal("1000000"),
        total_debt=Decimal("300000"),
        monthly_debt_service=Decimal("10000"),
        monthly_operating_cash_flow=Decimal("25000"),
        bureau_score=Decimal("850"),
        years_in_operation=12,
        requested_amount=Decimal("30000"),
    )
