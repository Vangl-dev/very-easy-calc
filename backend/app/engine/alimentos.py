from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import brl, percentual_txt, round_brl, to_decimal
from app.indexers import obter
from app.indexers.salario_minimo import KEY as SalarioKey

TIPO_SALARIO_MINIMO = "salario_minimo"
TIPO_FIXO = "fixo"
TIPOS = (TIPO_SALARIO_MINIMO, TIPO_FIXO)

DIA_VENCIMENTO_PADRAO = 10


@dataclass(frozen=True)
class RegraAlimento:
    inicio: Competencia
    fim: Competencia | None
    tipo: str
    percentual: Decimal | None = None
    valor: Decimal | None = None
    descricao: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "inicio", Competencia.parse(self.inicio))
        if self.fim is not None:
            object.__setattr__(self, "fim", Competencia.parse(self.fim))
            if self.fim < self.inicio:
                raise ValueError(
                    f"bloco de alimentos com fim ({self.fim.label}) anterior ao início "
                    f"({self.inicio.label})"
                )
        if self.tipo not in TIPOS:
            raise ValueError(f"tipo de regra de alimentos inválido: {self.tipo!r}")
        if self.tipo == TIPO_SALARIO_MINIMO:
            if self.percentual is None:
                raise ValueError("regra de salário mínimo exige percentual")
            percentual = to_decimal(self.percentual)
            if percentual <= 0:
                raise ValueError("o percentual do salário mínimo deve ser maior que zero")
            object.__setattr__(self, "percentual", percentual)
        else:
            if self.valor is None:
                raise ValueError("regra de valor fixo exige valor")
            valor = round_brl(to_decimal(self.valor))
            if valor <= 0:
                raise ValueError("o valor fixo deve ser maior que zero")
            object.__setattr__(self, "valor", valor)

    @property
    def ultimo(self) -> Competencia | None:
        return self.fim

    def descreve(self) -> str:
        if self.descricao:
            return self.descricao
        if self.tipo == TIPO_SALARIO_MINIMO:
            return f"{percentual_txt(self.percentual)} do salário mínimo"
        return f"valor fixo de {self.valor}"


@dataclass(frozen=True)
class Parcela:
    numero: int
    competencia: Competencia
    vencimento: date
    principal: Decimal
    origem: str
    detalhe: str


def _dia_util_do_mes(ano: int, mes: int, dia: int) -> date:
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def _validar_blocos(regras: tuple[RegraAlimento, ...]) -> None:
    if not regras:
        raise ValueError("informe ao menos um bloco de regras de alimentos")
    ordenadas = sorted(regras, key=lambda r: r.inicio)
    if tuple(ordenadas) != tuple(regras):
        raise ValueError("os blocos de alimentos devem estar ordenados pelo início")
    for atual, proximo in zip(regras, regras[1:], strict=False):
        if atual.fim is None:
            raise ValueError(
                f"o bloco {atual.inicio.label} não tem fim e sobrepõe os blocos seguintes"
            )
        esperado = atual.fim.proxima
        if proximo.inicio < esperado:
            raise ValueError(
                f"sobreposição entre o bloco que termina em {atual.fim.label} e o bloco "
                f"que começa em {proximo.inicio.label}"
            )
        if proximo.inicio > esperado:
            raise ValueError(
                f"lacuna entre {atual.fim.label} e {proximo.inicio.label} "
                "nos blocos de alimentos"
            )


def gerar_parcelas(
    regras: tuple[RegraAlimento, ...] | list[RegraAlimento],
    *,
    ate: Competencia | object,
    dia_vencimento: int = DIA_VENCIMENTO_PADRAO,
) -> list[Parcela]:
    blocos = tuple(regras)
    _validar_blocos(blocos)
    if not 1 <= dia_vencimento <= 31:
        raise ValueError(f"dia de vencimento inválido: {dia_vencimento}")

    fim = Competencia.parse(ate)
    inicio = blocos[0].inicio
    if fim < inicio:
        raise ValueError(
            f"período final ({fim.label}) anterior ao início do primeiro bloco ({inicio.label})"
        )

    indexador = obter(SalarioKey)
    parcelas: list[Parcela] = []
    competencia = inicio
    numero = 1
    while competencia <= fim:
        bloco = next(
            (
                r
                for r in blocos
                if r.inicio <= competencia and (r.fim is None or competencia <= r.fim)
            ),
            None,
        )
        if bloco is None:
            raise ValueError(f"nenhum bloco de alimentos cobre a competência {competencia.label}")
        vencimento = _dia_util_do_mes(competencia.year, competencia.month, dia_vencimento)
        if bloco.tipo == TIPO_SALARIO_MINIMO:
            salario = indexador.salario(competencia)
            principal = round_brl(salario * bloco.percentual)
            detalhe = f"{percentual_txt(bloco.percentual)} × {brl(salario)}"
        else:
            principal = bloco.valor
            detalhe = "valor fixo"
        parcelas.append(
            Parcela(
                numero=numero,
                competencia=competencia,
                vencimento=vencimento,
                principal=principal,
                origem=bloco.descreve(),
                detalhe=detalhe,
            )
        )
        numero += 1
        competencia = competencia.proxima

    return parcelas
