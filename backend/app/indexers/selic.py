from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.core.competencia import Competencia
from app.core.config import DATA_DIR
from app.core.money import to_decimal
from app.indexers.base import (
    KIND_CORRECAO,
    CoverageError,
    IndexerError,
    MonthlyIndexer,
    carregar_json,
    metadados_de_arquivo,
    registrar,
    serie_de_fatores,
)

KEY = "selic"
NOME = "SELIC (BCB)"
ARQUIVO_PADRAO = DATA_DIR / "selic.json"


class Selic(MonthlyIndexer):
    """SELIC acumulada por competência — critério próprio, distinto da Taxa Legal."""

    _mensal: dict[Competencia, Decimal] = {}

    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "Selic":
        path = Path(caminho) if caminho else ARQUIVO_PADRAO
        if not path.exists():
            raise IndexerError(f"base da SELIC não encontrada: {path}")
        dados = carregar_json(path)
        metadata = metadados_de_arquivo(dados, KEY, NOME, KIND_CORRECAO)
        serie = serie_de_fatores(dados["factors"])
        instancia = cls(metadata=metadata, series=serie)
        instancia._arquivo_dados = path
        instancia._mensal = {
            Competencia(int(f["year"]), int(f["month"])): to_decimal(f["mensal"]) - 1
            for f in dados["factors"]
            if f.get("mensal") is not None
        }
        return instancia

    def unidade(self) -> str:
        return "fator acumulado"

    def taxa(self, competencia: object) -> Decimal:
        """Taxa SELIC da competência (fração mensal), ex.: 0,00867512."""
        comp = Competencia.parse(competencia)
        taxa = self._mensal.get(comp)
        if taxa is None:
            anterior = (
                Competencia(comp.year - 1, 12)
                if comp.month == 1
                else Competencia(comp.year, comp.month - 1)
            )
            taxa = self.valor(comp) / self.valor(anterior) - 1
        return taxa


def _fabrica() -> Selic:
    return Selic.carregar()


registrar(KEY, _fabrica)
