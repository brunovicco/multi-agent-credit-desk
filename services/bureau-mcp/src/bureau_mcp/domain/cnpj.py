"""CNPJ (Brazilian legal-entity registry number) format and checksum validation.

A valid CNPJ is a business-defined identity concept - who is being looked up - not a transport
detail, so the Receita Federal mod-11 checksum lives here as pure domain logic rather than in
``entrypoints/schemas.py``. This module has no I/O and no framework dependency.
"""

import re

from bureau_mcp.domain.errors import InvalidCnpjError

_NON_DIGITS = re.compile(r"\D+")
_CNPJ_LENGTH = 14
_FIRST_CHECK_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_CHECK_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def validate_cnpj(raw: str) -> str:
    """Normalize and validate a CNPJ, accepting either punctuated or digits-only input.

    Args:
        raw: The CNPJ as provided (e.g. ``"11.222.333/0001-81"`` or ``"11222333000181"``).

    Returns:
        The canonical, digits-only, 14-character CNPJ.

    Raises:
        InvalidCnpjError: If ``raw`` does not normalize to 14 digits, is one of the
            all-repeated-digit sequences Receita Federal never issues, or its check digits do
            not match the ones computed from its first 12 digits.
    """
    digits = _NON_DIGITS.sub("", raw)
    if len(digits) != _CNPJ_LENGTH or len(set(digits)) == 1:
        raise InvalidCnpjError(raw)
    if digits != _with_check_digits(digits[:12]):
        raise InvalidCnpjError(raw)
    return digits


def _with_check_digits(root_and_branch: str) -> str:
    """Append the two Receita Federal check digits to a 12-digit root-and-branch prefix.

    Args:
        root_and_branch: The first 12 digits of a CNPJ (8-digit root plus 4-digit branch).

    Returns:
        The full 14-digit CNPJ with valid check digits appended.
    """
    first_check_digit = _check_digit(root_and_branch, _FIRST_CHECK_WEIGHTS)
    second_check_digit = _check_digit(root_and_branch + first_check_digit, _SECOND_CHECK_WEIGHTS)
    return root_and_branch + first_check_digit + second_check_digit


def _check_digit(digits: str, weights: tuple[int, ...]) -> str:
    """Compute one Receita Federal mod-11 check digit.

    Args:
        digits: The digit string to weight and sum, matching ``weights`` in length.
        weights: The positional weights to apply, most significant digit first.

    Returns:
        The single computed check digit, as a one-character string.
    """
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights, strict=True))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)
