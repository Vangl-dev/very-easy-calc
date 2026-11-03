"""Abatimento de pagamentos na data em que foram feitos (art. 354 do CC).

Cada pagamento é imputado, na sua data, primeiro nos juros vencidos até ali e
depois no principal corrigido, começando pelo valor mais antigo. O principal
que sobra continua sendo corrigido e rendendo juros até a data final.

Os valores são comparados em moeda da data final: o pagamento é corrigido da
sua data até a data final pelo mesmo critério de correção da parcela em que é
imputado. Multa e honorários continuam incidindo sobre o débito apurado sem a
dedução dos pagamentos (a imputação não reduz a base desses encargos).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal

from app.core.competencia import Competencia
from app.core.money import round_brl
from app.engine.bases import BASE_PRINCIPAL, construir_bases
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.correcao import ConfigCorrecao, calcular_correcao
from app.engine.encargos import Pagamento, calcular_encargo
from app.engine.juros import ConfigJuros, ResultadoJuros, TrechoJuros, calcular_juros
from app.engine.parcela import ParcelaInput, ResultadoParcela

CRITERIO_NOMINAL = "nominal"
CRITERIO_DATA_PAGAMENTO = "data_pagamento"
CRITERIOS_PAGAMENTO = (CRITERIO_NOMINAL, CRITERIO_DATA_PAGAMENTO)

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ItemImputacao:
    parcela: int
    razao: Decimal
    juros: Decimal
    principal: Decimal


@dataclass(frozen=True)
class ImputacaoPagamento:
    data: date
    valor: Decimal
    descricao: str
    valor_atualizado: Decimal
    itens: tuple[ItemImputacao, ...]
    credito: Decimal
    """Parte que excedeu principal e juros (valor da data do pagamento)."""
    credito_atualizado: Decimal = ZERO
    """O mesmo excedente levado à data final; abate multa e honorários."""


@dataclass
class _Estado:
    entrada: ParcelaInput
    bruto: ResultadoParcela
    cfg_correcao: ConfigCorrecao
    cfg_juros: ConfigJuros
    inicio_juros: date
    fim_juros: date
    segmentos: list[ResultadoJuros] = field(default_factory=list)
    inicio_segmento: date | None = None
    principal_imputado: Decimal = ZERO
    juros_imputados: Decimal = ZERO

    def __post_init__(self) -> None:
        self.inicio_segmento = self.inicio_juros

    @property
    def corrigido(self) -> Decimal:
        return self.bruto.correcao.valor_corrigido

    def base_juros(self) -> Decimal:
        restante = self.corrigido - self.principal_imputado
        if self.cfg_juros.base == BASE_PRINCIPAL:
            if self.corrigido <= 0:
                return ZERO
            return round_brl(self.entrada.principal * restante / self.corrigido)
        return round_brl(restante)

    def _juros_ate(self, dia: date) -> ResultadoJuros | None:
        fim = min(dia, self.fim_juros)
        if not self.cfg_juros.aplicar or self.inicio_segmento > fim:
            return None
        if self.base_juros() <= 0:
            return None
        return calcular_juros(self.base_juros(), self.inicio_segmento, fim, self.cfg_juros)

    def juros_disponiveis(self, dia: date) -> Decimal:
        pendente = self._juros_ate(dia)
        acumulado = sum((s.juros for s in self.segmentos), ZERO)
        if pendente is not None:
            acumulado += pendente.juros
        return acumulado - self.juros_imputados

    def principal_disponivel(self) -> Decimal:
        return self.corrigido - self.principal_imputado

    def fechar_segmento(self, dia: date) -> None:
        """Encerra o trecho de juros em ``dia``; o próximo usa a nova base."""
        pendente = self._juros_ate(dia)
        if pendente is not None:
            self.segmentos.append(pendente)
        self.inicio_segmento = max(self.inicio_segmento, dia + timedelta(days=1))

    def finalizar(self) -> ResultadoJuros:
        self.fechar_segmento(self.fim_juros)
        bruto = self.bruto.juros
        if not self.segmentos:
            if not bruto.aplicado:
                return bruto
            return replace(bruto, juros=ZERO, trechos=())
        if len(self.segmentos) == 1:
            return self.segmentos[0]
        trechos: list[TrechoJuros] = []
        for segmento in self.segmentos:
            for trecho in segmento.trechos:
                trechos.append(
                    replace(trecho, rotulo=f"{trecho.rotulo} — base {formatar_brl(segmento.base)}")
                )
        return replace(
            self.segmentos[0],
            incidencia=f"{bruto.incidencia}, reduzida pelos pagamentos imputados no principal",
            juros=sum((t.valor for t in trechos), ZERO),
            trechos=tuple(trechos),
        )


def formatar_brl(valor: Decimal) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _razao_correcao(
    cfg: ConfigCorrecao, dia: date, data_base: date
) -> Decimal:
    """Fator que leva um valor de ``dia`` até a data final, pelo critério da parcela."""
    if not cfg.aplicar:
        return Decimal(1)
    inicio = Competencia(dia.year, dia.month)
    if cfg.segmentos:
        segmentos = tuple(
            replace(s, termo_inicial=max(s.termo_inicial, inicio))
            for s in cfg.segmentos
            if s.termo_final >= inicio
        )
        if not segmentos:
            return Decimal(1)
        ajustada = replace(cfg, segmentos=segmentos)
    else:
        if cfg.termo_inicial is not None and inicio < cfg.termo_inicial:
            inicio = cfg.termo_inicial
        ajustada = replace(cfg, termo_inicial=inicio)
    resultado = calcular_correcao(ZERO, ajustada, vencimento=dia, data_base=data_base)
    return resultado.razao if resultado.razao is not None else Decimal(1)


def _recompor(estado: _Estado, configuracao: ConfiguracaoCalculo) -> ResultadoParcela:
    bruto = estado.bruto
    juros = estado.finalizar()
    entrada = estado.entrada
    bases = construir_bases(entrada.principal, bruto.correcao.correcao, juros.juros)
    multa = calcular_encargo(entrada.multa or configuracao.multa, bases, nome="Multa")
    honorarios = calcular_encargo(
        entrada.honorarios or configuracao.honorarios, bases, nome="Honorários"
    )
    total = round_brl(
        bruto.principal + bruto.correcao.correcao + juros.juros + multa.valor + honorarios.valor
    )
    pago = round_brl(estado.juros_imputados + estado.principal_imputado)
    return replace(
        bruto,
        juros=juros,
        multa=multa,
        honorarios=honorarios,
        total=total,
        total_pago=pago,
        saldo=round_brl(total - pago),
    )


def imputar_pagamentos(
    configuracao: ConfiguracaoCalculo,
    entradas: list[ParcelaInput],
    brutos: tuple[ResultadoParcela, ...],
) -> tuple[tuple[ResultadoParcela, ...], tuple[ImputacaoPagamento, ...]]:
    """Recalcula as parcelas abatendo cada pagamento na sua data.

    ``brutos`` são os resultados calculados sem pagamentos. Parcelas fora do
    total da execução não recebem imputação.
    """
    estados: dict[int, _Estado] = {}
    for entrada, bruto in zip(entradas, brutos, strict=True):
        cfg_juros = entrada.juros or configuracao.juros
        estados[entrada.numero] = _Estado(
            entrada=entrada,
            bruto=bruto,
            cfg_correcao=entrada.correcao or configuracao.correcao,
            cfg_juros=cfg_juros,
            inicio_juros=cfg_juros.inicio or entrada.vencimento,
            fim_juros=cfg_juros.fim or configuracao.data_base,
        )

    pagamentos: list[Pagamento] = sorted(
        (p for entrada in entradas for p in entrada.pagamentos),
        key=lambda p: p.data,
    )
    somaveis = sorted(
        (estados[e.numero] for e in entradas if e.entra_no_total),
        key=lambda s: (s.entrada.vencimento, s.entrada.numero),
    )

    imputacoes: list[ImputacaoPagamento] = []
    for pagamento in pagamentos:
        dia = pagamento.data
        vencidas = [s for s in somaveis if s.entrada.vencimento <= dia]
        futuras = [s for s in somaveis if s.entrada.vencimento > dia]
        restante = pagamento.valor
        itens: dict[int, list[Decimal]] = {}
        razoes: dict[int, Decimal] = {}

        def razao_de(estado: _Estado) -> Decimal:
            numero = estado.entrada.numero
            if numero not in razoes:
                momento = max(dia, estado.entrada.vencimento)
                razoes[numero] = _razao_correcao(
                    estado.cfg_correcao, momento, configuracao.data_base
                )
            return razoes[numero]

        # 1º os juros vencidos (art. 354 do CC), depois o principal; sempre do
        # valor mais antigo para o mais novo.
        for etapa in ("juros", "principal"):
            for estado in vencidas + futuras:
                if restante <= 0:
                    break
                razao = razao_de(estado)
                if etapa == "juros":
                    disponivel = estado.juros_disponiveis(dia)
                else:
                    disponivel = estado.principal_disponivel()
                if disponivel <= 0:
                    continue
                capacidade = round_brl(disponivel / razao)
                usado = min(restante, capacidade)
                atualizado = disponivel if usado == capacidade else round_brl(usado * razao)
                restante -= usado
                registro = itens.setdefault(estado.entrada.numero, [ZERO, ZERO])
                if etapa == "juros":
                    estado.juros_imputados += atualizado
                    registro[0] += atualizado
                else:
                    estado.fechar_segmento(dia)
                    estado.principal_imputado += atualizado
                    registro[1] += atualizado

        detalhes = tuple(
            ItemImputacao(
                parcela=numero,
                razao=razoes[numero],
                juros=round_brl(valores[0]),
                principal=round_brl(valores[1]),
            )
            for numero, valores in itens.items()
        )
        imputacoes.append(
            ImputacaoPagamento(
                data=dia,
                valor=pagamento.valor,
                descricao=pagamento.descricao,
                valor_atualizado=round_brl(sum((i.juros + i.principal for i in detalhes), ZERO)),
                itens=detalhes,
                credito=round_brl(restante),
                credito_atualizado=(
                    round_brl(restante * razao_de(somaveis[-1])) if restante > 0 and somaveis else ZERO
                ),
            )
        )

    resultados = tuple(
        _recompor(estados[e.numero], configuracao) if e.entra_no_total else estados[e.numero].bruto
        for e in entradas
    )
    return resultados, tuple(imputacoes)
