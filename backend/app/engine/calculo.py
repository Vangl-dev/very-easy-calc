from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.core.money import round_brl
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.juros import (
    MODALIDADE_REGIMES,
    MODALIDADE_TAXA_LEGAL,
    TIPO_SELIC,
    TIPO_SELIC_MENOS_IPCA,
    TIPO_TAXA_LEGAL,
    ConfigJuros,
)
from app.indexers.ipca import KEY as IpcaKey
from app.indexers.selic import KEY as SELIC_KEY
from app.indexers.taxa_legal import KEY as TAXA_LEGAL_KEY
from app.engine.parcela import ParcelaInput, ResultadoParcela, calcular_parcela
from app.indexers import obter

__all__ = [
    "BaseUtilizada",
    "ConfiguracaoCalculo",
    "ResumoCalculo",
    "ResultadoCalculo",
    "calcular",
    "coletar_bases",
]


@dataclass(frozen=True)
class ResumoCalculo:
    qtd_parcelas: int
    periodo_inicio: date | None
    periodo_fim: date | None
    principal: Decimal
    correcao: Decimal
    juros: Decimal
    multa: Decimal
    honorarios: Decimal
    total: Decimal
    pagamentos: Decimal
    saldo: Decimal

    @property
    def adicional(self) -> Decimal:
        return self.total - self.principal


@dataclass(frozen=True)
class BaseUtilizada:
    key: str
    nome: str
    versao: str
    fonte: str
    fonte_url: str
    papel: str
    cobertura: str


@dataclass(frozen=True)
class ResultadoCalculo:
    data_base: date
    parcelas: tuple[ResultadoParcela, ...]
    resumo: ResumoCalculo
    bases: tuple[BaseUtilizada, ...]
    avisos: tuple[str, ...] = ()


def _base_utilizada(key: str, papel: str) -> BaseUtilizada:
    meta = obter(key).metadata
    return BaseUtilizada(
        key=meta.key,
        nome=meta.name,
        versao=meta.version,
        fonte=meta.source,
        fonte_url=meta.source_url,
        papel=papel,
        cobertura=f"{meta.cobertura.inicio.label} a {meta.cobertura.fim.label}",
    )


def _indexadores_de_correcao(config: ConfigCorrecao) -> list[str]:
    if config.segmentos:
        return list(dict.fromkeys(s.indexador for s in config.segmentos))
    return [config.indexador]


def _indexadores_de_juros(config: ConfigJuros) -> list[str]:
    if not config.aplicar:
        return []
    if config.modalidade == MODALIDADE_TAXA_LEGAL:
        return [TAXA_LEGAL_KEY]
    if config.modalidade == MODALIDADE_REGIMES:
        chaves: list[str] = []
        for regra in config.regras:
            if regra.tipo == TIPO_SELIC:
                chaves.append(SELIC_KEY)
            elif regra.tipo == TIPO_SELIC_MENOS_IPCA:
                chaves.append(SELIC_KEY)
                chaves.append(regra.indexador or IpcaKey)
            elif regra.tipo == TIPO_TAXA_LEGAL:
                chaves.append(TAXA_LEGAL_KEY)
        return list(dict.fromkeys(chaves))
    return []


def _registrar_base(
    coletadas: dict[str, BaseUtilizada], key: str, papel: str
) -> None:
    """Acumula papéis quando a mesma base serve correção e juros."""
    base = _base_utilizada(key, papel)
    existente = coletadas.get(key)
    if existente is None:
        coletadas[key] = base
    elif papel not in existente.papel.split(" / "):
        coletadas[key] = replace(existente, papel=f"{existente.papel} / {papel}")


def coletar_bases(
    configuracao: ConfiguracaoCalculo,
    entradas: list[ParcelaInput],
    resultados: tuple[ResultadoParcela, ...],
) -> tuple[BaseUtilizada, ...]:
    coletadas: dict[str, BaseUtilizada] = {}

    for entrada in entradas:
        cfg_correcao = entrada.correcao or configuracao.correcao
        if cfg_correcao.aplicar:
            for key in _indexadores_de_correcao(cfg_correcao):
                _registrar_base(coletadas, key, "Correção monetária")

        for key in _indexadores_de_juros(entrada.juros or configuracao.juros):
            _registrar_base(coletadas, key, "Juros")

        for key in entrada.indexadores:
            if key not in coletadas:
                _registrar_base(coletadas, key, "Composição do principal")

    if not coletadas:
        return ()

    ordem = ["tjsp_tabela_pratica", "selic", "taxa_legal", "salario_minimo"]
    return tuple(
        coletadas[k]
        for k in sorted(coletadas, key=lambda k: (ordem.index(k) if k in ordem else 99, k))
    )


def calcular(
    configuracao: ConfiguracaoCalculo,
    parcelas: list[ParcelaInput] | tuple[ParcelaInput, ...],
) -> ResultadoCalculo:
    entradas = list(parcelas)
    if not entradas:
        raise ValueError("informe ao menos uma parcela")
    numeros = [p.numero for p in entradas]
    if len(numeros) != len(set(numeros)):
        raise ValueError("número de parcela repetido")

    resultados = tuple(calcular_parcela(p, configuracao=configuracao) for p in entradas)

    # Composição no total vem da semântica explícita da verba (entra_no_total).
    # A verba-base continua existindo e alimentando as derivadas; ela entra na
    # soma apenas quando configurada (ou pelo padrão histórico, se ausente).
    somaveis = tuple(
        r
        for r, entrada in zip(resultados, entradas, strict=True)
        if entrada.entra_no_total
    )

    principal = sum((r.principal for r in somaveis), Decimal("0.00"))
    correcao = sum((r.correcao.correcao for r in somaveis), Decimal("0.00"))
    juros = sum((r.juros.juros for r in somaveis), Decimal("0.00"))
    multa = sum((r.multa.valor for r in somaveis), Decimal("0.00"))
    honorarios = sum((r.honorarios.valor for r in somaveis), Decimal("0.00"))
    pagamentos = sum((r.total_pago for r in somaveis), Decimal("0.00"))
    total = round_brl(principal + correcao + juros + multa + honorarios)
    soma_totais = sum((r.total for r in somaveis), Decimal("0.00"))
    saldo = round_brl(total - pagamentos)

    vencimentos = [r.vencimento for r in resultados]
    resumo = ResumoCalculo(
        qtd_parcelas=len(resultados),
        periodo_inicio=min(vencimentos),
        periodo_fim=max(vencimentos),
        principal=round_brl(principal),
        correcao=round_brl(correcao),
        juros=round_brl(juros),
        multa=round_brl(multa),
        honorarios=round_brl(honorarios),
        total=total,
        pagamentos=round_brl(pagamentos),
        saldo=saldo,
    )

    avisos: list[str] = []
    if soma_totais != total:
        avisos.append("divergência entre a soma dos totais das parcelas e o total do cálculo")
    for r in resultados:
        if r.saldo < 0:
            avisos.append(f"parcela {r.numero}: pagamento acima do total ({r.saldo})")

    return ResultadoCalculo(
        data_base=configuracao.data_base,
        parcelas=resultados,
        resumo=resumo,
        bases=coletar_bases(configuracao, entradas, resultados),
        avisos=tuple(avisos),
    )
