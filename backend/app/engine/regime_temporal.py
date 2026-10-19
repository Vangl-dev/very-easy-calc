from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from app.core.competencia import Competencia
from app.engine.correcao import ConfigCorrecao, SegmentoCorrecao
from app.engine.juros import (
    MODALIDADE_REGIMES,
    TIPO_SELIC_MENOS_IPCA,
    TIPO_SEM_JUROS,
    ConfigJuros,
    RegraJuros,
)
from app.indexers.ipca import KEY as IpcaKey
from app.indexers.selic import KEY as SelicKey

REGIME_SELIC_INICIO = date(2024, 8, 28)

CRITERIO_SOMENTE_CORRECAO = "somente_correcao"
CRITERIO_SOMENTE_JUROS = "somente_juros"
CRITERIO_CORRECAO_E_JUROS = "correcao_e_juros"

ROTULO_SOMENTE_JUROS = "SELIC menos correção monetária"
ROTULO_SELIC_INTEGRAL = "SELIC integral"

MOTIVO_SOMENTE_JUROS = (
    "Regime pós-28/08/2024: apenas juros no período — "
    "SELIC menos a correção monetária, com piso mensal zero."
)
MOTIVO_CORRECAO_ANTES = (
    "Regime pós-28/08/2024: correção antes dos juros — correção monetária "
    "(IPCA — IBGE) no trecho inicial e SELIC integral a partir dos juros."
)
MOTIVO_JUROS_ANTES = (
    "Regime pós-28/08/2024: juros antes da correção — SELIC menos correção "
    "no trecho inicial e SELIC integral a partir da correção."
)


@dataclass(frozen=True)
class TrechoRegime:
    """Trecho da verba e o critério que o motor aplica nele."""

    criterio: str
    inicio: date
    fim: date
    aplicacao: str


@dataclass(frozen=True)
class ResolucaoRegime:
    """Configurações finais da verba após a resolução temporal automática."""

    aplicada: bool
    correcao: ConfigCorrecao
    juros: ConfigJuros
    trechos: tuple[TrechoRegime, ...] = ()
    motivo: str = ""


def _sem_resolucao(correcao: ConfigCorrecao, juros: ConfigJuros) -> ResolucaoRegime:
    return ResolucaoRegime(aplicada=False, correcao=correcao, juros=juros)


def _competencia_de_troca(data: date) -> Competencia:
    """Competência em que o critério novo passa a valer.

    A competência da troca pertence ao regime seguinte quando a mudança
    acontece no meio do mês.
    """
    proximo = data + timedelta(days=1)
    return Competencia(proximo.year, proximo.month)


def _segmentos_do_regime(
    comp_inicio: Competencia,
    troca: Competencia,
    comp_final: Competencia,
    indexador: str,
) -> tuple[SegmentoCorrecao, ...]:
    """Correção antes da troca com o indexador próprio; depois, a SELIC.

    Os dois segmentos compartilham o ponto de referência em que a troca
    acontece: o fator de cada trecho é uma razão entre índices do próprio mês,
    então encadear ``fim`` de um com ``início`` seguinte distinto lançaria fora
    a transição entre as duas referências (lacuna de uma competência).
    """
    segmentos: list[SegmentoCorrecao] = []
    referencia = troca
    if comp_inicio < troca:
        termo_final = min(troca.anterior, comp_final)
        segmentos.append(
            SegmentoCorrecao(
                termo_inicial=comp_inicio,
                termo_final=termo_final,
                indexador=indexador,
            )
        )
        referencia = termo_final
    if troca <= comp_final:
        segmentos.append(
            SegmentoCorrecao(
                termo_inicial=referencia,
                termo_final=comp_final,
                indexador=SelicKey,
            )
        )
    return tuple(segmentos)


def _regra_somente_juros(inicio: date, fim: date) -> RegraJuros:
    """Critério exclusivo de juros: SELIC menos o IPCA do mês.

    A regra é do regime automático, então o componente de correção é sempre a
    série oficial do IBGE — nunca a Tabela Prática (IPCA-E) que a verba use
    para a sua própria correção monetária.
    """
    return RegraJuros(
        rotulo=ROTULO_SOMENTE_JUROS,
        inicio=inicio,
        fim=fim,
        tipo=TIPO_SELIC_MENOS_IPCA,
        indexador=IpcaKey,
    )


def _regra_selic_integral(inicio: date, fim: date) -> RegraJuros:
    """Trecho em que correção e juros incidem juntos: a SELIC já é integral.

    O critério entra na correção monetária (segmento SELIC); os juros do
    trecho são nulos para não contar duas vezes a mesma SELIC.
    """
    return RegraJuros(
        rotulo=ROTULO_SELIC_INTEGRAL,
        inicio=inicio,
        fim=fim,
        tipo=TIPO_SEM_JUROS,
    )


