from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import round_brl, to_decimal
from app.indexers import IndexerError, obter
from app.indexers.base import KIND_CORRECAO
from app.indexers.tjsp import KEY as TjspKey


@dataclass(frozen=True)
class SegmentoCorrecao:
    """Trecho do período com um indexador próprio (regime de atualização)."""

    termo_inicial: Competencia
    termo_final: Competencia
    indexador: str


@dataclass(frozen=True)
class SegmentoCorrecaoResultado:
    termo_inicial: Competencia
    termo_final: Competencia
    indexador: str
    indexador_versao: str | None
    indexador_fonte: str | None
    fator_inicial: Decimal
    fator_final: Decimal
    razao: Decimal


@dataclass(frozen=True)
class ConfigCorrecao:
    aplicar: bool = True
    indexador: str = TjspKey
    termo_inicial: Competencia | None = None
    termo_final: Competencia | None = None
    segmentos: tuple[SegmentoCorrecao, ...] = ()


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
    segmentos: tuple[SegmentoCorrecaoResultado, ...] = ()

    @property
    def fator_exibicao(self) -> Decimal | None:
        if self.razao is None:
            return None
        return self.razao.quantize(Decimal("0.000001"))


NAO_APLICAR = "Correção monetária não aplicada (parâmetro explícito do usuário)."
SEM_PERIODO = "Correção monetária não aplicada (termo inicial ou final não informado)."


def _correcao_segmentada(base: Decimal, config: ConfigCorrecao) -> ResultadoCorrecao:
    """Aplica cada trecho com o próprio indexador e encadeia as razões."""
    razao_total = Decimal(1)
    detalhes: list[SegmentoCorrecaoResultado] = []
    anterior_fim: Competencia | None = None
    ultimo_indexador: str | None = None
    ultimo_meta = None

    for segmento in config.segmentos:
        if segmento.termo_final < segmento.termo_inicial:
            raise ValueError(
                f"segmento de correção com termo final "
                f"({segmento.termo_final.label}) anterior ao termo inicial "
                f"({segmento.termo_inicial.label})"
            )
        # fronteira compartilhada não é sobreposição: a razão do segundo trecho
        # parte do mesmo índice em que o primeiro termina, então os fatores se
        # cancelam na junção em vez de serem aplicados duas vezes.
        if anterior_fim is not None and segmento.termo_inicial < anterior_fim:
            raise ValueError(
                f"segmentos de correção se sobrepõem em {segmento.termo_inicial.label}"
            )
        indexador = obter(segmento.indexador)
        if indexador.metadata.kind != KIND_CORRECAO:
            raise IndexerError(
                f"o indexador '{segmento.indexador}' ({indexador.metadata.kind}) "
                "não é de correção monetária"
            )
        fator_inicial = indexador.valor(segmento.termo_inicial)
        fator_final = indexador.valor(segmento.termo_final)
        razao = fator_final / fator_inicial
        razao_total *= razao
        detalhes.append(
            SegmentoCorrecaoResultado(
                termo_inicial=segmento.termo_inicial,
                termo_final=segmento.termo_final,
                indexador=indexador.metadata.key,
                indexador_versao=indexador.metadata.version,
                indexador_fonte=indexador.metadata.source,
                fator_inicial=fator_inicial,
                fator_final=fator_final,
                razao=razao,
            )
        )
        ultimo_indexador = indexador.metadata.key
        ultimo_meta = indexador.metadata
        anterior_fim = segmento.termo_final

    corrigido = round_brl(base * razao_total)
    ultimo = detalhes[-1]
    return ResultadoCorrecao(
        aplicado=True,
        principal=base,
        valor_corrigido=corrigido,
        correcao=corrigido - base,
        motivo="Correção monetária aplicada.",
        indexador=ultimo_indexador,
        indexador_versao=ultimo_meta.version if ultimo_meta else None,
        indexador_fonte=ultimo_meta.source if ultimo_meta else None,
        termo_inicial=detalhes[0].termo_inicial,
        termo_final=ultimo.termo_final,
        fator_inicial=detalhes[0].fator_inicial,
        fator_final=ultimo.fator_final,
        razao=razao_total,
        segmentos=tuple(detalhes),
    )


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

    if config.segmentos:
        return _correcao_segmentada(base, config)

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
