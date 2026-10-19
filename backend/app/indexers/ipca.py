from __future__ import annotations

from pathlib import Path

from app.core.config import DATA_DIR
from app.indexers.base import (
    KIND_CORRECAO,
    IndexerError,
    MonthlyIndexer,
    carregar_json,
    metadados_de_arquivo,
    registrar,
    serie_de_fatores,
)

KEY = "ipca"
NOME = "IPCA (IBGE)"
ARQUIVO_PADRAO = DATA_DIR / "ipca.json"


class Ipca(MonthlyIndexer):
    """Número-índice do IPCA (IBGE) — série própria, distinta da Tabela Prática."""

    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "Ipca":
        path = Path(caminho) if caminho else ARQUIVO_PADRAO
        if not path.exists():
            raise IndexerError(f"base do IPCA não encontrada: {path}")
        dados = carregar_json(path)
        metadata = metadados_de_arquivo(dados, KEY, NOME, KIND_CORRECAO)
        serie = serie_de_fatores(dados["factors"])
        instancia = cls(metadata=metadata, series=serie)
        instancia._arquivo_dados = path
        return instancia

    def unidade(self) -> str:
        return "número-índice"


def _fabrica() -> Ipca:
    return Ipca.carregar()


registrar(KEY, _fabrica)
