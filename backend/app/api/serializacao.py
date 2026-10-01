from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import round_brl, to_decimal
from app.engine.calculo import BaseUtilizada, ResultadoCalculo
from app.engine.correcao import ResultadoCorrecao
from app.engine.encargos import Pagamento, ResultadoEncargo
from app.engine.juros import ResultadoJuros
from app.engine.parcela import ResultadoParcela

__all__ = [
    "RastroParcela",
    "serializar_calculo",
    "serializar_pagamento",
]


@dataclass(frozen=True)
class RastroParcela:
    numero: int
    salario_minimo: Decimal | None = None
    percentual: Decimal | None = None
    tipo_regra: str | None = None
    origem: str = ""
    detalhe: str = ""


def _dec(valor: object | None) -> str | None:
    if valor is None:
        return None
    return str(valor)


def _brl(valor: object | None) -> str | None:
    if valor is None:
        return None
    return str(round_brl(valor))


def _percentual(valor: object | None) -> str | None:
    if valor is None:
        return None
    return str(to_decimal(valor))


def _comp(valor: Competencia | None) -> str | None:
    return None if valor is None else valor.key


def _data(valor: date | None) -> str | None:
    return None if valor is None else valor.isoformat()


def serializar_pagamento(pagamento: Pagamento) -> dict:
    return {
        "data": pagamento.data.isoformat(),
        "valor": str(round_brl(pagamento.valor)),
        "descricao": pagamento.descricao,
    }


def _serializar_correcao(resultado: ResultadoCorrecao) -> dict:
    return {
        "aplicado": resultado.aplicado,
        "principal": str(round_brl(resultado.principal)),
        "valor_corrigido": str(round_brl(resultado.valor_corrigido)),
        "correcao": str(round_brl(resultado.correcao)),
        "motivo": resultado.motivo,
        "indexador": resultado.indexador,
        "indexador_versao": resultado.indexador_versao,
        "indexador_fonte": resultado.indexador_fonte,
        "termo_inicial": _comp(resultado.termo_inicial),
        "termo_final": _comp(resultado.termo_final),
        "fator_inicial": _dec(resultado.fator_inicial),
        "fator_final": _dec(resultado.fator_final),
        "razao": _dec(resultado.razao),
        "fator_exibicao": _dec(resultado.fator_exibicao),
    }


def _serializar_juros(resultado: ResultadoJuros) -> dict:
    return {
        "aplicado": resultado.aplicado,
        "motivo": resultado.motivo,
        "base": str(round_brl(resultado.base)),
        "incidencia": resultado.incidencia,
        "modalidade": resultado.modalidade,
        "juros": str(round_brl(resultado.juros)),
        "indexador": resultado.indexador,
        "indexador_versao": resultado.indexador_versao,
        "indexador_fonte": resultado.indexador_fonte,
        "trechos": [
            {
                "rotulo": t.rotulo,
                "inicio": t.inicio.isoformat(),
                "fim": t.fim.isoformat(),
                "dias": t.dias,
                "taxa": _dec(t.taxa),
                "taxa_rotulo": t.taxa_rotulo,
                "valor": str(round_brl(t.valor)),
            }
            for t in resultado.trechos
        ],
    }


def _serializar_encargo(resultado: ResultadoEncargo) -> dict:
    return {
        "aplicado": resultado.aplicado,
        "motivo": resultado.motivo,
        "valor": str(round_brl(resultado.valor)),
        "percentual": _percentual(resultado.percentual),
        "base_nome": resultado.base_nome,
        "base_rotulo": resultado.base_rotulo,
        "base_valor": _brl(resultado.base_valor),
    }


