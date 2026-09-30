from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import round_brl, to_decimal
from app.indexers import IndexerError, obter
from app.indexers.base import KIND_CORRECAO
from app.indexers.tjsp import KEY as TjspKey


@dataclass(frozen=True)
class ConfigCorrecao:
    aplicar: bool = True
    indexador: str = TjspKey
    termo_inicial: Competencia | None = None
    termo_final: Competencia | None = None


@dataclass(frozen=True)
class ResultadoCorrecao:
    aplicado: bool
    principal: Decimal
    valor_corrigido: Decimal
    correcao: Decimal
    motivo: str
    indexador: str | None = None
    indexador_versao: str | None = None
    indexador_fonte: str | None = None
    termo_inicial: Competencia | None = None
    termo_final: Competencia | None = None
    fator_inicial: Decimal | None = None
    fator_final: Decimal | None = None
    razao: Decimal | None = None

    @property
    def fator_exibicao(self) -> Decimal | None:
        if self.razao is None:
            return None
        return self.razao.quantize(Decimal("0.000001"))


NAO_APLICAR = "Correção monetária não aplicada (parâmetro explícito do usuário)."
SEM_PERIODO = "Correção monetária não aplicada (termo inicial ou final não informado)."


def calcular_correcao(
    principal: object,
    config: ConfigCorrecao,
    *,
    vencimento: object | None = None,
    data_base: object | None = None,
) -> ResultadoCorrecao:
    base = round_brl(to_decimal(principal))
    if base < 0:
        raise ValueError("principal negativo não é suportado na correção monetária")

    if not config.aplicar:
        return ResultadoCorrecao(
            aplicado=False,
            principal=base,
            valor_corrigido=base,
            correcao=Decimal("0.00"),
            motivo=NAO_APLICAR,
        )

    termo_inicial = config.termo_inicial
    if termo_inicial is None and vencimento is not None:
        termo_inicial = Competencia.parse(vencimento)
    termo_final = config.termo_final
    if termo_final is None and data_base is not None:
        termo_final = Competencia.parse(data_base)

    if termo_inicial is None or termo_final is None:
        return ResultadoCorrecao(
            aplicado=False,
            principal=base,
            valor_corrigido=base,
            correcao=Decimal("0.00"),
            motivo=SEM_PERIODO,
        )

    inicio = Competencia.parse(termo_inicial)
    fim = Competencia.parse(termo_final)
    if fim < inicio:
        raise ValueError(
            f"termo final ({fim.label}) anterior ao termo inicial ({inicio.label})"
        )

    indexador = obter(config.indexador)
    if indexador.metadata.kind != KIND_CORRECAO:
        raise IndexerError(
            f"o indexador '{config.indexador}' ({indexador.metadata.kind}) não é de correção monetária"
        )
    fator_inicial = indexador.valor(inicio)
    fator_final = indexador.valor(fim)
    razao = fator_final / fator_inicial
    corrigido = round_brl(base * razao)

    return ResultadoCorrecao(
        aplicado=True,
        principal=base,
        valor_corrigido=corrigido,
        correcao=corrigido - base,
        motivo="Correção monetária aplicada.",
        indexador=indexador.metadata.key,
        indexador_versao=indexador.metadata.version,
        indexador_fonte=indexador.metadata.source,
        termo_inicial=inicio,
        termo_final=fim,
        fator_inicial=fator_inicial,
        fator_final=fator_final,
        razao=razao,
    )
