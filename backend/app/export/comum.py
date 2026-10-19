from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.core.money import percentual_txt, to_decimal
from app.engine.memoria import REGRA_TOTAL_DA_EXECUCAO

__all__ = [
    "brl_memoria",
    "criterio_encargo_efetivo",
    "pagamentos_efetivos",
    "criterios_txt",
    "dec_memoria",
    "ids_verbas_fora_do_total",
    "pct_memoria",
    "regra_parcela_txt",
    "verbas_fora_do_total",
]


def criterio_encargo_efetivo(config: dict | None, parcelas: list[dict], chave: str) -> dict:
    """Completa critérios de memórias legadas a partir do resultado registrado.

    Versões anteriores guardavam apenas a configuração global, embora o Cível
    pudesse aplicar encargo por verba. Não se infere percentual: quando ele não
    consta da memória, a saída apenas declara a cobrança por verba já refletida
    nas parcelas. Isso preserva a matemática e evita o falso “não aplicado”.
    """
    criterio = dict(config or {})
    if criterio.get("aplicar"):
        return criterio
    if any((parcela.get(chave) or {}).get("aplicado") for parcela in parcelas):
        return {"aplicar": True, "por_verba": True, "variado_por_verba": True}
    return criterio


def pagamentos_efetivos(criterios: dict, parcelas: list[dict]) -> list[dict]:
    """Usa a lista da memória; em versões legadas, os pagamentos das parcelas."""
    declarados = criterios.get("pagamentos_informados") or []
    if declarados:
        return [dict(pagamento) for pagamento in declarados]
    return [
        dict(pagamento)
        for parcela in parcelas
        for pagamento in (parcela.get("pagamentos") or [])
    ]


def verbas_fora_do_total(verbas: list[dict]) -> list[dict]:
    """Verbas que não compõem o total da execução.

    Fonte única: o campo explícito ``entra_no_total``. Memórias antigas, sem o
    campo, seguem o padrão histórico (a verba usada como base por outra fica
    fora do total) para não alterar relatórios de cálculos já salvos.
    """
    referenciadas = {
        v.get("base_verba_id") for v in verbas if v.get("base_verba_id")
    }
    fora: list[dict] = []
    for verba in verbas:
        if "entra_no_total" in verba and verba.get("entra_no_total") is not None:
            if not verba.get("entra_no_total"):
                fora.append(verba)
        elif verba.get("id") in referenciadas:
            fora.append(verba)
    return fora


def ids_verbas_fora_do_total(verbas: list[dict]) -> set:
    return {v.get("id") for v in verbas_fora_do_total(verbas)}


def dec_memoria(valor: object | None) -> Decimal | None:
    """Converte valor serializado na memória para Decimal sem recalcular."""
    if valor is None or valor == "":
        return None
    try:
        return to_decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return None


def brl_memoria(valor: object | None) -> str:
    d = dec_memoria(valor)
    if d is None:
        return ""
    texto = f"{d:.2f}"
    inteiro, centavos = texto.split(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"


def pct_memoria(valor: object | None) -> str:
    """Percentual fracionado (0.85) exibido como porcentagem (85%)."""
    d = dec_memoria(valor)
    if d is None:
        return ""
    return percentual_txt(d)


def critério_encargo_txt(config: dict | None) -> str:
    if not config or not config.get("aplicar"):
        return "não aplicado"
    sufixo = " — configurado por verba" if config.get("por_verba") else ""
    if config.get("variado_por_verba"):
        return f"aplicado{sufixo}; critérios distintos por verba"
    if config.get("percentual") is not None:
        return f"{pct_memoria(config.get('percentual'))} sobre {config.get('base', 'corrigido')}{sufixo}"
    if config.get("valor_fixo") is not None:
        return f"{brl_memoria(config.get('valor_fixo'))} ({config.get('base', 'corrigido')}){sufixo}"
    return f"aplicado{sufixo}"


def criterios_txt(criterios: dict) -> list[tuple[str, str]]:
    correcao = criterios.get("correcao") or {}
    juros = criterios.get("juros") or {}
    multa = criterios.get("multa") or {}
    honorarios = criterios.get("honorarios") or {}
    alimentos = criterios.get("alimentos")
    verbas = criterios.get("verbas") or []
    correcao_por_verba = any(v.get("inicio_correcao") for v in verbas)
    juros_por_verba = any(v.get("inicio_juros") for v in verbas)
    linhas: list[tuple[str, str]] = [
        ("Data-base", criterios.get("data_base") or ""),
        (
            "Correção monetária",
            (
                f"sim — {correcao.get('indexador')}"
                if correcao.get("aplicar")
                else "sim — configurada por verba"
                if correcao_por_verba
                else "não aplicada"
            ),
        ),
        (
            "Juros",
            (
                f"sim — {juros.get('modalidade')}"
                if juros.get("aplicar")
                else "sim — configurada por verba"
                if juros_por_verba
                else "não aplicados"
            ),
        ),
        ("Multa", critério_encargo_txt(multa)),
        ("Honorários", critério_encargo_txt(honorarios)),
    ]
    if verbas:
        linhas.append(
            (
                "Verbas",
                f"{len(verbas)} rubrica(s) — correção e juros com datas próprias",
            )
        )
        fora = verbas_fora_do_total(verbas)
        if fora:
            nomes = ", ".join(str(v.get("nome") or v.get("id") or "—") for v in fora)
            linhas.append(
                (
                    "Total da execução",
                    f"não compõem o total: {nomes}. {REGRA_TOTAL_DA_EXECUCAO}",
                )
            )
        else:
            linhas.append(("Total da execução", REGRA_TOTAL_DA_EXECUCAO))
    if alimentos:
        regras = alimentos.get("regras") or []
        partes = []
        for regra in regras:
            if regra.get("tipo") == "salario_minimo":
                partes.append(
                    f"{regra.get('inicio')}–{regra.get('fim') or '...'}: "
                    f"{pct_memoria(regra.get('percentual'))} do salário mínimo"
                )
            else:
                partes.append(
                    f"{regra.get('inicio')}–{regra.get('fim') or '...'}: "
                    f"{brl_memoria(regra.get('valor'))} (fixo)"
                )
        linhas.append(("Regras de alimentos", "; ".join(partes) if partes else "—"))
        linhas.append(("Período até", str(alimentos.get("ate") or "")))
        linhas.append(
            ("Dia de vencimento", str(alimentos.get("dia_vencimento") or ""))
        )
    pagamentos = criterios.get("pagamentos_informados") or []
    linhas.append(("Pagamentos informados", str(len(pagamentos))))
    return linhas


def bases_txt(bases: list[dict]) -> list[tuple[str, str]]:
    linhas = []
    for base in bases:
        linhas.append(
            (
                base.get("key", ""),
                f"{base.get('versao', '')} — {base.get('nome', '')} "
                f"({base.get('fonte', '')}); papel: {base.get('papel', '')}; "
                f"cobertura: {base.get('cobertura', '')}",
            )
        )
    return linhas


def regra_parcela_txt(parcela: dict) -> str:
    regra = parcela.get("regra")
    if not regra:
        return ""
    partes = [regra.get("detalhe") or regra.get("origem") or ""]
    sm = regra.get("salario_minimo")
    if sm is not None:
        partes.append(f"SM {brl_memoria(sm)}")
    pct = regra.get("percentual")
    if pct is not None:
        partes.append(pct_memoria(pct))
    return " | ".join(p for p in partes if p)