def resolver_regime_temporal(
    correcao: ConfigCorrecao,
    juros: ConfigJuros,
    *,
    data_final: date,
    inicio_correcao: date | None = None,
) -> ResolucaoRegime:
    """Resolve a verba em trechos segundo o regime pós-28/08/2024.

    Critérios automáticos, conforme as datas de início da correção e dos juros:

    - só correção → correção monetária (IPCA — IBGE);
    - só juros → SELIC menos a correção monetária, com piso mensal zero;
    - correção + juros → SELIC integral (o trecho passa a ser corrigido pela
      SELIC, que já embute correção e juros).

    Não altera verbas fora do regime, sem juros, com correção e juros na
    mesma competência ou com regimes explícitos informados pelo usuário.
    Quando a correção começa antes do regime, o título mantém o critério
    histórico (correção + Taxa Legal) — o usuário pode segmentar com regimes.
    """
    if not juros.aplicar or juros.inicio is None:
        return _sem_resolucao(correcao, juros)

    inicio_juros = juros.inicio
    fim_juros = juros.fim or data_final
    if inicio_juros < REGIME_SELIC_INICIO or data_final < REGIME_SELIC_INICIO:
        return _sem_resolucao(correcao, juros)

    if not correcao.aplicar or correcao.termo_inicial is None:
        regra = _regra_somente_juros(inicio_juros, fim_juros)
        trecho = TrechoRegime(
            criterio=CRITERIO_SOMENTE_JUROS,
            inicio=inicio_juros,
            fim=fim_juros,
            aplicacao="SELIC menos a correção monetária do mês (piso mensal zero).",
        )
        return ResolucaoRegime(
            aplicada=True,
            correcao=correcao,
            juros=replace(juros, modalidade=MODALIDADE_REGIMES, regras=(regra,)),
            trechos=(trecho,),
            motivo=MOTIVO_SOMENTE_JUROS,
        )

    comp_correcao = Competencia.parse(correcao.termo_inicial)
    if comp_correcao < Competencia(REGIME_SELIC_INICIO.year, REGIME_SELIC_INICIO.month):
        return _sem_resolucao(correcao, juros)

    comp_juros = Competencia(inicio_juros.year, inicio_juros.month)
    if comp_correcao == comp_juros:
        return _sem_resolucao(correcao, juros)

    comp_final = Competencia.parse(correcao.termo_final or data_final)
    inicio_correcao_data = inicio_correcao or comp_correcao.inicio

    if comp_correcao < comp_juros:
        troca = _competencia_de_troca(inicio_juros)
        segmentos = _segmentos_do_regime(comp_correcao, troca, comp_final, IpcaKey)
        trechos = (
            TrechoRegime(
                criterio=CRITERIO_SOMENTE_CORRECAO,
                inicio=inicio_correcao_data,
                fim=inicio_juros,
                aplicacao="Correção monetária (IPCA — IBGE), sem juros.",
            ),
            TrechoRegime(
                criterio=CRITERIO_CORRECAO_E_JUROS,
                inicio=inicio_juros,
                fim=fim_juros,
                aplicacao=(
                    "SELIC integral: correção e juros no mesmo trecho, "
                    "com os juros embutidos na correção monetária."
                ),
            ),
        )
        regras = (_regra_selic_integral(inicio_juros, fim_juros),)
        motivo = MOTIVO_CORRECAO_ANTES
    else:
        troca = _competencia_de_troca(inicio_correcao_data)
        segmentos = _segmentos_do_regime(
            comp_correcao, troca, comp_final, correcao.indexador
        )
        limite = inicio_correcao_data
        trechos_list: list[TrechoRegime] = []
        regras_list: list[RegraJuros] = []
        if limite > inicio_juros:
            # juros-only termina na véspera do início da correção: o trecho
            # seguinte começa em `limite`, sem sobreposição nem lacuna de dias.
            fim_somente_juros = limite - timedelta(days=1)
            regras_list.append(_regra_somente_juros(inicio_juros, fim_somente_juros))
            trechos_list.append(
                TrechoRegime(
                    criterio=CRITERIO_SOMENTE_JUROS,
                    inicio=inicio_juros,
                    fim=fim_somente_juros,
                    aplicacao=(
                        "SELIC menos a correção monetária do mês (piso mensal zero)."
                    ),
                )
            )
        if limite <= fim_juros:
            regras_list.append(_regra_selic_integral(limite, fim_juros))
            trechos_list.append(
                TrechoRegime(
                    criterio=CRITERIO_CORRECAO_E_JUROS,
                    inicio=limite,
                    fim=fim_juros,
                    aplicacao=(
                        "SELIC integral: correção e juros no mesmo trecho, "
                        "com os juros embutidos na correção monetária."
                    ),
                )
            )
        if not regras_list:
            return _sem_resolucao(correcao, juros)
        trechos = tuple(trechos_list)
        regras = tuple(regras_list)
        motivo = MOTIVO_JUROS_ANTES

    nova_correcao = (
        replace(correcao, segmentos=segmentos) if segmentos else correcao
    )
    return ResolucaoRegime(
        aplicada=True,
        correcao=nova_correcao,
        juros=replace(juros, modalidade=MODALIDADE_REGIMES, regras=regras),
        trechos=trechos,
        motivo=motivo,
    )
