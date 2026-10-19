from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    CalculoRequest,
    ConfigCorrecaoSchema,
    ConfigEncargoSchema,
    EncargoConsolidadoSchema,
    ConfigJurosSchema,
    PagamentoSchema,
    RegimeAtualizacaoSchema,
    RegraAlimentoSchema,
    VerbaSchema,
)
from app.api.serializacao import RastroParcela, serializar_calculo
from app.core.competencia import Competencia
from app.core.config import get_settings
from app.core.money import percentual_txt, round_brl, to_decimal
from app.engine.alimentos import (
    TIPO_FIXO,
    TIPO_SALARIO_MINIMO,
    RegraAlimento,
    entradas_de_alimentos,
    gerar_parcelas,
)
from app.engine.calculo import calcular
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.correcao import ConfigCorrecao, SegmentoCorrecao
from app.engine.encargos import ConfigEncargo, Pagamento
from app.engine.encargos_consolidados import EncargoConsolidado, calcular_encargos_consolidados
from app.engine.juros import (
    MODALIDADE_FIXA,
    MODALIDADE_REGIMES,
    MODALIDADE_TAXA_LEGAL,
    TIPO_ANUAL,
    TIPO_MENSAL,
    TIPO_SELIC,
    TIPO_TAXA_LEGAL,
    UNIDADE_ANUAL,
    ConfigJuros,
    RegraJuros,
)
from app.engine.memoria import montar_memoria
from app.engine.parcela import ParcelaInput
from app.engine.regime_temporal import ResolucaoRegime, resolver_regime_temporal
from app.engine.verbas import resolver_verbas
from app.indexers import obter
from app.indexers.overrides import (
    carregar_overrides_da_sessao,
    definir_overrides_ativos,
    limpar_overrides_ativos,
    overrides_utilizados,
)
from app.indexers.salario_minimo import KEY as SalarioKey
from app.indexers.selic import KEY as SelicKey
from app.models.entities import Calculo

__all__ = ["gerar_codigo_calculo", "serializar_para_persistencia", "executar_calculo"]


def gerar_codigo_calculo(session: Session) -> str:
    max_id = session.scalar(select(func.coalesce(func.max(Calculo.id), 0))) or 0
    ano = date.today().year
    return f"VEC-{ano:04d}-{max_id + 1:06d}"


def _montar_pagamentos(schema: PagamentoSchema | list[PagamentoSchema]) -> tuple[Pagamento, ...]:
    itens = schema if isinstance(schema, list) else [schema]
    return tuple(
        Pagamento(
            data=date.fromisoformat(p.data),
            valor=to_decimal(p.valor),
            descricao=p.descricao,
        )
        for p in itens
    )


def _montar_config_correcao(schema: ConfigCorrecaoSchema | None) -> ConfigCorrecao:
    if schema is None:
        return ConfigCorrecao()
    return ConfigCorrecao(
        aplicar=schema.aplicar,
        indexador=schema.indexador,
        termo_inicial=Competencia.parse(schema.termo_inicial) if schema.termo_inicial else None,
        termo_final=Competencia.parse(schema.termo_final) if schema.termo_final else None,
    )


def _montar_config_juros(schema: ConfigJurosSchema | None) -> ConfigJuros:
    if schema is None:
        return ConfigJuros()
    kwargs: dict = {
        "aplicar": schema.aplicar,
        "modalidade": schema.modalidade,
        "unidade": schema.unidade,
        "base": schema.base,
    }
    if schema.taxa is not None:
        kwargs["taxa"] = to_decimal(schema.taxa)
    if schema.inicio:
        kwargs["inicio"] = date.fromisoformat(schema.inicio)
    if schema.fim:
        kwargs["fim"] = date.fromisoformat(schema.fim)
    return ConfigJuros(**kwargs)


def _montar_config_correcao_de_verba(
    schema: ConfigCorrecaoSchema | None,
    *,
    data_base_verba: str,
) -> ConfigCorrecao:
    if schema is None:
        return ConfigCorrecao(aplicar=False)
    inicio = schema.termo_inicial or data_base_verba
    return ConfigCorrecao(
        aplicar=schema.aplicar,
        indexador=schema.indexador,
        termo_inicial=Competencia.parse(inicio) if schema.aplicar else None,
        termo_final=(
            Competencia.parse(schema.termo_final)
            if schema.termo_final and schema.aplicar
            else None
        ),
    )


