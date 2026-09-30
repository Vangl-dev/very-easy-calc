from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.core.competencia import Competencia
from app.core.config import DATA_DIR
from app.core.money import to_decimal
from app.indexers.base import (
    KIND_CORRECAO,
    IndexerError,
    MonthlyIndexer,
    carregar_json,
    metadados_de_arquivo,
    registrar,
    serie_de_fatores,
)

KEY = "tjsp_tabela_pratica"
NOME = "Tabela Prática TJSP"
ARQUIVO_PADRAO = DATA_DIR / "tjsp_tabela_pratica.json"


class TabelaPraticaTJSP(MonthlyIndexer):
    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "TabelaPraticaTJSP":
        path = Path(caminho) if caminho else ARQUIVO_PADRAO
        if not path.exists():
            raise IndexerError(f"base da Tabela Prática não encontrada: {path}")
        dados = carregar_json(path)
        metadata = metadados_de_arquivo(dados, KEY, NOME, KIND_CORRECAO)
        serie = serie_de_fatores(dados["factors"])
        instancia = cls(metadata=metadata, series=serie)
        instancia._arquivo_dados = path
        return instancia

    def unidade(self) -> str:
        return "fator acumulado"

    def razao(self, termo_inicial: Competencia, termo_final: Competencia) -> Decimal:
        inicial = self.valor(termo_inicial)
        final = self.valor(termo_final)
        return final / inicial

    def atualizar(
        self,
        valor: object,
        termo_inicial: Competencia,
        termo_final: Competencia,
    ) -> Decimal:
        base = to_decimal(valor)
        return base * self.razao(Competencia.parse(termo_inicial), Competencia.parse(termo_final))


def _fabrica() -> TabelaPraticaTJSP:
    return TabelaPraticaTJSP.carregar()


registrar(KEY, _fabrica)
