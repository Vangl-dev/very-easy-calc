from __future__ import annotations

import calendar
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

CRITERIO_SOMENTE_JUROS = "somente_juros"
CRITERIO_CORRECAO_E_JUROS = "correcao_e_juros"

ARREDONDAMENTO = {
    "casas": 2,
    "modo": "ROUND_HALF_UP",
    "rotina": "round_brl",
}

CONVENCAO_COMPETENCIA = (
    "Correção mensal: a data civil é reduzida à competência (ano, mês) e a "
    "razão usa o índice do mês do termo final sobre o índice do mês do "
    "termo inicial."
)
CONVENCAO_FRONTEIRA = (
    "Segmentos consecutivos compartilham a mesma competência de referência: "
    "a razão do segundo segmento parte do índice em que o primeiro termina, "
    "sem lacuna e sem aplicar o fator duas vezes."
)
CONVENCAO_ARREDONDAMENTO = (
    "O arredondamento é aplicado uma única vez, ao final da cadeia de "
    "segmentos; valores intermediários por segmento não são produzidos pelo "
    "motor."
)
CONVENCAO_SELIC_INTEGRAL = (
    "No critério correção + juros a SELIC embute correção e juros: o trecho "
    "de juros correspondente fica com valor 0,00 e não é somado em separado."
)
CONVENCAO_JUROS_DIAS = (
    "Quando a taxa varia por competência (SELIC, SELIC − IPCA, Taxa Legal), o "
    "motor aplica a taxa do mês proporcionalmente aos dias decorridos."
)


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
        "segmentos": [
            {
                "termo_inicial": _comp(s.termo_inicial),
                "termo_final": _comp(s.termo_final),
                "indexador": s.indexador,
                "indexador_versao": s.indexador_versao,
                "indexador_fonte": s.indexador_fonte,
                "fator_inicial": _dec(s.fator_inicial),
                "fator_final": _dec(s.fator_final),
                "razao": _dec(s.razao),
            }
            for s in resultado.segmentos
        ],
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


def _fim_do_mes(comp: Competencia) -> str:
    return f"{comp.year:04d}-{comp.month:02d}-{calendar.monthrange(comp.year, comp.month)[1]:02d}"


def _criterio_em(regime: dict | None, data_iso: str) -> str | None:
    """Critério do regime automático que cobre a data de referência do segmento."""
    if not regime:
        return None
    for trecho in regime.get("trechos") or []:
        fim = trecho.get("fim")
        if trecho.get("inicio", "") <= data_iso and (fim is None or data_iso <= fim):
            return trecho.get("criterio")
    return None


def _rotulo_do(regime: dict | None, criterio: str | None) -> str | None:
    if not regime or not criterio:
        return None
    for trecho in regime.get("trechos") or []:
        if trecho.get("criterio") == criterio:
            return trecho.get("aplicacao")
    return None


def _serie_de(chave: str | None, bases: dict[str, BaseUtilizada]) -> dict:
    base = bases.get(chave) if chave else None
    if base is None:
        return {"key": chave, "nome": None, "fonte": None, "versao": None}
    return {
        "key": base.key,
        "nome": base.nome,
        "fonte": base.fonte,
        "versao": base.versao,
    }


def _series_de_juros(bases: dict[str, BaseUtilizada]) -> list[dict]:
    """Séries com papel de juros, na ordem em que o motor as registrou."""
    return [
        _serie_de(base.key, bases)
        for base in bases.values()
        if "Juros" in (base.papel or "")
    ]


