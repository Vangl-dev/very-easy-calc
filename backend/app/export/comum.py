from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.core.money import percentual_txt, to_decimal


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


def rotulo_sim_nao(flag: object) -> str:
    return "Sim" if flag else "Não"


def critério_encargo_txt(config: dict | None) -> str:
    if not config or not config.get("aplicar"):
        return "não aplicado"
    if config.get("percentual") is not None:
        return f"{pct_memoria(config.get('percentual'))} sobre {config.get('base', 'corrigido')}"
    if config.get("valor_fixo") is not None:
        return f"{brl_memoria(config.get('valor_fixo'))} ({config.get('base', 'corrigido')})"
    return "aplicado"


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
