from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import round_brl, to_decimal
from app.engine.bases import construir_bases
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.correcao import ConfigCorrecao, ResultadoCorrecao, calcular_correcao
from app.engine.encargos import (
    ConfigEncargo,
    Pagamento,
    ResultadoEncargo,
    calcular_encargo,
    total_pagamentos,
)
from app.engine.juros import ConfigJuros, ResultadoJuros, calcular_juros


@dataclass(frozen=True)
class ParcelaInput:
    numero: int
    vencimento: date
    principal: object
    competencia: Competencia | None = None
    correcao: ConfigCorrecao | None = None
    juros: ConfigJuros | None = None
    multa: ConfigEncargo | None = None
    honorarios: ConfigEncargo | None = None
    pagamentos: tuple[Pagamento, ...] = ()
    descricao: str = ""
    indexadores: tuple[str, ...] = ()
    entra_no_total: bool = True
    """Compõe o total da execução (verba não meramente referencial)."""

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise ValueError(f"número de parcela inválido: {self.numero}")
        if isinstance(self.vencimento, str):
            object.__setattr__(self, "vencimento", date.fromisoformat(self.vencimento))
        if self.competencia is None:
            object.__setattr__(
                self, "competencia", Competencia(self.vencimento.year, self.vencimento.month)
            )
        object.__setattr__(self, "principal", round_brl(to_decimal(self.principal)))
        if self.principal < 0:
            raise ValueError(f"parcela {self.numero}: principal negativo")


@dataclass(frozen=True)
class ResultadoParcela:
    numero: int
    competencia: Competencia
    vencimento: date
    descricao: str
    principal: Decimal
    correcao: ResultadoCorrecao
    juros: ResultadoJuros
    multa: ResultadoEncargo
    honorarios: ResultadoEncargo
    pagamentos: tuple[Pagamento, ...]
    total: Decimal
    total_pago: Decimal
    saldo: Decimal

    @property
    def adicional(self) -> Decimal:
        return self.total - self.principal


def calcular_parcela(
    parcela: ParcelaInput,
    *,
    configuracao: ConfiguracaoCalculo,
) -> ResultadoParcela:
    cfg_correcao = parcela.correcao or configuracao.correcao
    cfg_juros = parcela.juros or configuracao.juros
    cfg_multa = parcela.multa or configuracao.multa
    cfg_honorarios = parcela.honorarios or configuracao.honorarios

    correcao = calcular_correcao(
        parcela.principal,
        cfg_correcao,
        vencimento=parcela.vencimento,
        data_base=configuracao.data_base,
    )

    bases_sem_juros = construir_bases(parcela.principal, correcao.correcao, Decimal("0.00"))
    inicio_juros = cfg_juros.inicio or parcela.vencimento
    fim_juros = cfg_juros.fim or configuracao.data_base
    juros = calcular_juros(
        bases_sem_juros.valor(cfg_juros.base),
        inicio_juros,
        fim_juros,
        cfg_juros,
        base_rotulo=None,
    )

    bases = construir_bases(parcela.principal, correcao.correcao, juros.juros)
    multa = calcular_encargo(cfg_multa, bases, nome="Multa")
    honorarios = calcular_encargo(cfg_honorarios, bases, nome="Honorários")

    total = round_brl(
        parcela.principal
        + correcao.correcao
        + juros.juros
        + multa.valor
        + honorarios.valor
    )
    pago = total_pagamentos(parcela.pagamentos)
    saldo = round_brl(total - pago)

    return ResultadoParcela(
        numero=parcela.numero,
        competencia=parcela.competencia,
        vencimento=parcela.vencimento,
        descricao=parcela.descricao,
        principal=parcela.principal,
        correcao=correcao,
        juros=juros,
        multa=multa,
        honorarios=honorarios,
        pagamentos=tuple(parcela.pagamentos),
        total=total,
        total_pago=pago,
        saldo=saldo,
    )
