from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.core.money import round_brl
from app.indexers import CoverageError
from app.indexers.salario_minimo import ARQUIVO_PADRAO, KEY, SalarioMinimo
from app.indexers.base import carregar_json


@pytest.fixture(scope="module")
def sm() -> SalarioMinimo:
    return SalarioMinimo.carregar()


def test_metadata(sm: SalarioMinimo) -> None:
    meta = sm.metadata
    assert meta.key == KEY
    assert meta.name == "Salário mínimo"
    assert meta.kind == "salario"
    assert meta.source == "Ipeadata / Ministério da Economia"
    assert meta.version == "2026.12"
    assert meta.cobertura.inicio == Competencia(1994, 7)
    assert meta.cobertura.fim == Competencia(2026, 12)
    assert meta.total_records == 390
    assert "anteriores a 07/1994" in meta.note
    assert "ipeadata.gov.br" in meta.source_url


@pytest.mark.parametrize(
    ("competencia", "esperado"),
    [
        ("1994-07", "64.79"),
        ("1994-12", "70.00"),
        ("2021-01", "1100.00"),
        ("2023-01", "1302.00"),
        ("2024-01", "1412.00"),
        ("2025-01", "1518.00"),
        ("2026-01", "1621.00"),
        ("2026-12", "1621.00"),
    ],
)
def test_valores_oficiais(sm: SalarioMinimo, competencia: str, esperado: str) -> None:
    assert sm.salario(competencia) == Decimal(esperado)


def test_fora_da_cobertura(sm: SalarioMinimo) -> None:
    with pytest.raises(CoverageError) as exc:
        sm.salario(Competencia(1994, 6))
    assert "06/1994" in str(exc.value)
    assert "07/1994" in str(exc.value)
    with pytest.raises(CoverageError):
        sm.salario(Competencia(2027, 1))


def test_proveniencia_ipeadata() -> None:
    with (ARQUIVO_PADRAO.parent / "salario_minimo_ipea_raw.json").open(encoding="utf-8") as h:
        bruto = {r["VALDATA"][:7]: r for r in json.load(h)}
    fatores = carregar_json(ARQUIVO_PADRAO)["factors"]
    assert len(fatores) == 390
    for fator in fatores:
        chave = f"{fator['year']:04d}-{fator['month']:02d}"
        registro = bruto[chave]
        esperado = round_brl(registro["VALVALOR"])
        obtido = round_brl(fator["factor"])
        assert obtido == esperado
        assert obtido == Decimal(str(fator["factor"])).quantize(Decimal("0.01"))