def _segmentos_temporais(
    resultado: ResultadoParcela,
    regime: dict | None,
    bases: dict[str, BaseUtilizada],
) -> dict | None:
    """Segmenta temporalmente a parcela a partir do resultado do motor.

    Não recalcula fatores nem montantes: apenas reorganiza os segmentos de
    correção e os trechos de juros que o motor já produziu, acrescentando o
    critério do regime automático quando existe.
    """
    correcao = resultado.correcao
    juros = resultado.juros
    resolvido = bool(regime and regime.get("aplicada"))
    if not correcao.segmentos and not resolvido:
        return None

    itens: list[dict] = []
    for s in correcao.segmentos:
        criterio = _criterio_em(regime, _fim_do_mes(s.termo_final))
        itens.append(
            {
                "tipo": "correcao",
                "criterio": criterio,
                "criterio_rotulo": _rotulo_do(regime, criterio),
                "periodo": {
                    "termo_inicial": s.termo_inicial.key,
                    "termo_final": s.termo_final.key,
                    "data_inicio": f"{s.termo_inicial.key}-01",
                    "data_fim": _fim_do_mes(s.termo_final),
                    "unidade": "competencia",
                },
                "indexador": s.indexador,
                "serie": _serie_de(s.indexador, bases),
                "fator_inicial": _dec(s.fator_inicial),
                "fator_final": _dec(s.fator_final),
                "fator_acumulado": _dec(s.razao),
                "arredondamento": ARREDONDAMENTO,
                "valor_base": None,
                "valor_resultante": None,
                "juros_incorporados": criterio == CRITERIO_CORRECAO_E_JUROS,
            }
        )
    if itens:
        # a cadeia parte do principal e termina no valor corrigido; o motor
        # arredonda uma única vez, então não há montante por segmento
        itens[0]["valor_base"] = str(round_brl(correcao.principal))
        itens[-1]["valor_resultante"] = str(round_brl(correcao.valor_corrigido))

    for trecho in juros.trechos:
        criterio = _criterio_em(regime, trecho.fim.isoformat())
        itens.append(
            {
                "tipo": "juros",
                "criterio": criterio,
                "criterio_rotulo": _rotulo_do(regime, criterio),
                "periodo": {
                    "data_inicio": trecho.inicio.isoformat(),
                    "data_fim": trecho.fim.isoformat(),
                    "unidade": "data",
                },
                "dias": trecho.dias,
                "proporcional_aos_dias": trecho.taxa is None and trecho.valor != 0,
                "taxa": _dec(trecho.taxa),
                "taxa_rotulo": trecho.taxa_rotulo,
                "piso_mensal_zero": "piso mensal zero" in (trecho.taxa_rotulo or ""),
                "indexador": juros.indexador,
                "serie": (
                    _serie_de(juros.indexador, bases) if juros.indexador else None
                ),
                "series_envolvidas": (
                    _series_de_juros(bases)
                    if criterio == CRITERIO_SOMENTE_JUROS
                    else None
                ),
                "arredondamento": ARREDONDAMENTO,
                "valor_base": str(round_brl(juros.base)),
                "valor_resultante": str(round_brl(trecho.valor)),
                "juros_incorporados": criterio == CRITERIO_CORRECAO_E_JUROS,
            }
        )

    return {
        "origem": "regime_automatico" if resolvido else "segmentacao_da_verba",
        "convencao": {
            "competencia": CONVENCAO_COMPETENCIA,
            "fronteira_compartilhada": CONVENCAO_FRONTEIRA,
            "arredondamento": CONVENCAO_ARREDONDAMENTO,
            "selic_integral": CONVENCAO_SELIC_INTEGRAL,
            "juros_proporcionais_aos_dias": CONVENCAO_JUROS_DIAS,
        },
        "motivo": regime.get("motivo") if regime else None,
        "segmentos": itens,
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
    bases: dict[str, BaseUtilizada],
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
        "diferenca": str(round_brl(resultado.principal - resultado.total_pago)),
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

    regime = rastro.get("regime_temporal") if isinstance(rastro, dict) else None
    if regime is not None:
        dados["regime_temporal"] = regime
    temporais = _segmentos_temporais(resultado, regime, bases)
    if temporais is not None:
        dados["segmentos_temporais"] = temporais
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
    bases_por_key = {b.key: b for b in resultado.bases}
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
            _serializar_parcela(p, mapa.get(p.numero), bases_por_key)
            for p in resultado.parcelas
        ],
        "verbas": [dict(v) for v in (verbas or [])],
        "encargos_consolidados": [],
        "bases": [_serializar_base(b) for b in resultado.bases],
        "avisos": list(resultado.avisos),
        "payload": payload or {},
    }