def _montar_config_juros_de_verba(
    schema: ConfigJurosSchema | None,
    *,
    data_base_verba: str,
) -> ConfigJuros:
    if schema is None:
        return ConfigJuros(aplicar=False)
    kwargs: dict = {
        "aplicar": schema.aplicar,
        "modalidade": schema.modalidade,
        "unidade": schema.unidade,
        "base": schema.base,
    }
    if schema.taxa is not None:
        kwargs["taxa"] = to_decimal(schema.taxa)
    if schema.aplicar:
        kwargs["inicio"] = (
            date.fromisoformat(schema.inicio)
            if schema.inicio
            else date.fromisoformat(data_base_verba)
        )
        if schema.fim:
            kwargs["fim"] = date.fromisoformat(schema.fim)
    return ConfigJuros(**kwargs)


def _correcao_do_regime(regime: RegimeAtualizacaoSchema) -> str | None:
    """Critério combinado tem prioridade sobre o campo isolado."""
    return regime.criterio or regime.correcao


def _juros_do_regime(regime: RegimeAtualizacaoSchema) -> ConfigJurosSchema | None:
    if regime.criterio:
        return ConfigJurosSchema(aplicar=True, modalidade=regime.criterio, base="corrigido")
    if regime.juros is not None and regime.juros.aplicar:
        return regime.juros
    return None


def _segmentos_de_regimes(
    regimes: list[RegimeAtualizacaoSchema],
    *,
    termo_inicial_padrao: Competencia | None,
    data_final: str,
) -> list[SegmentoCorrecao]:
    """Converte os períodos dos regimes em segmentos de correção.

    A correção é mensal e cada segmento é uma razão entre índices do próprio
    mês: o regime encerra exatamente no ponto de referência em que o próximo
    começa, para que a transição entre as duas séries não se perda no produto.
    """
    fim_total = Competencia.parse(data_final)
    brutos: list[list] = []
    for indice, regime in enumerate(regimes):
        chave = _correcao_do_regime(regime)
        if not chave:
            continue
        fim = Competencia.parse(regime.data_fim) if regime.data_fim else fim_total
        if regime.data_inicio:
            inicio = Competencia.parse(regime.data_inicio)
        elif indice == 0:
            inicio = termo_inicial_padrao
        else:
            raise ValueError(
                "regime de atualização a partir do segundo deve informar data_inicio"
            )
        if inicio is None:
            raise ValueError(
                "regime de atualização sem data inicial e a verba não tem data de correção"
            )
        if fim < inicio:
            raise ValueError(
                f"regime de atualização de {chave} termina ({fim.label}) antes de "
                f"começar ({inicio.label})"
            )
        brutos.append([inicio, fim, chave])

    for indice in range(len(brutos) - 1):
        proximo = brutos[indice + 1][0]
        if proximo <= brutos[indice][0]:
            raise ValueError(
                f"regimes de atualização se sobrepõem em {proximo.label}"
            )
        brutos[indice][1] = proximo

    return [
        SegmentoCorrecao(
            termo_inicial=inicio, termo_final=fim, indexador=chave
        )
        for inicio, fim, chave in brutos
    ]


def _regras_de_regimes(
    regimes: list[RegimeAtualizacaoSchema],
    *,
    data_final: str,
) -> list[RegraJuros]:
    fim_total = date.fromisoformat(data_final)
    regras: list[RegraJuros] = []
    for indice, regime in enumerate(regimes):
        if regime.data_inicio:
            inicio = date.fromisoformat(regime.data_inicio)
        elif indice == 0:
            inicio = date(1900, 1, 1)
        else:
            raise ValueError(
                "regime de atualização a partir do segundo deve informar data_inicio"
            )
        fim = date.fromisoformat(regime.data_fim) if regime.data_fim else fim_total
        if fim < inicio:
            raise ValueError(
                f"regime de atualização termina ({fim.isoformat()}) antes de começar "
                f"({inicio.isoformat()})"
            )

        juros = _juros_do_regime(regime)
        if juros is None:
            regras.append(
                RegraJuros(
                    rotulo="Sem juros neste período",
                    inicio=inicio,
                    fim=fim,
                    tipo=TIPO_MENSAL,
                    taxa=Decimal(0),
                )
            )
            continue

        modalidade = juros.modalidade
        if modalidade == MODALIDADE_FIXA:
            taxa = to_decimal(juros.taxa) if juros.taxa is not None else Decimal(0)
            anual = juros.unidade == UNIDADE_ANUAL
            regras.append(
                RegraJuros(
                    rotulo=(
                        f"{percentual_txt(taxa)} a.a."
                        if anual
                        else f"{percentual_txt(taxa)} ao mês"
                    ),
                    inicio=inicio,
                    fim=fim,
                    tipo=TIPO_ANUAL if anual else TIPO_MENSAL,
                    taxa=taxa,
                )
            )
        elif modalidade == MODALIDADE_TAXA_LEGAL:
            regras.append(
                RegraJuros(
                    rotulo="Taxa Legal, art. 406 do CC",
                    inicio=inicio,
                    fim=fim,
                    tipo=TIPO_TAXA_LEGAL,
                )
            )
        elif modalidade == SelicKey:
            regras.append(
                RegraJuros(
                    rotulo="SELIC",
                    inicio=inicio,
                    fim=fim,
                    tipo=TIPO_SELIC,
                )
            )
        else:
            raise ValueError(
                f"modalidade de juros não suportada em regime de atualização: "
                f"{modalidade!r}"
            )
    return regras


