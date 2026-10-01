from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import percentual_txt, round_brl, to_decimal
from app.engine.bases import BASE_CORRIGIDO, rotulo_base
from app.indexers import obter
from app.indexers.taxa_legal import KEY as TaxaLegalKey

MODALIDADE_NAO_APLICAR = "nao_aplicar"
MODALIDADE_TAXA_LEGAL = "taxa_legal"
MODALIDADE_FIXA = "fixa"
MODALIDADES = (MODALIDADE_NAO_APLICAR, MODALIDADE_TAXA_LEGAL, MODALIDADE_FIXA)

UNIDADE_MENSAL = "mensal"
UNIDADE_ANUAL = "anual"
UNIDADES = (UNIDADE_MENSAL, UNIDADE_ANUAL)

TIPO_ANUAL = "anual"
TIPO_MENSAL = "mensal"
TIPO_TAXA_LEGAL = "taxa_legal"


@dataclass(frozen=True)
class RegraJuros:
    rotulo: str
    inicio: date
    fim: date | None
    tipo: str
    taxa: Decimal | None = None

    def cobre(self, data: date) -> bool:
        if data < self.inicio:
            return False
        return self.fim is None or data <= self.fim


REGRA_CC1916 = RegraJuros(
    rotulo="Código Civil 1916: 6% a.a.",
    inicio=date(1900, 1, 1),
    fim=date(2003, 1, 11),
    tipo=TIPO_ANUAL,
    taxa=Decimal("0.06"),
)
REGRA_CC2002 = RegraJuros(
    rotulo="CC/2002 + CTN: 12% a.a.",
    inicio=date(2003, 1, 12),
    fim=date(2024, 8, 29),
    tipo=TIPO_ANUAL,
    taxa=Decimal("0.12"),
)
REGRA_TAXA_LEGAL = RegraJuros(
    rotulo="Taxa Legal, art. 406 do CC",
    inicio=date(2024, 8, 30),
    fim=None,
    tipo=TIPO_TAXA_LEGAL,
)
REGRAS_PADRAO = (REGRA_CC1916, REGRA_CC2002, REGRA_TAXA_LEGAL)


@dataclass(frozen=True)
class ConfigJuros:
    aplicar: bool = True
    modalidade: str = MODALIDADE_TAXA_LEGAL
    taxa: Decimal | None = None
    unidade: str = UNIDADE_MENSAL
    regras: tuple[RegraJuros, ...] = REGRAS_PADRAO
    base: str = BASE_CORRIGIDO
    inicio: date | None = None
    fim: date | None = None

    def __post_init__(self) -> None:
        rotulo_base(self.base)
        if self.modalidade not in MODALIDADES:
            raise ValueError(f"modalidade inválida: {self.modalidade!r}")
        if self.unidade not in UNIDADES:
            raise ValueError(f"unidade inválida: {self.unidade!r}")
        if self.modalidade == MODALIDADE_FIXA:
            if self.taxa is None:
                raise ValueError("modalidade fixa exige taxa")
            if to_decimal(self.taxa) < 0:
                raise ValueError("taxa não pode ser negativa")
        if self.modalidade == MODALIDADE_TAXA_LEGAL and not self.regras:
            raise ValueError("modalidade taxa_legal exige ao menos uma regra de período")
        if self.inicio is not None and isinstance(self.inicio, str):
            object.__setattr__(self, "inicio", _para_data(self.inicio, "início dos juros"))
        if self.fim is not None and isinstance(self.fim, str):
            object.__setattr__(self, "fim", _para_data(self.fim, "fim dos juros"))
        if self.inicio is not None and self.fim is not None and self.inicio > self.fim:
            raise ValueError(
                f"início dos juros ({self.inicio.isoformat()}) posterior ao "
                f"fim ({self.fim.isoformat()})"
            )


@dataclass(frozen=True)
class TrechoJuros:
    rotulo: str
    inicio: date
    fim: date
    dias: int
    taxa: Decimal | None
    taxa_rotulo: str
    valor: Decimal


