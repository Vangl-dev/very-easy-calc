from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.core.competencia import Competencia
from app.core.config import DATA_DIR
from app.indexers.base import (
    KIND_JUROS,
    IndexerError,
    MonthlyIndexer,
    carregar_json,
    metadados_de_arquivo,
    registrar,
    serie_de_fatores,
)

KEY = "taxa_legal"
NOME = "Taxa Legal (BCB SGS 29543)"
ARQUIVO_PADRAO = DATA_DIR / "taxa_legal.json"


class TaxaLegal(MonthlyIndexer):
    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "TaxaLegal":
        path = Path(caminho) if caminho else ARQUIVO_PADRAO
        if not path.exists():
            raise IndexerError(f"base da Taxa Legal não encontrada: {path}")
        dados = carregar_json(path)
        metadata = metadados_de_arquivo(dados, KEY, NOME, KIND_JUROS)
        serie = serie_de_fatores(dados["factors"])
        instancia = cls(metadata=metadata, series=serie)
        instancia._arquivo_dados = path
        return instancia

    def unidade(self) -> str:
        return "taxa mensal"

    def taxa(self, competencia: Competencia) -> Decimal:
        return self.valor(competencia)


def _fabrica() -> TaxaLegal:
    return TaxaLegal.carregar()


registrar(KEY, _fabrica)
