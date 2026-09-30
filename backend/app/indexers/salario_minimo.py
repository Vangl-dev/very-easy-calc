from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.core.competencia import Competencia
from app.core.config import DATA_DIR
from app.indexers.base import (
    KIND_SALARIO,
    IndexerError,
    MonthlyIndexer,
    carregar_json,
    metadados_de_arquivo,
    registrar,
    serie_de_fatores,
)

KEY = "salario_minimo"
NOME = "Salário mínimo"
ARQUIVO_PADRAO = DATA_DIR / "salario_minimo.json"


class SalarioMinimo(MonthlyIndexer):
    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "SalarioMinimo":
        path = Path(caminho) if caminho else ARQUIVO_PADRAO
        if not path.exists():
            raise IndexerError(f"base do salário mínimo não encontrada: {path}")
        dados = carregar_json(path)
        metadata = metadados_de_arquivo(dados, KEY, NOME, KIND_SALARIO)
        serie = serie_de_fatores(dados["factors"])
        instancia = cls(metadata=metadata, series=serie)
        instancia._arquivo_dados = path
        return instancia

    def unidade(self) -> str:
        return "R$ (nominal por competência)"

    def salario(self, competencia: Competencia) -> Decimal:
        return self.valor(competencia)


def _fabrica() -> SalarioMinimo:
    return SalarioMinimo.carregar()


registrar(KEY, _fabrica)
