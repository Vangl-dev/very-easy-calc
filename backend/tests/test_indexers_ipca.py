from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.competencia import Competencia
from app.indexers import CoverageError, IndexerError, SeriesIntegrityError, chaves, obter
from app.indexers.ipca import KEY, Ipca
from app.indexers.tjsp import KEY as TjspKey

D = Decimal
DADOS = Path(__file__).resolve().parents[1] / "app" / "data"


@pytest.fixture(scope="module")
def ipca() -> Ipca:
    return Ipca.carregar()


def test_metadata_oficial(ipca: Ipca) -> None:
    meta = ipca.metadata
    assert meta.key == KEY == "ipca"
    assert meta.name == "IPCA (IBGE)"
    assert meta.kind == "correcao"
    assert meta.source == "IBGE"
    assert meta.source_url == "https://sidra.ibge.gov.br/tabela/1737"
    assert meta.version == "2026.09"
    assert meta.updated_at == "2026-10-09"
    assert meta.cobertura.inicio == Competencia(1979, 12)
    assert meta.cobertura.fim == Competencia(2026, 9)
    assert meta.total_records == 562
    assert meta.cobertura.total == 562
    assert "SIDRA tabela 1737" in meta.note


def test_fatores_conhecidos(ipca: Ipca) -> None:
    assert ipca.valor("1979-12") == D("0.0000000076183")
    assert ipca.valor("2025-02") == D("7205.03")
    assert ipca.valor("2025-03") == D("7245.38")
    assert ipca.valor("2025-04") == D("7276.54")
    assert ipca.valor("2026-09") == D("7695.82")
    assert ipca.valor(Competencia(2026, 9)) == D("7695.82")


def test_razao_de_fevereiro_para_marco_e_a_do_ipca(ipca: Ipca) -> None:
    """IPCA-IBGE de mar/2025 = 0,56% — bem abaixo do 1,23% da Tabela Prática."""
    razao = ipca.valor("2025-03") / ipca.valor("2025-02")
    assert razao.quantize(D("0.000001")) == D("1.005600")


def test_ipca_ibge_nao_e_a_tabela_pratica(ipca: Ipca) -> None:
    tjsp = obter(TjspKey)
    razao_ipca = ipca.valor("2025-03") / ipca.valor("2025-02")
    razao_tjsp = tjsp.valor("2025-03") / tjsp.valor("2025-02")
    assert razao_ipca.quantize(D("0.000001")) == D("1.005600")
    assert razao_tjsp.quantize(D("0.000001")) == D("1.012300")
    assert razao_ipca != razao_tjsp


def test_tabela_pratica_continua_intacta() -> None:
    tjsp = obter(TjspKey)
    assert tjsp.metadata.source == "AASP"
    assert tjsp.metadata.version == "2026.09"
    assert tjsp.metadata.cobertura.inicio == Competencia(1992, 1)
    assert tjsp.metadata.cobertura.fim == Competencia(2026, 9)
    assert tjsp.valor("2026-09") == D("8.566509")
    assert tjsp.valor("1995-01") == D("1.133251")


def test_cobertura_insuficiente_produz_erro_explicito(ipca: Ipca) -> None:
    with pytest.raises(CoverageError) as antes:
        ipca.valor(Competencia(1979, 11))
    assert "11/1979" in str(antes.value)
    with pytest.raises(CoverageError) as depois:
        ipca.valor(Competencia(2026, 10))
    assert "10/2026" in str(depois.value)
    assert "12/1979" in str(depois.value)
    assert "09/2026" in str(depois.value)


def test_registry(ipca: Ipca) -> None:
    assert KEY in chaves()
    assert "tjsp_tabela_pratica" in chaves()
    assert obter(KEY).metadata.source == "IBGE"
    with pytest.raises(IndexerError):
        obter("nao_existe")
    with pytest.raises(IndexerError):
        Ipca.carregar(DADOS / "ipca_inexistente.json")


def test_proveniencia_gravada() -> None:
    crua = json.loads((DADOS / "ibge_sidra_raw.json").read_text(encoding="utf-8"))
    assert crua["source"] == "IBGE"
    assert crua["tabela"] == "1737"
    assert crua["variavel"] == "2266"
    assert "servicodados.ibge.gov.br" in crua["sourceUrl"]
    assert len(crua["registros"]) == 562

    publicado = json.loads((DADOS / "ipca.json").read_text(encoding="utf-8"))
    assert publicado["metadata"]["source"] == "IBGE"
    assert publicado["metadata"]["version"] == "2026.09"
    assert publicado["metadata"]["totalRecords"] == 562
    assert len(publicado["factors"]) == 562
    assert len(crua["registros"]) == len(publicado["factors"])
    # o número-índice publicado é o mesmo que veio do SIDRA
    ultimo = publicado["factors"][-1]
    chave = f"{ultimo['year']:04d}{ultimo['month']:02d}"
    assert Decimal(crua["registros"][chave]) == Decimal(str(ultimo["factor"]))


def test_serie_com_lacuna_e_rejeitada(tmp_path: Path) -> None:
    dados = {
        "metadata": {"source": "IBGE", "sourceUrl": "u", "version": "1", "updatedAt": "2026-01-01"},
        "factors": [
            {"year": 2025, "month": 1, "factor": 1},
            {"year": 2025, "month": 3, "factor": 1.1},
        ],
    }
    caminho = tmp_path / "ipca.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(SeriesIntegrityError):
        Ipca.carregar(caminho)