@dataclass(frozen=True)
class ResultadoJuros:
    aplicado: bool
    motivo: str
    base: Decimal
    incidencia: str
    modalidade: str
    juros: Decimal
    trechos: tuple[TrechoJuros, ...] = ()
    indexador: str | None = None
    indexador_versao: str | None = None
    indexador_fonte: str | None = None


NAO_APLICAR = "Juros não aplicados (parâmetro explícito do usuário)."


def _para_data(valor: object, papel: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, Competencia):
        raise ValueError(f"{papel}: informe uma data completa, não apenas a competência")
    if isinstance(valor, str):
        texto = valor.strip()
        try:
            return date.fromisoformat(texto)
        except ValueError:
            pass
        try:
            partes = [int(p) for p in texto.split("/")]
            if len(partes) == 3:
                dia, mes, ano = partes
                return date(ano, mes, dia)
        except ValueError as exc:
            raise ValueError(f"{papel} inválida: {valor!r}") from exc
        raise ValueError(f"{papel} inválida: {valor!r}")
    raise TypeError(f"{papel}: tipo não suportado ({type(valor).__name__})")


def _dias(inicio: date, fim: date) -> int:
    return (fim - inicio).days + 1


def _proximo_dia(dia: date) -> date:
    return dia + timedelta(days=1)


def _juros_anuais(base: Decimal, inicio: date, fim: date, taxa: Decimal) -> Decimal:
    return base * taxa * (Decimal(_dias(inicio, fim)) / Decimal(365))


def _por_mes(base: Decimal, inicio: date, fim: date, taxa_de) -> Decimal:
    total = Decimal(0)
    cursor = inicio
    while cursor <= fim:
        dias_no_mes = calendar.monthrange(cursor.year, cursor.month)[1]
        fim_mes = date(cursor.year, cursor.month, dias_no_mes)
        limite = min(fim_mes, fim)
        dias = Decimal(_dias(cursor, limite))
        total += base * taxa_de(cursor) * (dias / Decimal(dias_no_mes))
        cursor = _proximo_dia(limite)
    return total


def _taxa_legal_de(dia: date) -> Decimal:
    return obter(TaxaLegalKey).taxa(Competencia(dia.year, dia.month))


def _intervalos_nao_cobertos(inicio: date, fim: date, trechos: list[TrechoJuros]) -> list[str]:
    pedacos = sorted((t.inicio, t.fim) for t in trechos)
    faltando: list[str] = []
    cursor = inicio
    for ini, fim_pedaco in pedacos:
        if ini > cursor:
            faltando.append(f"{cursor.isoformat()} a {(ini - timedelta(days=1)).isoformat()}")
        cursor = max(cursor, fim_pedaco + timedelta(days=1))
    if cursor <= fim:
        faltando.append(f"{cursor.isoformat()} a {fim.isoformat()}")
    return faltando


def _validar_cobertura(inicio: date, fim: date, trechos: list[TrechoJuros]) -> None:
    faltando = _intervalos_nao_cobertos(inicio, fim, trechos)
    if faltando:
        raise ValueError(
            "a configuração de juros não cobre todo o período informado; "
            f"sem regra: {', '.join(faltando)}"
        )