def _aplicar_regimes_de_verba(
    verba: VerbaSchema,
    correcao: ConfigCorrecao,
    juros: ConfigJuros,
    *,
    data_final: str,
) -> tuple[ConfigCorrecao, ConfigJuros]:
    """Troca os critérios da verba pelos dos regimes, se houver."""
    regimes = verba.regimes
    if not regimes:
        return correcao, juros

    nova_correcao = correcao
    if correcao.aplicar:
        segmentos = _segmentos_de_regimes(
            regimes,
            termo_inicial_padrao=correcao.termo_inicial,
            data_final=data_final,
        )
        nova_correcao = (
            ConfigCorrecao(aplicar=False)
            if not segmentos
            else ConfigCorrecao(
                aplicar=True,
                indexador=correcao.indexador,
                termo_inicial=segmentos[0].termo_inicial,
                termo_final=segmentos[-1].termo_final,
                segmentos=tuple(segmentos),
            )
        )

    nova_juros = juros
    if juros.aplicar:
        regras = _regras_de_regimes(regimes, data_final=data_final)
        nova_juros = (
            ConfigJuros(aplicar=False)
            if not any(_juros_do_regime(r) for r in regimes)
            else ConfigJuros(
                aplicar=True,
                modalidade=MODALIDADE_REGIMES,
                unidade=juros.unidade,
                base=juros.base,
                inicio=juros.inicio,
                fim=juros.fim,
                regras=tuple(regras),
            )
        )
    return nova_correcao, nova_juros


def _regimes_para_memoria(regimes: list[RegimeAtualizacaoSchema]) -> list[dict]:
    return [
        {
            "data_inicio": r.data_inicio,
            "data_fim": r.data_fim,
            "correcao": _correcao_do_regime(r),
            "criterio": r.criterio,
            "juros": None
            if _juros_do_regime(r) is None
            else {
                "modalidade": _juros_do_regime(r).modalidade,
                "taxa": _juros_do_regime(r).taxa,
            },
        }
        for r in regimes
    ]


def _para_data_iso(valor: object) -> date | None:
    if valor is None:
        return None
    try:
        return date.fromisoformat(str(valor).strip())
    except ValueError:
        return None


def _regime_para_memoria(resolucao: ResolucaoRegime | None) -> dict | None:
    """Serializa a resolução automática do regime sem recalcular nada.

    Os trechos carregam o critério que o motor escolheu (somente correção,
    somente juros ou correção + juros) e o texto da aplicação.
    """
    if resolucao is None or not resolucao.aplicada:
        return None
    return {
        "aplicada": bool(resolucao.aplicada),
        "motivo": resolucao.motivo,
        "trechos": [
            {
                "criterio": t.criterio,
                "inicio": t.inicio.isoformat(),
                "fim": t.fim.isoformat(),
                "aplicacao": t.aplicacao,
            }
            for t in resolucao.trechos
        ],
    }


def _aplicar_regime_temporal_de_verba(
    verba: VerbaSchema,
    correcao: ConfigCorrecao,
    juros: ConfigJuros,
    *,
    data_base_verba: str,
    data_final: str,
) -> tuple[ConfigCorrecao, ConfigJuros, ResolucaoRegime | None]:
    """Aplica o regime pós-28/08/2024 quando correção e juros têm datas próprias."""
    termino = _para_data_iso(data_final)
    if termino is None:
        return correcao, juros, None
    inicio_correcao: date | None = None
    if verba.correcao is not None:
        inicio_correcao = _para_data_iso(
            verba.correcao.termo_inicial or data_base_verba
        )
    resolucao = resolver_regime_temporal(
        correcao,
        juros,
        data_final=termino,
        inicio_correcao=inicio_correcao,
    )
    return resolucao.correcao, resolucao.juros, resolucao