def _serializar_parcela(
    resultado: ResultadoParcela,
    rastro: object | None,
) -> dict:
    dados = {
        "numero": resultado.numero,
        "competencia": resultado.competencia.key,
        "competencia_rotulo": resultado.competencia.label,
        "vencimento": resultado.vencimento.isoformat(),
        "descricao": resultado.descricao,
        "principal": str(round_brl(resultado.principal)),
        "correcao": _serializar_correcao(resultado.correcao),
        "juros": _serializar_juros(resultado.juros),
        "multa": _serializar_encargo(resultado.multa),
        "honorarios": _serializar_encargo(resultado.honorarios),
        "pagamentos": [serializar_pagamento(p) for p in resultado.pagamentos],
        "total": str(round_brl(resultado.total)),
        "total_pago": str(round_brl(resultado.total_pago)),
        "saldo": str(round_brl(resultado.saldo)),
        "adicional": str(round_brl(resultado.adicional)),
        "salario_minimo": None,
        "percentual": None,
        "tipo_regra": None,
        "origem": "",
        "detalhe": "",
        "verba": None,
        "inicio_correcao": _comp(resultado.correcao.termo_inicial),
        "inicio_juros": (
            resultado.juros.trechos[0].inicio.isoformat()
            if resultado.juros.trechos
            else None
        ),
    }
    if isinstance(rastro, RastroParcela):
        dados["salario_minimo"] = _brl(rastro.salario_minimo)
        dados["percentual"] = _percentual(rastro.percentual)
        dados["tipo_regra"] = rastro.tipo_regra
        dados["origem"] = rastro.origem
        dados["detalhe"] = rastro.detalhe
        if rastro.detalhe and not dados["descricao"]:
            dados["descricao"] = rastro.detalhe
    elif isinstance(rastro, dict):
        if rastro.get("verba_nome"):
            dados["verba"] = {
                "id": rastro.get("verba_id"),
                "nome": rastro.get("verba_nome"),
                "valor": rastro.get("verba_valor"),
                "data_base": rastro.get("verba_data_base"),
            }
        if rastro.get("inicio_correcao"):
            dados["inicio_correcao"] = rastro["inicio_correcao"]
        if rastro.get("inicio_juros"):
            dados["inicio_juros"] = rastro["inicio_juros"]
        if rastro.get("detalhe") and not dados["descricao"]:
            dados["descricao"] = rastro["detalhe"]
    return dados


def _serializar_base(base: BaseUtilizada) -> dict:
    return {
        "key": base.key,
        "nome": base.nome,
        "versao": base.versao,
        "fonte": base.fonte,
        "fonte_url": base.fonte_url,
        "papel": base.papel,
        "cobertura": base.cobertura,
    }


def serializar_calculo(
    resultado: ResultadoCalculo,
    *,
    tipo: str,
    app_version: str,
    rastros: dict[int, object] | None = None,
    payload: dict | None = None,
    verbas: list[dict] | None = None,
) -> dict:
    mapa = rastros or {}
    resumo = resultado.resumo
    return {
        "tipo": tipo,
        "app_version": app_version,
        "data_base": resultado.data_base.isoformat(),
        "resumo": {
            "qtd_parcelas": resumo.qtd_parcelas,
            "periodo_inicio": _data(resumo.periodo_inicio),
            "periodo_fim": _data(resumo.periodo_fim),
            "principal": str(round_brl(resumo.principal)),
            "correcao": str(round_brl(resumo.correcao)),
            "juros": str(round_brl(resumo.juros)),
            "multa": str(round_brl(resumo.multa)),
            "honorarios": str(round_brl(resumo.honorarios)),
            "total": str(round_brl(resumo.total)),
            "pagamentos": str(round_brl(resumo.pagamentos)),
            "saldo": str(round_brl(resumo.saldo)),
            "adicional": str(round_brl(resumo.adicional)),
        },
        "parcelas": [
            _serializar_parcela(p, mapa.get(p.numero)) for p in resultado.parcelas
        ],
        "verbas": [dict(v) for v in (verbas or [])],
        "bases": [_serializar_base(b) for b in resultado.bases],
        "avisos": list(resultado.avisos),
        "payload": payload or {},
    }
