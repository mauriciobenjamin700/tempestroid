"""Tests for the Brazilian field validators in :mod:`tempestroid.validators`.

Each validator follows the ``Form`` validator shape: ``None`` when valid, a
PT-BR error message string when invalid.
"""

from __future__ import annotations

from tempestroid import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)

# --- CPF --------------------------------------------------------------------


def test_validate_cpf_accepts_known_valid() -> None:
    assert validate_cpf("52998224725") is None
    # Same number, masked.
    assert validate_cpf("529.982.247-25") is None
    assert validate_cpf("111.444.777-35") is None


def test_validate_cpf_rejects_bad_check_digits() -> None:
    assert validate_cpf("52998224726") is not None
    assert validate_cpf("12345678900") is not None


def test_validate_cpf_rejects_wrong_length() -> None:
    assert validate_cpf("123") is not None
    assert validate_cpf("5299822472") is not None  # 10 digits


def test_validate_cpf_rejects_all_same_digit() -> None:
    assert validate_cpf("00000000000") is not None
    assert validate_cpf("11111111111") is not None


# --- CNPJ -------------------------------------------------------------------


def test_validate_cnpj_accepts_known_valid() -> None:
    assert validate_cnpj("11222333000181") is None
    # Same number, masked.
    assert validate_cnpj("11.222.333/0001-81") is None


def test_validate_cnpj_rejects_bad_check_digits() -> None:
    assert validate_cnpj("11222333000182") is not None


def test_validate_cnpj_rejects_wrong_length() -> None:
    assert validate_cnpj("1122233300018") is not None  # 13 digits
    assert validate_cnpj("abc") is not None


def test_validate_cnpj_rejects_all_same_digit() -> None:
    assert validate_cnpj("00000000000000") is not None
    assert validate_cnpj("11111111111111") is not None


# --- email ------------------------------------------------------------------


def test_validate_email_accepts_valid() -> None:
    assert validate_email("user@example.com") is None
    assert validate_email("a.b+c@sub.domain.co") is None


def test_validate_email_rejects_invalid() -> None:
    assert validate_email("not-an-email") is not None
    assert validate_email("missing@domain") is not None
    assert validate_email("@no-local.com") is not None
    assert validate_email("spaces in@x.com") is not None


# --- phone ------------------------------------------------------------------


def test_validate_phone_accepts_landline_and_mobile() -> None:
    assert validate_phone("1133334444") is None  # 10 digits (landline)
    assert validate_phone("11987654321") is None  # 11 digits (mobile)
    assert validate_phone("(11) 98765-4321") is None  # masked mobile


def test_validate_phone_rejects_wrong_length() -> None:
    assert validate_phone("123") is not None
    assert validate_phone("119876543210") is not None  # 12 digits
