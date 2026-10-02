from __future__ import annotations

from datetime import datetime

ESQUEMA_MEMORIA = "memoria-calculo/1.3"

__all__ = ["ESQUEMA_MEMORIA", "montar_memoria"]


def _critério_encargo(config: dict | None) -> dict:
    if config is None:
        return {"aplicar": False}
    return {
        "aplicar": bool(config.get("aplicar", False)),
        "percentual": config.get("percentual"),
        "valor_fixo": config.get("valor_fixo"),
        "base": config.get("base", "corrigido"),
    }


def _criterios_de(
    *,
    data_base: str,
    configuracao: dict,
    payload: dict,
    verbas: list[dict] | None = None,
) -> dict:
    correcao = configuracao.get("correcao") or {}
    juros = configuracao.get("juros") or {}
    alimentos = payload.get("alimentos")
    return {
        "data_base": data_base,
        "correcao": {
            "aplicar": bool(correcao.get("aplicar", False)),
            "indexador": correcao.get("indexador"),
            "termo_inicial": correcao.get("termo_inicial"),
            "termo_final": correcao.get("termo_final"),
        },
        "juros": {
            "aplicar": bool(juros.get("aplicar", False)),
            "modalidade": juros.get("modalidade"),
            "taxa": juros.get("taxa"),
            "unidade": juros.get("unidade"),
            "base": juros.get("base"),
        },
        "multa": _critério_encargo(configuracao.get("multa")),
        "honorarios": _critério_encargo(configuracao.get("honorarios")),
        "alimentos": None
        if alimentos is None
        else {
            "regras": list(alimentos.get("regras") or []),
            "ate": alimentos.get("ate"),
            "dia_vencimento": alimentos.get("dia_vencimento"),
        },
        "verbas": [
            {
                "nome": v.get("nome"),
                "valor": v.get("valor"),
                "data_base": v.get("data_base"),
                "inicio_correcao": v.get("inicio_correcao"),
                "inicio_juros": v.get("inicio_juros"),
            }
            for v in (verbas or [])
        ],
        "pagamentos_informados": list(payload.get("pagamentos") or []),
    }


def _parcela_de_memoria(parcela: dict) -> dict:
    item = dict(parcela)
    tipo_regra = item.get("tipo_regra")
    if tipo_regra:
        item["regra"] = {
            "tipo": tipo_regra,
            "origem": item.get("origem", ""),
            "detalhe": item.get("detalhe", ""),
            "salario_minimo": item.get("salario_minimo"),
            "percentual": item.get("percentual"),
        }
    else:
        item["regra"] = None
    return item


def montar_memoria(
    *,
    codigo: str,
    tipo: str,
    titulo: str,
    processo: str,
    parte: str,
    app_name: str,
    app_version: str,
    data_geracao: datetime,
    data_base: str,
    configuracao: dict,
    payload: dict,
    resumo: dict,
    parcelas: list[dict],
    bases: list[dict],
    avisos: list[str],
    atualizacao: dict | None = None,
    overrides_utilizados: list[dict] | None = None,
    verbas: list[dict] | None = None,
) -> dict:
    """Monta a memória de cálculo a partir de valores já calculados.

    Não recalcula nem altera montantes; apenas reorganiza o resultado
    como fonte única para relatórios (PDF/XLSX).
    """
    return {
        "esquema": ESQUEMA_MEMORIA,
        "codigo": codigo,
        "tipo": tipo,
        "identificacao": {
            "titulo": titulo,
            "processo": processo,
            "parte": parte,
            "app_name": app_name,
            "app_version": app_version,
            "data_geracao": data_geracao.isoformat(),
            "data_base": data_base,
        },
        "criterios": _criterios_de(
            data_base=data_base,
            configuracao=configuracao,
            payload=payload,
            verbas=verbas,
        ),
        "bases": [dict(b) for b in bases],
        "resumo": dict(resumo),
        "parcelas": [_parcela_de_memoria(p) for p in parcelas],
        "verbas": [dict(v) for v in (verbas or [])],
        "avisos": list(avisos),
        "atualizacao": dict(atualizacao) if atualizacao else None,
        "overrides_utilizados": [dict(o) for o in (overrides_utilizados or [])],
    }
