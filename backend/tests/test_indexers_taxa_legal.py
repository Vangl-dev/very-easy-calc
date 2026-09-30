from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.indexers import CoverageError
from app.indexers.taxa_legal import ARQUIVO_PADRAO, KEY, TaxaLegal
from app.indexers.base import carregar_json


@pytest.fixture(scope="module")
def taxa() -> TaxaLegal:
    return TaxaLegal.carregar()


def test_metadata_oficial(taxa: TaxaLegal) -> None:
    meta = taxa.metadata
    assert meta.key == KEY
    assert meta.name == "Taxa Legal (BCB SGS 29543)"
    assert meta.kind == "juros"
    assert meta.source == "Banco Central do Brasil"
    assert meta.version == "2026.09"
    assert meta.cobertura.inicio == Competencia(2024, 8)
    assert meta.cobertura.fim == Competencia(2026, 9)
    assert meta.total_records == 26
    assert "sgs.29543" in meta.source_url


def test_taxas_conhecidas(taxa: TaxaLegal) -> None:
    assert taxa.taxa("2024-08") == Decimal("0.00605306")
    assert taxa.taxa("2026-09") == Decimal("0.01499119")
    assert taxa.taxa(Competencia(2025, 3)) == Decimal("0")


def test_cobertura_explicita(taxa: TaxaLegal) -> None:
    with pytest.raises(CoverageError) as antes:
        taxa.taxa(Competencia(2024, 7))
    assert "07/2024" in str(antes.value)
    with pytest.raises(CoverageError) as depois:
        taxa.taxa(Competencia(2026, 10))
    assert "10/2026" in str(depois.value)
    assert "09/2026" in str(depois.value)


def test_proveniencia_contra_resposta_bruta_do_bcb() -> None:
    with (ARQUIVO_PADRAO.parent / "taxa_legal_bcb_raw.json").open(encoding="utf-8") as handle:
        bruto = json.load(handle)
    fatores = carregar_json(ARQUIVO_PADRAO)["factors"]
    assert len(bruto) == len(fatores) == 26
    for registro, fator in zip(bruto, fatores, strict=True):
        dia, mes, ano = registro["data"].split("/")
        assert (fator["year"], fator["month"]) == (int(ano), int(mes))
        assert Decimal(str(fator["sourceValue"])) / Decimal(100) == Decimal(str(fator["factor"]))
        assert fator["sourceDate"] == registro["data"]
        assert Decimal(registro["valor"]) / Decimal(100) == Decimal(str(fator["factor"]))
