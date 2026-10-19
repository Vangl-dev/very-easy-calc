"""Encargos apurados uma vez sobre uma base declarada.

Este módulo deliberadamente recebe os valores já apurados por parcela.  Assim,
ele não altera a matemática histórica das verbas nem deixa PDF/XLSX recalcularem
um encargo.  Referências entre encargos formam um DAG ordenado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.money import round_brl, to_decimal
from app.engine.juros import ConfigJuros, calcular_juros

COMPONENTES = {"principal", "principal_corrigido", "juros_individuais"}
TIPOS = {"multa", "honorarios", "juros"}


@dataclass(frozen=True)
class EncargoConsolidado:
    id: str
    tipo: str
    ordem: int
    verba_ids: tuple[str, ...]
    componentes: tuple[str, ...]
    predecessores: tuple[str, ...]
    percentual: Decimal | None = None
    valor_fixo: Decimal | None = None
    juros: ConfigJuros | None = None
    inicio: date | None = None
    fim: date | None = None
    entra_no_total: bool = True


def calcular_encargos_consolidados(
    encargos: list[EncargoConsolidado], parcelas: list[dict]
) -> list[dict]:
    """Calcula encargos em ordem, sem permitir juros sobre juros implícitos."""
    vistos: dict[str, dict] = {}
    resultado: list[dict] = []
    for encargo in sorted(encargos, key=lambda e: (e.ordem, e.id)):
        if encargo.id in vistos:
            raise ValueError(f"id de encargo consolidado duplicado: '{encargo.id}'")
        if encargo.tipo not in TIPOS:
            raise ValueError(f"tipo de encargo consolidado inválido: '{encargo.tipo}'")
        desconhecidos = set(encargo.componentes) - COMPONENTES
        if desconhecidos:
            raise ValueError(f"componentes de base inválidos: {', '.join(sorted(desconhecidos))}")
        if encargo.tipo == "juros" and "juros_individuais" in encargo.componentes:
            raise ValueError("juros consolidados não podem incidir sobre juros individuais")
        if encargo.tipo == "juros" and encargo.predecessores:
            raise ValueError("juros consolidados não podem incidir sobre outros encargos")
        if not encargo.componentes and encargo.valor_fixo is None:
            raise ValueError("encargo consolidado percentual exige ao menos um componente")

        selecionadas = [
            p for p in parcelas
            if not encargo.verba_ids or (p.get("verba") or {}).get("id") in encargo.verba_ids
        ]
        if encargo.verba_ids and not selecionadas:
            raise ValueError(f"encargo '{encargo.id}': nenhuma verba selecionada")
        if encargo.tipo == "juros":
            # Juros individuais e consolidados no mesmo conjunto seriam dupla
            # incidência, ainda que a base consolidada não liste o componente.
            com_juros_individuais = [
                p.get("numero") for p in selecionadas
                if (p.get("juros") or {}).get("aplicado")
                and to_decimal((p.get("juros") or {}).get("juros") or "0") != 0
            ]
            if com_juros_individuais:
                raise ValueError(
                    "juros consolidados exigem desativar os juros individuais das "
                    f"parcelas selecionadas: {', '.join(map(str, com_juros_individuais))}"
                )
        itens: list[dict] = []
        base = Decimal("0.00")
        for p in selecionadas:
            valores = {
                "principal": p.get("principal"),
                "principal_corrigido": (p.get("correcao") or {}).get("valor_corrigido"),
                "juros_individuais": (p.get("juros") or {}).get("juros"),
            }
            for componente in encargo.componentes:
                valor = round_brl(to_decimal(valores[componente] or "0"))
                base += valor
                itens.append({
                    "verba_id": (p.get("verba") or {}).get("id"),
                    "parcela": p.get("numero"), "componente": componente,
                    "valor": str(valor),
                })
        predecessores: list[dict] = []
        for predecessor_id in encargo.predecessores:
            anterior = vistos.get(predecessor_id)
            if anterior is None:
                raise ValueError(
                    f"encargo '{encargo.id}' referencia predecessor inexistente ou posterior: "
                    f"'{predecessor_id}'"
                )
            if anterior["tipo"] == "juros":
                raise ValueError("encargos não podem usar juros consolidados como base")
            valor = to_decimal(anterior["valor"])
            base += valor
            predecessores.append({"id": predecessor_id, "valor": str(valor)})
        base = round_brl(base)

        if encargo.valor_fixo is not None:
            valor = round_brl(encargo.valor_fixo)
            trechos = []
        elif encargo.tipo == "juros":
            if encargo.juros is None or encargo.inicio is None or encargo.fim is None:
                raise ValueError("juros consolidados exigem configuração, termo inicial e termo final")
            juros = calcular_juros(base, encargo.inicio, encargo.fim, encargo.juros,
                                   base_rotulo="base consolidada")
            valor, trechos = juros.juros, [
                {"inicio": t.inicio.isoformat(), "fim": t.fim.isoformat(), "dias": t.dias,
                 "taxa": None if t.taxa is None else str(t.taxa), "rotulo": t.taxa_rotulo,
                 "valor": str(t.valor)} for t in juros.trechos]
        else:
            if encargo.percentual is None:
                raise ValueError("encargo consolidado exige percentual ou valor fixo")
            valor, trechos = round_brl(base * encargo.percentual), []
        item = {
            "id": encargo.id, "tipo": encargo.tipo, "ordem": encargo.ordem,
            "percentual": None if encargo.percentual is None else str(encargo.percentual),
            "valor_fixo": None if encargo.valor_fixo is None else str(encargo.valor_fixo),
            "base": {"componentes": list(encargo.componentes), "verba_ids": list(encargo.verba_ids),
                     "itens": itens, "predecessores": predecessores, "valor": str(base)},
            "inicio": None if encargo.inicio is None else encargo.inicio.isoformat(),
            "fim": None if encargo.fim is None else encargo.fim.isoformat(),
            "trechos_juros": trechos, "valor": str(round_brl(valor)),
            "arredondamento": "ROUND_HALF_UP, 2 casas, uma vez ao final",
            "entra_no_total": encargo.entra_no_total,
        }
        vistos[encargo.id] = item
        resultado.append(item)
    return resultado