def _entradas_de_verbas(
    payload: CalculoRequest,
) -> tuple[list[ParcelaInput], dict[int, dict], list[dict]]:
    """Expande verbas em ParcelaInput com configs independentes por rubrica.

    Verbas do tipo percentual são resolvidas antes da expansão:
    principal = percentual × principal da verba-base (sem herdar datas
    de correção/juros da base).
    """
    if not payload.verbas:
        raise ValueError("tipo 'parcelas' com verbas exige ao menos uma verba em 'verbas'")

    resolvidas = resolver_verbas(payload.verbas)
    entradas: list[ParcelaInput] = []
    rastros: dict[int, dict] = {}
    memoria_verbas: list[dict] = []
    numero = 0

    for resolvida in resolvidas:
        verba = payload.verbas[resolvida.indice - 1]
        principal = resolvida.principal
        principal_txt = str(principal)
        vencimento = date.fromisoformat(resolvida.data_base)
        correcao = _montar_config_correcao_de_verba(
            verba.correcao, data_base_verba=resolvida.data_base
        )
        juros = _montar_config_juros_de_verba(
            verba.juros, data_base_verba=resolvida.data_base
        )
        correcao, juros = _aplicar_regimes_de_verba(
            verba, correcao, juros, data_final=payload.data_base
        )
        regime_resolvido: ResolucaoRegime | None = None
        if not verba.regimes:
            correcao, juros, regime_resolvido = _aplicar_regime_temporal_de_verba(
                verba,
                correcao,
                juros,
                data_base_verba=resolvida.data_base,
                data_final=payload.data_base,
            )
        regime_memoria = _regime_para_memoria(regime_resolvido)
        multa = _montar_config_encargo(verba.multa)
        honorarios = _montar_config_encargo(verba.honorarios)
        pagamentos = _montar_pagamentos(verba.pagamentos)

        if verba.parcelas:
            for parcela_verba in verba.parcelas:
                numero += 1
                venc_parc = date.fromisoformat(parcela_verba.vencimento)
                correcao_p = (
                    _montar_config_correcao(parcela_verba.correcao)
                    if parcela_verba.correcao
                    else correcao
                )
                juros_p = (
                    _montar_config_juros(parcela_verba.juros)
                    if parcela_verba.juros
                    else juros
                )
                entrada = ParcelaInput(
                    numero=numero,
                    vencimento=venc_parc,
                    principal=parcela_verba.principal,
                    descricao=parcela_verba.descricao or resolvida.descricao or resolvida.nome,
                    pagamentos=_montar_pagamentos(parcela_verba.pagamentos) or pagamentos,
                    correcao=correcao_p,
                    juros=juros_p,
                    multa=multa,
                    honorarios=honorarios,
                    entra_no_total=resolvida.entra_no_total,
                )
                entradas.append(entrada)
                rastros[numero] = {
                    "verba_id": resolvida.id,
                    "verba_nome": resolvida.nome,
                    "verba_valor": principal_txt,
                    "verba_data_base": resolvida.data_base,
                    "verba_tipo": resolvida.tipo,
                    "inicio_correcao": (
                        correcao_p.termo_inicial.key if correcao_p.termo_inicial else None
                    ),
                    "inicio_juros": (
                        juros_p.inicio.isoformat() if juros_p.inicio else None
                    ),
                    "regime_temporal": regime_memoria,
                }
        else:
            numero += 1
            entrada = ParcelaInput(
                numero=numero,
                vencimento=vencimento,
                principal=principal,
                descricao=resolvida.descricao or resolvida.nome,
                pagamentos=pagamentos,
                correcao=correcao,
                juros=juros,
                multa=multa,
                honorarios=honorarios,
                entra_no_total=resolvida.entra_no_total,
            )
            entradas.append(entrada)
            rastros[numero] = {
                "verba_id": resolvida.id,
                "verba_nome": resolvida.nome,
                "verba_valor": principal_txt,
                "verba_data_base": resolvida.data_base,
                "verba_tipo": resolvida.tipo,
                "inicio_correcao": (
                    correcao.termo_inicial.key if correcao.termo_inicial else None
                ),
                "inicio_juros": juros.inicio.isoformat() if juros.inicio else None,
                "regime_temporal": regime_memoria,
            }

        inicio_correcao = next(
            (
                item["inicio_correcao"]
                for item in rastros.values()
                if item.get("verba_id") == resolvida.id and item.get("inicio_correcao")
            ),
            None,
        )
        inicio_juros = next(
            (
                item["inicio_juros"]
                for item in rastros.values()
                if item.get("verba_id") == resolvida.id and item.get("inicio_juros")
            ),
            None,
        )
        memoria_verbas.append(
            {
                "id": resolvida.id,
                "nome": resolvida.nome,
                "descricao": resolvida.descricao,
                "tipo": resolvida.tipo,
                "valor": principal_txt,
                "valor_entrada": resolvida.valor_entrada,
                "base_verba_id": resolvida.base_verba_id,
                "percentual": (
                    str(resolvida.percentual) if resolvida.percentual is not None else None
                ),
                "entra_no_total": resolvida.entra_no_total,
                "data_base": resolvida.data_base,
                "inicio_correcao": inicio_correcao,
                "inicio_juros": inicio_juros,
                "regimes": _regimes_para_memoria(verba.regimes),
                "regime_temporal": regime_memoria,
                # No modo Cível, estes encargos podem ser definidos por verba.
                # A memória precisa conservar o critério de origem para que os
                # relatórios não confundam uma configuração global vazia com
                # uma cobrança efetivamente aplicada.
                "multa": verba.multa.model_dump() if verba.multa else None,
                "honorarios": verba.honorarios.model_dump() if verba.honorarios else None,
            }
        )

    return entradas, rastros, memoria_verbas


