from __future__ import annotations

from datetime import datetime

# 1.4: `diferenca` por parcela. 1.5: composição auditável do total
# (`verbas[].entra_no_total` e `criterios.total_da_execucao`).
ESQUEMA_MEMORIA = "memoria-calculo/1.6"

__all__ = ["ESQUEMA_MEMORIA", "REGRA_TOTAL_DA_EXECUCAO", "montar_memoria"]

REGRA_TOTAL_DA_EXECUCAO = (
    "O total da execução soma somente as verbas que compõem o total. Usar uma "
    "verba como base de cálculo de outra não muda essa marcação: a composição "
    "é decisão explícita da própria verba. Em cálculos antigos, sem a marcação, "
    "vale o padrão histórico — a verba usada como base fica fora do total."
)


def _critério_encargo(config: dict | None) -> dict:
    if config is None:
        return {"aplicar": False}
    return {
        "aplicar": bool(config.get("aplicar", False)),
        "percentual": config.get("percentual"),
        "valor_fixo": config.get("valor_fixo"),
        "base": config.get("base", "corrigido"),
    }


def _verbas_para_criterios(verbas: list[dict] | None) -> list[dict]:
    return [
        {
            "id": v.get("id"),
            "nome": v.get("nome"),
            "tipo": v.get("tipo", "valor"),
            "valor": v.get("valor"),
            "base_verba_id": v.get("base_verba_id"),
            "percentual": v.get("percentual"),
            "entra_no_total": v.get("entra_no_total"),
            "data_base": v.get("data_base"),
            "inicio_correcao": v.get("inicio_correcao"),
            "inicio_juros": v.get("inicio_juros"),
            "regimes": list(v.get("regimes") or []),
            "regime_temporal": v.get("regime_temporal"),
            "multa": dict(v.get("multa") or {}),
            "honorarios": dict(v.get("honorarios") or {}),
        }
        for v in (verbas or [])
    ]


def _criterio_encargo_efetivo(configuracao: dict | None, verbas: list[dict] | None, chave: str) -> dict:
    """Critério global ou, no Cível, o critério efetivo configurado por verba.

    A escolha não altera valores: apenas torna a memória fiel ao payload que
    originou parcelas já calculadas. Quando as verbas divergem, não inventamos
    um percentual único; o relatório declara expressamente a configuração por
    verba.
    """
    global_ = _critério_encargo(configuracao)
    if global_.get("aplicar"):
        return global_
    aplicados = [
        _critério_encargo(v.get(chave))
        for v in (verbas or [])
        if (v.get(chave) or {}).get("aplicar")
    ]
    if not aplicados:
        return global_
    unicos = {
        (c.get("percentual"), c.get("valor_fixo"), c.get("base"))
        for c in aplicados
    }
    criterio = dict(aplicados[0])
    criterio["por_verba"] = True
    if len(unicos) > 1:
        criterio["variado_por_verba"] = True
        criterio["percentual"] = None
        criterio["valor_fixo"] = None
    return criterio


def _pagamentos_efetivos(parcelas: list[dict] | None) -> list[dict]:
    """Lançamentos efetivamente levados ao motor, sem duplicar o payload."""
    return [
        dict(pagamento)
        for parcela in (parcelas or [])
        for pagamento in (parcela.get("pagamentos") or [])
    ]


def _total_da_execucao(verbas: list[dict] | None) -> dict | None:
    """Regra aplicada à soma do total, auditável na memória e nos relatórios."""
    lista = list(verbas or [])
    if not lista:
        return None
    fora = [
        {"id": v.get("id"), "nome": v.get("nome")}
        for v in lista
        if v.get("entra_no_total") is False
    ]
    return {
        "regra": REGRA_TOTAL_DA_EXECUCAO,
        "verbas_fora_do_total": fora,
    }


def _criterios_de(
    *,
    data_base: str,
    configuracao: dict,
    payload: dict,
    verbas: list[dict] | None = None,
    parcelas: list[dict] | None = None,
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
        "multa": _criterio_encargo_efetivo(configuracao.get("multa"), verbas, "multa"),
        "honorarios": _criterio_encargo_efetivo(configuracao.get("honorarios"), verbas, "honorarios"),
        "alimentos": None
        if alimentos is None
        else {
            "regras": list(alimentos.get("regras") or []),
            "ate": alimentos.get("ate"),
            "dia_vencimento": alimentos.get("dia_vencimento"),
        },
        "verbas": _verbas_para_criterios(verbas),
        "total_da_execucao": _total_da_execucao(verbas),
        "pagamentos_informados": _pagamentos_efetivos(parcelas)
        or list(payload.get("pagamentos") or []),
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
    encargos_consolidados: list[dict] | None = None,
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
            parcelas=parcelas,
        ),
        "bases": [dict(b) for b in bases],
        "resumo": dict(resumo),
        "parcelas": [_parcela_de_memoria(p) for p in parcelas],
        "verbas": [dict(v) for v in (verbas or [])],
        "encargos_consolidados": [dict(e) for e in (encargos_consolidados or [])],
        "avisos": list(avisos),
        "atualizacao": dict(atualizacao) if atualizacao else None,
        "overrides_utilizados": [dict(o) for o in (overrides_utilizados or [])],
    }
