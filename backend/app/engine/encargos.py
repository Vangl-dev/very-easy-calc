from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.money import round_brl, to_decimal
from app.engine.bases import ValoresBase, rotulo_base


@dataclass(frozen=True)
class ConfigEncargo:
    aplicar: bool = False
    percentual: Decimal | None = None
    valor_fixo: Decimal | None = None
    base: str = "corrigido"

    def __post_init__(self) -> None:
        rotulo_base(self.base)
        if not self.aplicar:
            return
        if self.percentual is None and self.valor_fixo is None:
            raise ValueError("encargo aplicado exige percentual ou valor fixo")
        if self.percentual is not None and self.valor_fixo is not None:
            raise ValueError("informe percentual ou valor fixo, não ambos")
        if self.percentual is not None and to_decimal(self.percentual) < 0:
            raise ValueError("o percentual do encargo não pode ser negativo")
        if self.valor_fixo is not None and to_decimal(self.valor_fixo) < 0:
            raise ValueError("o valor fixo do encargo não pode ser negativo")


@dataclass(frozen=True)
class ResultadoEncargo:
    aplicado: bool
    motivo: str
    valor: Decimal
    percentual: Decimal | None = None
    base_nome: str | None = None
    base_rotulo: str | None = None
    base_valor: Decimal | None = None


def calcular_encargo(
    config: ConfigEncargo,
    bases: ValoresBase,
    *,
    nome: str,
) -> ResultadoEncargo:
    if not config.aplicar:
        return ResultadoEncargo(
            aplicado=False,
            motivo=f"{nome} não aplicado (parâmetro explícito do usuário).",
            valor=Decimal("0.00"),
        )

    base_valor = bases.valor(config.base)
    if config.valor_fixo is not None:
        valor = round_brl(to_decimal(config.valor_fixo))
        return ResultadoEncargo(
            aplicado=True,
            motivo=f"{nome} aplicado sobre {rotulo_base(config.base)}.",
            valor=valor,
            percentual=None,
            base_nome=config.base,
            base_rotulo=rotulo_base(config.base),
            base_valor=base_valor,
        )

    percentual = to_decimal(config.percentual)
    valor = round_brl(base_valor * percentual)
    return ResultadoEncargo(
        aplicado=True,
        motivo=f"{nome} aplicado sobre {rotulo_base(config.base)}.",
        valor=valor,
        percentual=percentual,
        base_nome=config.base,
        base_rotulo=rotulo_base(config.base),
        base_valor=base_valor,
    )


@dataclass(frozen=True)
class Pagamento:
    data: date
    valor: Decimal
    descricao: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "valor", round_brl(to_decimal(self.valor)))
        if self.valor < 0:
            raise ValueError("o valor do pagamento não pode ser negativo")


def total_pagamentos(pagamentos: tuple[Pagamento, ...] | list[Pagamento]) -> Decimal:
    return sum((p.valor for p in pagamentos), Decimal("0.00"))