def _entradas_manuais(
    payload: CalculoRequest,
) -> list[ParcelaInput]:
    if payload.verbas:
        entradas, _, _ = _entradas_de_verbas(payload)
        return entradas
    if not payload.parcelas:
        raise ValueError("tipo 'parcelas' exige verbas ou ao menos uma parcela")
    entradas: list[ParcelaInput] = []
    for item in payload.parcelas:
        entradas.append(
            ParcelaInput(
                numero=item.numero,
                vencimento=item.vencimento,
                principal=item.principal,
                descricao=item.descricao,
                pagamentos=_montar_pagamentos(item.pagamentos),
                correcao=_montar_config_correcao(item.correcao) if item.correcao else None,
                juros=_montar_config_juros(item.juros) if item.juros else None,
                multa=_montar_config_encargo(item.multa) if item.multa else None,
                honorarios=_montar_config_encargo(item.honorarios) if item.honorarios else None,
            )
        )
    return entradas


def _montar_config_encargo(schema: ConfigEncargoSchema | None) -> ConfigEncargo:
    if schema is None:
        return ConfigEncargo()
    kwargs: dict = {
        "aplicar": schema.aplicar,
        "base": schema.base,
    }
    if schema.percentual is not None:
        kwargs["percentual"] = to_decimal(schema.percentual)
    if schema.valor_fixo is not None:
        kwargs["valor_fixo"] = to_decimal(schema.valor_fixo)
    return ConfigEncargo(**kwargs)


def _montar_encargos_consolidados(
    schemas: list[EncargoConsolidadoSchema],
) -> list[EncargoConsolidado]:
    itens: list[EncargoConsolidado] = []
    for schema in schemas:
        if bool(schema.percentual) == bool(schema.valor_fixo):
            raise ValueError(
                f"encargo consolidado '{schema.id}' exige percentual ou valor fixo, não ambos"
            )
        percentual = to_decimal(schema.percentual) if schema.percentual is not None else None
        valor_fixo = to_decimal(schema.valor_fixo) if schema.valor_fixo is not None else None
        if percentual is not None and percentual < 0:
            raise ValueError("percentual de encargo consolidado não pode ser negativo")
        if valor_fixo is not None and valor_fixo < 0:
            raise ValueError("valor fixo de encargo consolidado não pode ser negativo")
        juros = _montar_config_juros(schema.juros) if schema.juros else None
        itens.append(EncargoConsolidado(
            id=schema.id.strip(), tipo=schema.tipo, ordem=schema.ordem,
            verba_ids=tuple(schema.verba_ids), componentes=tuple(schema.componentes),
            predecessores=tuple(schema.predecessores), percentual=percentual,
            valor_fixo=valor_fixo, juros=juros,
            inicio=date.fromisoformat(schema.inicio) if schema.inicio else None,
            fim=date.fromisoformat(schema.fim) if schema.fim else None,
            entra_no_total=schema.entra_no_total,
        ))
    return itens


def _aplicar_encargos_consolidados(corpo: dict, schemas: list[EncargoConsolidadoSchema]) -> list[dict]:
    if not schemas:
        return []
    encargos = calcular_encargos_consolidados(_montar_encargos_consolidados(schemas), corpo["parcelas"])
    resumo = corpo["resumo"]
    por_tipo = {"multa": Decimal("0.00"), "honorarios": Decimal("0.00"), "juros": Decimal("0.00")}
    total_adicional = Decimal("0.00")
    for encargo in encargos:
        valor = to_decimal(encargo["valor"])
        if encargo["entra_no_total"]:
            por_tipo[encargo["tipo"]] += valor
            total_adicional += valor
    for tipo, chave in (("multa", "multa"), ("honorarios", "honorarios"), ("juros", "juros")):
        resumo[chave] = str(round_brl(to_decimal(resumo[chave]) + por_tipo[tipo]))
    resumo["total"] = str(round_brl(to_decimal(resumo["total"]) + total_adicional))
    resumo["saldo"] = str(round_brl(to_decimal(resumo["saldo"]) + total_adicional))
    resumo["adicional"] = str(round_brl(to_decimal(resumo["adicional"]) + total_adicional))
    corpo["encargos_consolidados"] = encargos
    return encargos


