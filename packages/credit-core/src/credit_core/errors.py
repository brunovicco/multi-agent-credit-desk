"""Domain-specific exceptions raised by the deterministic credit evaluation core."""


class CreditCoreError(Exception):
    """Base exception for all credit-core domain and policy errors."""


class InvalidCreditApplicationError(CreditCoreError):
    """Raised when a ``CreditApplicationSnapshot`` violates an input invariant."""


class InvalidCreditPolicyError(CreditCoreError):
    """Raised when a ``CreditPolicy`` violates a configuration invariant."""
