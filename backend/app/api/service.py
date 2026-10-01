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
    return ConfigJuros(**kwargs)


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


def _entradas_manuais(
    payload: CalculoRequest,
) -> list[ParcelaInput]:
    if not payload.parcelas:
        raise ValueError("tipo 'parcelas' exige ao menos uma parcela em 'parcelas'")
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
            )
        )
    return entradas


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


def executar_calculo(payload: CalculoRequest, session: Session) -> dict:
    settings = get_settings()
    data_base = date.fromisoformat(payload.data_base)

    configuracao = ConfiguracaoCalculo(
        data_base=data_base,
        correcao=_montar_config_correcao(payload.correcao),
        juros=_montar_config_juros(payload.juros),
        multa=_montar_config_encargo(payload.multa),
        honorarios=_montar_config_encargo(payload.honorarios),
    )

    if payload.tipo == "alimentos":
        entradas, rastros = _entradas_de_alimentos(payload)
    else:
        entradas, rastros = _entradas_manuais(payload), {}

    resultado = calcular(configuracao, entradas)
    corpo = serializar_calculo(
        resultado,
        tipo=payload.tipo,
        app_version=settings.app_version,
        rastros=rastros,
        payload=payload.model_dump(mode="json"),
    )

    codigo = gerar_codigo_calculo(session)
    data_geracao = datetime.now(timezone.utc)
    payload_dict = payload.model_dump(mode="json")
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