def _montar_regra(schema: RegraAlimentoSchema) -> RegraAlimento:
    return RegraAlimento(
        inicio=Competencia.parse(schema.inicio),
        fim=Competencia.parse(schema.fim) if schema.fim else None,
        tipo=schema.tipo,
        percentual=to_decimal(schema.percentual) if schema.percentual is not None else None,
        valor=to_decimal(schema.valor) if schema.valor is not None else None,
        descricao=schema.descricao,
    )


def _pagamentos_por_competencia(
    pagamentos: list[PagamentoSchema],
) -> dict[str, list[Pagamento]]:
    mapa: dict[str, list[Pagamento]] = {}
    for item in pagamentos:
        if item.competencia is None:
            raise ValueError(
                "pagamento de cálculo de alimentos exige competencia "
                f"(recebido: data={item.data}, valor={item.valor})"
            )
        chave = Competencia.parse(item.competencia).key
        mapa.setdefault(chave, []).append(
            Pagamento(
                data=date.fromisoformat(item.data),
                valor=to_decimal(item.valor),
                descricao=item.descricao,
            )
        )
    return mapa


def _entradas_de_alimentos(
    payload: CalculoRequest,
) -> tuple[list[ParcelaInput], dict[int, RastroParcela]]:
    if payload.alimentos is None:
        raise ValueError("tipo 'alimentos' exige o bloco 'alimentos' com regras")
    regras = tuple(_montar_regra(r) for r in payload.alimentos.regras)
    parcelas = gerar_parcelas(
        regras,
        ate=payload.alimentos.ate,
        dia_vencimento=payload.alimentos.dia_vencimento,
    )
    pagamentos = _pagamentos_por_competencia(payload.pagamentos)
    entradas = entradas_de_alimentos(parcelas)

    indexador = obter(SalarioKey)
    rastros: dict[int, RastroParcela] = {}
    reajustadas: list[ParcelaInput] = []
    for entrada in entradas:
        parcela_origem = next(p for p in parcelas if p.numero == entrada.numero)
        rastros[entrada.numero] = RastroParcela(
            numero=entrada.numero,
            salario_minimo=(
                indexador.salario(entrada.competencia)
                if parcela_origem.usou_salario_minimo
                else None
            ),
            percentual=(
                next(
                    (
                        r.percentual
                        for r in regras
                        if r.tipo == TIPO_SALARIO_MINIMO
                        and r.inicio <= entrada.competencia
                        and (r.fim is None or entrada.competencia <= r.fim)
                    ),
                    None,
                )
            ),
            tipo_regra=(
                TIPO_SALARIO_MINIMO if parcela_origem.usou_salario_minimo else TIPO_FIXO
            ),
            origem=parcela_origem.origem,
            detalhe=parcela_origem.detalhe,
        )
        extras = pagamentos.get(entrada.competencia.key, [])
        if extras:
            reajustadas.append(
                ParcelaInput(
                    numero=entrada.numero,
                    vencimento=entrada.vencimento,
                    principal=entrada.principal,
                    competencia=entrada.competencia,
                    correcao=entrada.correcao,
                    juros=entrada.juros,
                    multa=entrada.multa,
                    honorarios=entrada.honorarios,
                    pagamentos=tuple(extras),
                    descricao=entrada.descricao,
                    indexadores=entrada.indexadores,
                )
            )
        else:
            reajustadas.append(entrada)
    return reajustadas, rastros


def _configuracao_para_memoria(configuracao: ConfiguracaoCalculo) -> dict:
    return {
        "data_base": configuracao.data_base.isoformat(),
        "correcao": {
            "aplicar": configuracao.correcao.aplicar,
            "indexador": configuracao.correcao.indexador,
            "termo_inicial": (
                configuracao.correcao.termo_inicial.key
                if configuracao.correcao.termo_inicial
                else None
            ),
            "termo_final": (
                configuracao.correcao.termo_final.key
                if configuracao.correcao.termo_final
                else None
            ),
        },
        "juros": {
            "aplicar": configuracao.juros.aplicar,
            "modalidade": configuracao.juros.modalidade,
            "taxa": str(configuracao.juros.taxa) if configuracao.juros.taxa is not None else None,
            "unidade": configuracao.juros.unidade,
            "base": configuracao.juros.base,
        },
        "multa": {
            "aplicar": configuracao.multa.aplicar,
            "percentual": (
                str(configuracao.multa.percentual)
                if configuracao.multa.percentual is not None
                else None
            ),
            "valor_fixo": (
                str(configuracao.multa.valor_fixo)
                if configuracao.multa.valor_fixo is not None
                else None
            ),
            "base": configuracao.multa.base,
        },
        "honorarios": {
            "aplicar": configuracao.honorarios.aplicar,
            "percentual": (
                str(configuracao.honorarios.percentual)
                if configuracao.honorarios.percentual is not None
                else None
            ),
            "valor_fixo": (
                str(configuracao.honorarios.valor_fixo)
                if configuracao.honorarios.valor_fixo is not None
                else None
            ),
            "base": configuracao.honorarios.base,
        },
    }


