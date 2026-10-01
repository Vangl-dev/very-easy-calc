from datetime import date
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.bases import BASE_PRINCIPAL, BASE_CORRIGIDO
from app.engine.configuracao import ConfiguracaoCalculo
from app.engine.correcao import ConfigCorrecao
from app.engine.encargos import ConfigEncargo, Pagamento
from app.engine.juros import ConfigJuros, MODALIDADE_NAO_APLICAR
from app.engine.parcela import ParcelaInput, calcular_parcela

D = Decimal


def _parcela(**kwargs) -> ParcelaInput:
    dados = {
        "numero": 1,
        "vencimento": date(2021, 1, 10),
        "principal": D("1000.00"),
        "correcao": ConfigCorrecao(aplicar=False),
        "juros": ConfigJuros(aplicar=False),
    }
    dados.update(kwargs)
    return ParcelaInput(**dados)


def _calc(parcela, *, data_base=date(2026, 8, 31), **cfg):
    return calcular_parcela(
        parcela, configuracao=ConfiguracaoCalculo(data_base=data_base, **cfg)
    )


def test_parcela_composta_sem_encargos() -> None:
    r = _calc(_parcela())
    assert r.principal == D("1000.00")
    assert r.correcao.correcao == D("0.00")
    assert r.juros.juros == D("0.00")
    assert r.multa.valor == D("0.00")
    assert r.honorarios.valor == D("0.00")
    assert r.total == D("1000.00")
    assert r.adicional == D("0.00")
    assert r.saldo == D("1000.00")
    assert r.competencia == Competencia(2021, 1)


def test_parcela_com_tudo_aplicado() -> None:
    entrada = _parcela(
        correcao=ConfigCorrecao(
            aplicar=True, indexador="tjsp_tabela_pratica", termo_final=Competencia(2026, 8)
        ),
        juros=ConfigJuros(aplicar=True, modalidade=MODALIDADE_NAO_APLICAR),
        multa=ConfigEncargo(aplicar=True, percentual=D("0.02")),
        honorarios=ConfigEncargo(aplicar=True, percentual=D("0.10"), base=BASE_PRINCIPAL),
    )
    r = _calc(entrada)

    assert r.correcao.aplicado is True
    assert r.correcao.valor_corrigido > r.principal
    assert r.multa.base_nome == BASE_CORRIGIDO
    assert r.multa.valor == (r.correcao.valor_corrigido * D("0.02")).quantize(D("0.01"))
    assert r.honorarios.valor == D("100.00")

    esperado_total = (
        r.principal + r.correcao.correcao + r.juros.juros + r.multa.valor + r.honorarios.valor
    )
    assert r.total == esperado_total.quantize(D("0.01"))
    assert r.adicional == (r.total - r.principal)


def test_pagamentos_abatem_do_saldo() -> None:
    entrada = _parcela(
        multa=ConfigEncargo(aplicar=True, percentual=D("0.02")),
        pagamentos=(
            Pagamento(date(2026, 1, 10), D("500.00"), "depósito"),
            Pagamento(date(2026, 2, 10), D("300.00")),
        ),
    )
    r = _calc(entrada)
    assert r.total == D("1020.00")
    assert r.total_pago == D("800.00")
    assert r.saldo == D("220.00")


def test_juros_incidem_sobre_principal_quando_configurado() -> None:
    entrada = _parcela(
        juros=ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_NAO_APLICAR,
            base=BASE_PRINCIPAL,
        ),
        correcao=ConfigCorrecao(
            aplicar=True, indexador="tjsp_tabela_pratica", termo_final=Competencia(2026, 8)
        ),
    )
    r = _calc(entrada)
    assert r.juros.incidencia == "principal histórico"


def test_parcela_rejeita_principal_negativo() -> None:
    with pytest.raises(ValueError, match="negativo"):
        _parcela(principal=D("-1"))


def test_competencia_derivada_do_vencimento() -> None:
    r = _calc(_parcela(vencimento=date(2024, 7, 10)))
    assert r.competencia == Competencia(2024, 7)


def test_vencimento_em_texto_e_aceito() -> None:
    r = _calc(_parcela(vencimento="2024-07-10"))
    assert r.vencimento == date(2024, 7, 10)


def test_fallback_da_configuracao_geral() -> None:
    cfg = ConfiguracaoCalculo(
        data_base=date(2026, 8, 31),
        correcao=ConfigCorrecao(aplicar=False),
        juros=ConfigJuros(aplicar=False),
        multa=ConfigEncargo(aplicar=True, percentual=D("0.02")),
        honorarios=ConfigEncargo(aplicar=True, percentual=D("0.10"), base=BASE_PRINCIPAL),
    )
    r = calcular_parcela(_parcela(multa=None, honorarios=None), configuracao=cfg)
    assert r.multa.valor == D("20.00")
    assert r.multa.base_nome == BASE_CORRIGIDO
    assert r.honorarios.valor == D("100.00")
    assert r.total == D("1120.00")


def test_sobreposicao_da_parcela_sobre_a_configuracao() -> None:
    cfg = ConfiguracaoCalculo(
        data_base=date(2026, 8, 31),
        correcao=ConfigCorrecao(aplicar=False),
        juros=ConfigJuros(aplicar=False),
        multa=ConfigEncargo(aplicar=True, percentual=D("0.02")),
        honorarios=ConfigEncargo(aplicar=True, percentual=D("0.10"), base=BASE_PRINCIPAL),
    )
    r = calcular_parcela(
        _parcela(multa=ConfigEncargo(aplicar=False)),
        configuracao=cfg,
    )
    assert r.multa.aplicado is False
    assert r.multa.valor == D("0.00")
    assert r.honorarios.valor == D("100.00")
    assert r.total == D("1100.00")
