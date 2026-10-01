from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.money import round_brl, to_decimal

BASE_PRINCIPAL = "principal"
BASE_CORRIGIDO = "corrigido"
BASE_COM_JUROS = "com_juros"
BASES = (BASE_PRINCIPAL, BASE_CORRIGIDO, BASE_COM_JUROS)

ROTULOS_BASE = {
    BASE_PRINCIPAL: "principal histórico",
    BASE_CORRIGIDO: "valor corrigido (principal + correção)",
    BASE_COM_JUROS: "principal + correção + juros",
}


def rotulo_base(nome: str) -> str:
    if nome not in ROTULOS_BASE:
        raise ValueError(f"base de cálculo inválida: {nome!r} (esperado um de {BASES})")
    return ROTULOS_BASE[nome]


@dataclass(frozen=True)
class ValoresBase:
    principal: Decimal
    corrigido: Decimal
    com_juros: Decimal

    def valor(self, nome: str) -> Decimal:
        rotulo_base(nome)
        if nome == BASE_PRINCIPAL:
            return self.principal
        if nome == BASE_CORRIGIDO:
            return self.corrigido
        return self.com_juros


def construir_bases(principal: object, correcao: Decimal, juros: Decimal) -> ValoresBase:
    base = round_brl(to_decimal(principal))
    corrigido = round_brl(base + to_decimal(correcao))
    com_juros = round_brl(corrigido + to_decimal(juros))
    return ValoresBase(principal=base, corrigido=corrigido, com_juros=com_juros)
