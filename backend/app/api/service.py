from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    CalculoRequest,
    ConfigCorrecaoSchema,
    ConfigEncargoSchema,
    ConfigJurosSchema,
    PagamentoSchema,
    RegraAlimentoSchema,
    VerbaSchema,
)
from app.api.serializacao import RastroParcela, serializar_calculo
from app.core.competencia import Competencia
from app.core.config import get_settings
from app.core.money import to_decimal
from app.engine.alimentos import (
    TIPO_FIXO,
    TIPO_SALARIO_MINIMO,
    RegraAlimento,
    entradas_de_alimentos,
    gerar_parcelas,
)
from app.engine.calculo import calcular
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.correcao import ConfigCorrecao
from app.engine.encargos import ConfigEncargo, Pagamento
from app.engine.juros import ConfigJuros
from app.engine.memoria import montar_memoria
from app.engine.parcela import ParcelaInput
from app.indexers import obter
from app.indexers.overrides import (
    carregar_overrides_da_sessao,
    definir_overrides_ativos,
    limpar_overrides_ativos,
    overrides_utilizados,
)
from app.indexers.salario_minimo import KEY as SalarioKey
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


def _entradas_de_verbas(
    payload: CalculoRequest,
) -> tuple[list[ParcelaInput], dict[int, dict]]:
    """Expande verbas em ParcelaInput com configs independentes por rubrica."""
    if not payload.verbas:
        raise ValueError("tipo 'parcelas' com verbas exige ao menos uma verba em 'verbas'")

    entradas: list[ParcelaInput] = []
    rastros: dict[int, dict] = {}
    numero = 0

    for indice, verba in enumerate(payload.verbas, start=1):
        vencimento = date.fromisoformat(verba.data_base)
        correcao = _montar_config_correcao_de_verba(
            verba.correcao, data_base_verba=verba.data_base
        )
        juros = _montar_config_juros_de_verba(
            verba.juros, data_base_verba=verba.data_base
        )
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
                    descricao=parcela_verba.descricao or verba.descricao or verba.nome,
                    pagamentos=_montar_pagamentos(parcela_verba.pagamentos) or pagamentos,
                    correcao=correcao_p,
                    juros=juros_p,
                    multa=multa,
                    honorarios=honorarios,
                )
                entradas.append(entrada)
                rastros[numero] = {
                    "verba_id": f"verba-{indice}",
                    "verba_nome": verba.nome,
                    "verba_valor": verba.valor,
                    "verba_data_base": verba.data_base,
                    "inicio_correcao": (
                        correcao_p.termo_inicial.key if correcao_p.termo_inicial else None
                    ),
                    "inicio_juros": (
                        juros_p.inicio.isoformat() if juros_p.inicio else None
                    ),
                }
        else:
            numero += 1
            entrada = ParcelaInput(
                numero=numero,
                vencimento=vencimento,
                principal=verba.valor,
                descricao=verba.descricao or verba.nome,
                pagamentos=pagamentos,
                correcao=correcao,
                juros=juros,
                multa=multa,
                honorarios=honorarios,
            )
            entradas.append(entrada)
            rastros[numero] = {
                "verba_id": f"verba-{indice}",
                "verba_nome": verba.nome,
                "verba_valor": verba.valor,
                "verba_data_base": verba.data_base,
                "inicio_correcao": (
                    correcao.termo_inicial.key if correcao.termo_inicial else None
                ),
                "inicio_juros": juros.inicio.isoformat() if juros.inicio else None,
            }

    return entradas, rastros


def _entradas_manuais(
    payload: CalculoRequest,
) -> list[ParcelaInput]:
    if payload.verbas:
        entradas, _ = _entradas_de_verbas(payload)
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


def _montar_verbas_para_memoria(
    payload: CalculoRequest,
    rastros: dict[int, dict],
) -> list[dict]:
    verbas: list[dict] = []
    for indice, verba in enumerate(payload.verbas or [], start=1):
        verba_id = f"verba-{indice}"
        parcelas_da_verba = [
            {
                "numero": numero,
                "verba_id": item.get("verba_id"),
                "inicio_correcao": item.get("inicio_correcao"),
                "inicio_juros": item.get("inicio_juros"),
            }
            for numero, item in rastros.items()
            if item.get("verba_id") == verba_id
        ]
        inicio_correcao = next(
            (p["inicio_correcao"] for p in parcelas_da_verba if p["inicio_correcao"]),
            None,
        )
        inicio_juros = next(
            (p["inicio_juros"] for p in parcelas_da_verba if p["inicio_juros"]),
            None,
        )
        verbas.append(
            {
                "id": verba_id,
                "nome": verba.nome,
                "descricao": verba.descricao,
                "valor": verba.valor,
                "data_base": verba.data_base,
                "inicio_correcao": inicio_correcao,
                "inicio_juros": inicio_juros,
                "parcelas": parcelas_da_verba,
            }
        )
    return verbas


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
            entradas, rastros = _entradas_de_verbas(payload)
            verbas_memoria = _montar_verbas_para_memoria(payload, rastros)
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

    codigo = gerar_codigo_calculo(session)
    data_geracao = datetime.now(timezone.utc)
    payload_dict = payload.model_dump(mode="json")
    bloco_atualizacao = (
        _montar_bloco_atualizacao(corpo, contexto_atualizacao)
        if contexto_atualizacao is not None
        else None
    )
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
    )

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
    resposta["memoria"] = memoria
    return resposta


def serializar_para_persistencia(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