def calcular_juros(
    principal: object,
    data_inicial: object,
    data_final: object,
    config: ConfigJuros | None = None,
    *,
    base_rotulo: str | None = None,
) -> ResultadoJuros:
    cfg = config or ConfigJuros()
    base = round_brl(to_decimal(principal))
    incidencia = base_rotulo or rotulo_base(cfg.base)

    if not cfg.aplicar or cfg.modalidade == MODALIDADE_NAO_APLICAR:
        return ResultadoJuros(
            aplicado=False,
            motivo=NAO_APLICAR,
            base=base,
            incidencia=incidencia,
            modalidade=cfg.modalidade,
            juros=Decimal("0.00"),
        )

    if base <= 0:
        raise ValueError("informe o valor principal para calcular juros")

    inicio = _para_data(data_inicial, "data inicial dos juros")
    fim = _para_data(data_final, "data final dos juros")
    if inicio > fim:
        raise ValueError("a data inicial dos juros deve ser anterior à data final")

    if cfg.modalidade == MODALIDADE_FIXA:
        taxa = to_decimal(cfg.taxa)
        if cfg.unidade == UNIDADE_ANUAL:
            valor = round_brl(_juros_anuais(base, inicio, fim, taxa))
            rotulo = f"{percentual_txt(taxa)} a.a. (simples, {_dias(inicio, fim)} dias / 365)"
        else:
            valor = round_brl(_por_mes(base, inicio, fim, lambda _d: taxa))
            rotulo = f"{percentual_txt(taxa)} ao mês (proporcional aos dias)"
        trecho = TrechoJuros(
            rotulo=rotulo,
            inicio=inicio,
            fim=fim,
            dias=_dias(inicio, fim),
            taxa=taxa,
            taxa_rotulo=percentual_txt(taxa),
            valor=valor,
        )
        return ResultadoJuros(
            aplicado=True,
            motivo="Juros aplicados.",
            base=base,
            incidencia=incidencia,
            modalidade=cfg.modalidade,
            juros=valor,
            trechos=(trecho,),
        )

    trechos: list[TrechoJuros] = []
    usado_taxa_legal = False
    for regra in cfg.regras:
        ini = max(inicio, regra.inicio)
        fim_regra = fim if regra.fim is None else min(fim, regra.fim)
        if ini > fim_regra:
            continue
        dias = _dias(ini, fim_regra)
        if regra.tipo == TIPO_ANUAL:
            taxa = to_decimal(regra.taxa) if regra.taxa is not None else Decimal(0)
            valor = round_brl(_juros_anuais(base, ini, fim_regra, taxa))
            trechos.append(
                TrechoJuros(
                    rotulo=regra.rotulo,
                    inicio=ini,
                    fim=fim_regra,
                    dias=dias,
                    taxa=taxa,
                    taxa_rotulo=f"{percentual_txt(taxa)} a.a.",
                    valor=valor,
                )
            )
        elif regra.tipo == TIPO_MENSAL:
            taxa = to_decimal(regra.taxa) if regra.taxa is not None else Decimal(0)
            valor = round_brl(_por_mes(base, ini, fim_regra, lambda _d: taxa))
            trechos.append(
                TrechoJuros(
                    rotulo=regra.rotulo,
                    inicio=ini,
                    fim=fim_regra,
                    dias=dias,
                    taxa=taxa,
                    taxa_rotulo=f"{percentual_txt(taxa)} ao mês",
                    valor=valor,
                )
            )
        elif regra.tipo == TIPO_TAXA_LEGAL:
            usado_taxa_legal = True
            indexador = obter(TaxaLegalKey)
            valor = round_brl(_por_mes(base, ini, fim_regra, _taxa_legal_de))
            trechos.append(
                TrechoJuros(
                    rotulo=regra.rotulo,
                    inicio=ini,
                    fim=fim_regra,
                    dias=dias,
                    taxa=None,
                    taxa_rotulo=f"Taxa Legal variável — SGS {indexador.metadata.version}",
                    valor=valor,
                )
            )
        else:
            raise ValueError(f"tipo de regra de juros desconhecido: {regra.tipo!r}")

    if not trechos:
        raise ValueError("nenhum período de juros corresponde às datas informadas")

    _validar_cobertura(inicio, fim, trechos)
    indexador_legal = obter(TaxaLegalKey)
    return ResultadoJuros(
        aplicado=True,
        motivo="Juros aplicados.",
        base=base,
        incidencia=incidencia,
        modalidade=cfg.modalidade,
        juros=sum((t.valor for t in trechos), Decimal("0.00")),
        trechos=tuple(trechos),
        indexador=TaxaLegalKey if usado_taxa_legal else None,
        indexador_versao=indexador_legal.metadata.version if usado_taxa_legal else None,
        indexador_fonte=indexador_legal.metadata.source if usado_taxa_legal else None,
    )
