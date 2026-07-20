"""Behavior tests for bureau_mcp's CNPJ format and checksum validation."""

import pytest

from bureau_mcp.domain.cnpj import validate_cnpj
from bureau_mcp.domain.errors import InvalidCnpjError


def test_validate_cnpj_accepts_digits_only_input() -> None:
    assert validate_cnpj("11222333000181") == "11222333000181"


def test_validate_cnpj_accepts_punctuated_input_and_normalizes_it() -> None:
    assert validate_cnpj("11.222.333/0001-81") == "11222333000181"


def test_validate_cnpj_rejects_wrong_length() -> None:
    with pytest.raises(InvalidCnpjError) as exc_info:
        validate_cnpj("112223330001")

    assert exc_info.value.raw == "112223330001"


def test_validate_cnpj_rejects_all_repeated_digits() -> None:
    with pytest.raises(InvalidCnpjError):
        validate_cnpj("11111111111111")


def test_validate_cnpj_rejects_wrong_check_digits() -> None:
    with pytest.raises(InvalidCnpjError):
        validate_cnpj("11222333000199")


def test_validate_cnpj_rejects_non_numeric_garbage() -> None:
    with pytest.raises(InvalidCnpjError):
        validate_cnpj("not-a-cnpj")
