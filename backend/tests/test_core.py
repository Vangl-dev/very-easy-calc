from __future__ import annotations

import pytest

from app.core.competencia import Competencia
from app.core.money import brl, parse_brl, round_brl, to_decimal


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1.234,56", "1234.56"),
        ("R$ 10.000,00", "10000.00"),
        ("1234,56", "1234.56"),
        ("1234.56", "1234.56"),
        ("0,01", "0.01"),
        ("(-1.500,00)", "-1500.00"),
        ("  99,9  ", "99.9"),
        ("1.234.567,89", "1234567.89"),
    ],
)
def test_parse_brl(texto: str, esperado: str) -> None:
    assert parse_brl(texto) == __import__("decimal").Decimal(esperado)


def test_parse_brl_invalido() -> None:
    with pytest.raises(ValueError):
        parse_brl("abc")
    with pytest.raises(ValueError):
        parse_brl("")


def test_to_decimal_tipos() -> None:
    assert to_decimal(10) == to_decimal("10")
    assert to_decimal(0.5) == to_decimal("0.5")
    assert to_decimal("3,14") == to_decimal("3.14")
    with pytest.raises(TypeError):
        to_decimal(True)
    with pytest.raises(TypeError):
        to_decimal(None)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2.345", "2.35"),
        ("2.344", "2.34"),
        ("0.005", "0.01"),
        ("-2.345", "-2.35"),
        ("0", "0.00"),
        ("100", "100.00"),
    ],
)
def test_round_brl_half_up(valor: str, esperado: str) -> None:
    assert round_brl(valor) == __import__("decimal").Decimal(esperado)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (1234.567, "R$ 1.234,57"),
        (-1000, "-R$ 1.000,00"),
        (0, "R$ 0,00"),
        (9999999.999, "R$ 10.000.000,00"),
        ("1518", "R$ 1.518,00"),
    ],
)
def test_formato_brl(valor: object, esperado: str) -> None:
    assert brl(valor) == esperado


def test_competencia_formats() -> None:
    assert Competencia.parse("2026-08") == Competencia(2026, 8)
    assert Competencia.parse("08/2026") == Competencia(2026, 8)
    assert Competencia.parse("8/2026") == Competencia(2026, 8)
    assert Competencia.parse("2026/8") == Competencia(2026, 8)
    assert Competencia.parse(Competencia(2026, 8)) == Competencia(2026, 8)
    assert Competencia.parse((__import__("datetime").date(2026, 8, 17))) == Competencia(2026, 8)
    assert Competencia.parse((2026, 8)) == Competencia(2026, 8)


def test_competencia_labels_e_fechamento_ano() -> None:
    c = Competencia(2026, 8)
    assert c.label == "08/2026"
    assert c.long_label == "Agosto/2026"
    assert c.key == "2026-08"
    assert c.proxima == Competencia(2026, 9)
    assert Competencia(2026, 12).proxima == Competencia(2027, 1)
    assert Competencia(2026, 1).anterior == Competencia(2025, 12)
    assert Competencia(2026, 1) < Competencia(2026, 2)
    assert str(c) == "08/2026"


def test_competencia_invalida() -> None:
    with pytest.raises(ValueError):
        Competencia(2026, 13)
    with pytest.raises(ValueError):
        Competencia(2026, 0)
    with pytest.raises(ValueError):
        Competencia.parse("2026-13")
    with pytest.raises(ValueError):
        Competencia.parse("qualquer")
    with pytest.raises(TypeError):
        Competencia.parse(3.5)