def _entradas_atualizacao(
    payload: CalculoRequest,
) -> tuple[list[ParcelaInput], ConfiguracaoCalculo, dict]:
    if payload.valor_base is None:
        raise ValueError("tipo 'atualizacao' exige o bloco 'valor_base'")
    if payload.data_final:
        data_final = date.fromisoformat(payload.data_final)
    else:
        data_final = date.fromisoformat(payload.data_base)

    data_base_valor = date.fromisoformat(payload.valor_base.data_base)
    if data_final < data_base_valor:
        raise ValueError(
            f"data final ({data_final.isoformat()}) anterior à data-base do valor "
            f"({data_base_valor.isoformat()})"
        )

    if payload.correcao is None:
        correcao = ConfigCorrecao(
            aplicar=True,
            indexador="tjsp_tabela_pratica",
            termo_inicial=Competencia.parse(data_base_valor),
            termo_final=Competencia.parse(data_final),
        )
    else:
        correcao = ConfigCorrecao(
            aplicar=payload.correcao.aplicar,
            indexador=payload.correcao.indexador,
            termo_inicial=(
                Competencia.parse(payload.correcao.termo_inicial)
                if payload.correcao.termo_inicial
                else Competencia.parse(data_base_valor)
            ),
            termo_final=(
                Competencia.parse(payload.correcao.termo_final)
                if payload.correcao.termo_final
                else Competencia.parse(data_final)
            ),
        )

    juros = (
        _montar_config_juros(payload.juros)
        if payload.juros is not None
        else ConfigJuros(aplicar=False)
    )
    multa = _montar_config_encargo(payload.multa)
    honorarios = _montar_config_encargo(payload.honorarios)

    configuracao = ConfiguracaoCalculo(
        data_base=data_final,
        correcao=correcao,
        juros=juros,
        multa=multa,
        honorarios=honorarios,
    )
    entrada = ParcelaInput(
        numero=1,
        vencimento=data_base_valor,
        principal=payload.valor_base.valor,
        competencia=Competencia.parse(data_base_valor),
        descricao=payload.valor_base.descricao or "Atualização de valor-base",
    )
    contexto = {
        "valor_original": entrada.principal,
        "data_base_valor": data_base_valor.isoformat(),
        "data_final": data_final.isoformat(),
        "descricao": payload.valor_base.descricao or "Atualização de valor-base",
        "correcao": correcao,
    }
    return [entrada], configuracao, contexto


def _montar_bloco_atualizacao(corpo: dict, contexto: dict) -> dict:
    parcela = corpo["parcelas"][0]
    correcao = parcela.get("correcao") or {}
    juros = parcela.get("juros") or {}
    multa = parcela.get("multa") or {}
    honorarios = parcela.get("honorarios") or {}
    return {
        "valor_original": str(contexto["valor_original"]),
        "data_base": contexto["data_base_valor"],
        "data_final": contexto["data_final"],
        "descricao": contexto["descricao"],
        "indexador": correcao.get("indexador"),
        "indexador_versao": correcao.get("indexador_versao"),
        "indexador_fonte": correcao.get("indexador_fonte"),
        "fator_inicial": correcao.get("fator_inicial"),
        "fator_final": correcao.get("fator_final"),
        "razao": correcao.get("razao"),
        "termo_inicial": correcao.get("termo_inicial"),
        "termo_final": correcao.get("termo_final"),
        "valor_corrigido": correcao.get("valor_corrigido"),
        "correcao": correcao.get("correcao"),
        "juros": juros.get("juros"),
        "multa": multa.get("valor"),
        "honorarios": honorarios.get("valor"),
        "valor_atualizado": parcela.get("total"),
        "total": parcela.get("total"),
        "motivo_correcao": correcao.get("motivo"),
        "motivo_juros": juros.get("motivo"),
    }


