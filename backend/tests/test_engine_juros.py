from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.engine.juros import (
    MODALIDADE_FIXA,
    MODALIDADE_NAO_APLICAR,
    MODALIDADE_TAXA_LEGAL,
    REGRA_CC1916,
    ConfigJuros,
    RegraJuros,
    calcular_juros,
)
from app.indexers import CoverageError

D = Decimal


def test_periodo_inteiro_2010_usa_cc2002() -> None:
    r = calcular_juros("1000", "2010-01-01", "2010-12-31")
    assert r.aplicado is True
    assert len(r.trechos) == 1
    assert r.trechos[0].rotulo == "CC/2002 + CTN: 12% a.a."
    assert r.trechos[0].dias == 365
    assert r.juros == D("120.00")


def test_periodo_ante_2003_usa_cc1916() -> None:
    r = calcular_juros("1000", "2000-01-01", "2000-12-31")
    assert len(r.trechos) == 1
    assert r.trechos[0].rotulo == "Código Civil 1916: 6% a.a."
    assert r.trechos[0].dias == 366
    esperado = (D(1000) * D("0.06") * D(366) / D(365)).quantize(D("0.01"))
    assert r.juros == esperado == D("60.16")


def test_periodo_cruza_corte_de_2003() -> None:
    r = calcular_juros("1000", "2003-01-01", "2003-12-31")
    assert len(r.trechos) == 2
    assert r.trechos[0].inicio == date(2003, 1, 1)
    assert r.trechos[0].fim == date(2003, 1, 11)
    assert r.trechos[0].dias == 11
    assert r.trechos[1].inicio == date(2003, 1, 12)
    assert r.trechos[1].fim == date(2003, 12, 31)
    assert r.trechos[1].dias == 354
    total = sum((t.valor for t in r.trechos), D("0.00"))
    assert r.juros == total


def test_periodo_tres_eras_completo() -> None:
    r = calcular_juros("1000", "2000-01-01", "2026-09-30")
    assert len(r.trechos) == 3
    assert r.indexador == "taxa_legal"
    assert r.indexador_versao == "2026.09"
    assert r.indexador_fonte == "Banco Central do Brasil"
    assert r.juros == sum((t.valor for t in r.trechos), D("0.00"))


def test_taxa_legal_dia_a_dia_mensal() -> None:
    r = calcular_juros(
        "1000",
        "2024-08-30",
        "2024-09-30",
        ConfigJuros(
            regras=(
                RegraJuros(
                    rotulo="Taxa Legal",
                    inicio=date(2024, 1, 1),
                    fim=None,
                    tipo="taxa_legal",
                ),
            )
        ),
    )
    agosto = D(1000) * D("0.00605306") * (D(2) / D(31))
    setembro = D(1000) * D("0.00676227") * (D(30) / D(30))
    esperado = (agosto + setembro).quantize(D("0.01"))
    assert r.juros == esperado
    assert len(r.trechos) == 1
    assert r.trechos[0].dias == 32


def test_taxa_legal_fora_da_cobertura_gera_erro_explicito() -> None:
    with pytest.raises(CoverageError) as exc:
        calcular_juros(
            "1000",
            "2026-09-01",
            "2026-10-31",
            ConfigJuros(
                regras=(
                    RegraJuros(
                        rotulo="Taxa Legal",
                        inicio=date(2024, 1, 1),
                        fim=None,
                        tipo="taxa_legal",
                    ),
                )
            ),
        )
    assert "10/2026" in str(exc.value)
    assert "09/2026" in str(exc.value)


def test_nao_aplicar_e_explicito() -> None:
    r = calcular_juros("1000", "2020-01-01", "2021-01-01", ConfigJuros(aplicar=False))
    assert r.aplicado is False
    assert r.juros == D("0.00")
    assert "explícito" in r.motivo

    r2 = calcular_juros(
        "1000", "2020-01-01", "2021-01-01", ConfigJuros(modalidade=MODALIDADE_NAO_APLICAR)
    )
    assert r2.aplicado is False


def test_modalidade_fixa_mensal() -> None:
    r = calcular_juros(
        "1000",
        "2026-01-01",
        "2026-01-31",
        ConfigJuros(modalidade=MODALIDADE_FIXA, taxa=D("0.01"), unidade="mensal"),
    )
    assert r.juros == D("10.00")
    assert len(r.trechos) == 1
    assert "1%" in r.trechos[0].rotulo
    assert r.indexador is None


def test_modalidade_fixa_mensal_proporcional_aos_dias() -> None:
    r = calcular_juros(
        "1000",
        "2026-01-16",
        "2026-01-31",
        ConfigJuros(modalidade=MODALIDADE_FIXA, taxa=D("0.01"), unidade="mensal"),
    )
    assert r.juros == D("5.16")
    assert r.trechos[0].dias == 16


def test_modalidade_fixa_anual() -> None:
    r = calcular_juros(
        "1000",
        "2026-01-01",
        "2026-12-31",
        ConfigJuros(modalidade=MODALIDADE_FIXA, taxa=D("0.12"), unidade="anual"),
    )
    assert r.juros == D("120.00")
    assert "a.a." in r.trechos[0].rotulo


def test_config_invalida() -> None:
    with pytest.raises(ValueError):
        ConfigJuros(modalidade="qualquer")
    with pytest.raises(ValueError):
        ConfigJuros(modalidade=MODALIDADE_FIXA)
    with pytest.raises(ValueError):
        ConfigJuros(modalidade=MODALIDADE_FIXA, taxa=D("-0.01"))
    with pytest.raises(ValueError):
        ConfigJuros(modalidade=MODALIDADE_TAXA_LEGAL, regras=())


def test_datas_invalidas() -> None:
    with pytest.raises(ValueError):
        calcular_juros("1000", "2026-05-01", "2026-01-01")
    with pytest.raises(ValueError):
        calcular_juros("1000", "01/01/2026", "invalida")
    with pytest.raises(ValueError):
        calcular_juros("0", "2026-01-01", "2026-02-01")


def test_regra_com_lacuna_e_rejeitada() -> None:
    com_lacuna = (
        RegraJuros(
            rotulo="só 1916",
            inicio=date(1900, 1, 1),
            fim=date(2003, 1, 11),
            tipo="anual",
            taxa=D("0.06"),
        ),
    )
    with pytest.raises(ValueError) as exc:
        calcular_juros(
            "1000",
            "2003-01-01",
            "2010-12-31",
            ConfigJuros(regras=com_lacuna),
        )
    assert "sem regra" in str(exc.value)


def test_periodo_sem_regra_alguma() -> None:
    with pytest.raises(ValueError):
        calcular_juros(
            "1000",
            "2010-01-01",
            "2010-12-31",
            ConfigJuros(regras=(REGRA_CC1916,)),
        )


def test_incidencia_rotulo_e_registrada() -> None:
    r = calcular_juros(
        "1000",
        "2026-01-01",
        "2026-02-01",
        base_rotulo="principal histórico",
    )
    assert r.incidencia == "principal histórico"
    assert r.base == D("1000.00")
