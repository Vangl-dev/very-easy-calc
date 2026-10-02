from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.competencia import Competencia
from app.indexers import CoverageError, IndexerError, SeriesIntegrityError, obter
from app.indexers.base import metadados_de_arquivo, serie_de_fatores, validar_serie
from app.indexers.tjsp import KEY, TabelaPraticaTJSP


@pytest.fixture(scope="module")
def tjsp() -> TabelaPraticaTJSP:
    return TabelaPraticaTJSP.carregar()


def test_metadata_oficial(tjsp: TabelaPraticaTJSP) -> None:
    meta = tjsp.metadata
    assert meta.key == KEY
    assert meta.name == "Tabela Prática TJSP"
    assert meta.kind == "correcao"
    assert meta.source == "AASP"
    assert meta.version == "2026.09"
    assert meta.updated_at == "2026-10-02"
    assert meta.cobertura.inicio == Competencia(1992, 1)
    assert meta.cobertura.fim == Competencia(2026, 9)
    assert meta.total_records == 417
    assert meta.cobertura.total == 417
    assert "aasp.org.br" in meta.source_url


def test_fatores_conhecidos(tjsp: TabelaPraticaTJSP) -> None:
    assert tjsp.valor("1992-01") == Decimal("1000")
    assert tjsp.valor("1995-01") == Decimal("1.133251")
    assert tjsp.valor("2026-06") == Decimal("8.560658")
    assert tjsp.valor("2026-08") == Decimal("8.600913")
    assert tjsp.valor("2026-09") == Decimal("8.566509")
    assert tjsp.valor(Competencia(2026, 9)) == Decimal("8.566509")


def test_exemplo_oficial_aasp(tjsp: TabelaPraticaTJSP) -> None:
    corrigido = tjsp.atualizar("1000", Competencia(1995, 1), Competencia(2026, 9))
    assert corrigido.quantize(Decimal("0.01")) == Decimal("7559.23")


def test_nao_usa_silenciosamente_indice_fora_da_cobertura(tjsp: TabelaPraticaTJSP) -> None:
    with pytest.raises(CoverageError) as antes:
        tjsp.valor(Competencia(1991, 12))
    assert "12/1991" in str(antes.value)
    with pytest.raises(CoverageError) as depois:
        tjsp.valor(Competencia(2026, 10))
    assert "10/2026" in str(depois.value)
    assert "09/2026" in str(depois.value)
    assert "01/1992" in str(depois.value)


def test_razao_e_simetrica(tjsp: TabelaPraticaTJSP) -> None:
    direto = tjsp.razao(Competencia(2020, 1), Competencia(2026, 8))
    inverso = tjsp.razao(Competencia(2026, 8), Competencia(2020, 1))
    assert direto * inverso == Decimal("1")


def test_registry(tjsp: TabelaPraticaTJSP) -> None:
    assert KEY in __import__("app.indexers", fromlist=["chaves"]).chaves()
    assert obter(KEY).metadata.version == "2026.09"
    with pytest.raises(IndexerError):
        obter("nao_existe")


def test_serie_com_lacuna_e_rejeitada(tmp_path: Path) -> None:
    dados = {
        "metadata": {
            "source": "X",
            "sourceUrl": "u",
            "version": "1",
            "updatedAt": "2026-01-01",
        },
        "factors": [
            {"year": 2025, "month": 1, "factor": 1},
            {"year": 2025, "month": 3, "factor": 1.1},
        ],
    }
    caminho = tmp_path / "tabela.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(SeriesIntegrityError):
        TabelaPraticaTJSP.carregar(caminho)


def test_serie_duplicada_e_rejeitada() -> None:
    with pytest.raises(SeriesIntegrityError):
        serie_de_fatores(
            [
                {"year": 2025, "month": 1, "factor": 1},
                {"year": 2025, "month": 1, "factor": 2},
                {"year": 2025, "month": 2, "factor": 3},
            ]
        )


def test_valor_nao_positivo_e_rejeitado() -> None:
    serie = {Competencia(2025, 1): Decimal("0")}
    with pytest.raises(SeriesIntegrityError):
        validar_serie(serie, "teste")


def test_metadata_de_arquivo_detecta_fatores_invalidos() -> None:
    with pytest.raises(IndexerError):
        metadados_de_arquivo({"metadata": {}}, "k", "n", "correcao")
    with pytest.raises(IndexerError):
        metadados_de_arquivo({"metadata": {}, "factors": []}, "k", "n", "correcao")
    with pytest.raises(ValueError):
        metadados_de_arquivo(
            {"metadata": {}, "factors": [{"year": 2025, "month": 1, "factor": 1}]},
            "k",
            "n",
            "tipo_invalido",
        )


def test_serie_de_fatores_converte_decimal() -> None:
    serie = serie_de_fatores([{"year": 2025, "month": 1, "factor": 1.5}])
    assert serie[Competencia(2025, 1)] == Decimal("1.5")