def executar_calculo(payload: CalculoRequest, session: Session) -> dict:
    settings = get_settings()
    verbas_memoria: list[dict] = []
    rastros: dict[int, object] = {}

    if payload.tipo == "atualizacao":
        entradas, configuracao, contexto_atualizacao = _entradas_atualizacao(payload)
    else:
        data_base = date.fromisoformat(payload.data_base)
        configuracao = ConfiguracaoCalculo(
            data_base=data_base,
            correcao=_montar_config_correcao(payload.correcao),
            juros=_montar_config_juros(payload.juros),
            multa=_montar_config_encargo(payload.multa),
            honorarios=_montar_config_encargo(payload.honorarios),
        )
        contexto_atualizacao = None
        if payload.tipo == "alimentos":
            entradas, rastros = _entradas_de_alimentos(payload)
        elif payload.verbas:
            entradas, rastros, verbas_memoria = _entradas_de_verbas(payload)
            for item in verbas_memoria:
                item["parcelas"] = [
                    {
                        "numero": numero,
                        "verba_id": rastro.get("verba_id"),
                        "inicio_correcao": rastro.get("inicio_correcao"),
                        "inicio_juros": rastro.get("inicio_juros"),
                    }
                    for numero, rastro in rastros.items()
                    if rastro.get("verba_id") == item["id"]
                ]
        else:
            entradas = _entradas_manuais(payload)

    definir_overrides_ativos(carregar_overrides_da_sessao(session))
    try:
        resultado = calcular(configuracao, entradas)
    finally:
        usados = [item.as_dict() for item in overrides_utilizados()]
        limpar_overrides_ativos()

    corpo = serializar_calculo(
        resultado,
        tipo=payload.tipo,
        app_version=settings.app_version,
        rastros=rastros,
        payload=payload.model_dump(mode="json"),
        verbas=verbas_memoria,
    )
    encargos_consolidados = _aplicar_encargos_consolidados(corpo, payload.encargos_consolidados)

    codigo = gerar_codigo_calculo(session)
    data_geracao = datetime.now(timezone.utc)
    payload_dict = payload.model_dump(mode="json")
    bloco_atualizacao = (
        _montar_bloco_atualizacao(corpo, contexto_atualizacao)
        if contexto_atualizacao is not None
        else None
    )
    revisao_numero = 1
    if payload.revisao_de:
        origem = session.scalar(select(Calculo).where(Calculo.codigo == payload.revisao_de))
        if origem is None:
            raise ValueError(f"cálculo original não encontrado: {payload.revisao_de}")
        # A numeração pertence à família inteira, inclusive quando se revisa
        # uma revisão. Assim, original → R2 → R3 e duas revisões paralelas
        # não reutilizam o mesmo número silenciosamente.
        todos = session.scalars(select(Calculo)).all()
        por_codigo = {item.codigo: item for item in todos}
        raiz = origem
        while raiz.revisao_de_codigo and raiz.revisao_de_codigo in por_codigo:
            raiz = por_codigo[raiz.revisao_de_codigo]
        familia = {raiz.codigo}
        mudou = True
        while mudou:
            mudou = False
            for item in todos:
                if item.revisao_de_codigo in familia and item.codigo not in familia:
                    familia.add(item.codigo)
                    mudou = True
        revisao_numero = max(
            (item.revisao_numero or 1 for item in todos if item.codigo in familia),
            default=1,
        ) + 1
    memoria = montar_memoria(
        codigo=codigo,
        tipo=payload.tipo,
        titulo=payload.titulo,
        processo=payload.processo,
        parte=payload.parte,
        app_name=settings.app_name,
        app_version=settings.app_version,
        data_geracao=data_geracao,
        data_base=corpo["data_base"],
        configuracao=_configuracao_para_memoria(configuracao),
        payload=payload_dict,
        resumo=corpo["resumo"],
        parcelas=corpo["parcelas"],
        bases=corpo["bases"],
        avisos=corpo["avisos"],
        atualizacao=bloco_atualizacao,
        overrides_utilizados=usados,
        verbas=verbas_memoria,
        encargos_consolidados=encargos_consolidados,
    )
    if payload.revisao_de:
        memoria["revisao"] = {"origem_codigo": payload.revisao_de, "numero": revisao_numero}

    registro = Calculo(
        codigo=codigo,
        tipo=payload.tipo,
        titulo=payload.titulo,
        processo=payload.processo,
        parte=payload.parte,
        app_version=settings.app_version,
        payload_json=payload.model_dump_json(),
        resultado_json=serializar_para_persistencia(corpo),
        bases_json=serializar_para_persistencia(corpo["bases"]),
        memoria_json=serializar_para_persistencia(memoria),
        revisao_de_codigo=payload.revisao_de,
        revisao_numero=revisao_numero,
        created_at=data_geracao,
    )
    session.add(registro)
    session.flush()

    resposta = dict(corpo)
    resposta["codigo"] = codigo
    resposta["titulo"] = payload.titulo
    resposta["processo"] = payload.processo
    resposta["parte"] = payload.parte
    resposta["created_at"] = registro.created_at.isoformat()
    resposta["revisao_de"] = registro.revisao_de_codigo
    resposta["revisao_numero"] = registro.revisao_numero
    resposta["memoria"] = memoria
    return resposta


def serializar_para_persistencia(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
