from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.alimentos import (
    TIPO_FIXO,
    TIPO_SALARIO_MINIMO,
    RegraAlimento,
    gerar_parcelas,
)
from app.indexers import CoverageError

D = Decimal


def _bloco(inicio: str, fim: str | None, tipo: str, **kwargs) -> RegraAlimento:
    return RegraAlimento(
        inicio=Competencia.parse(inicio),
        fim=Competencia.parse(fim) if fim else None,
        tipo=tipo,
        **kwargs,
    )


def test_trinta_por_cento_do_salario_minimo_2021() -> None:
    parcelas = gerar_parcelas(
        [_bloco("01/2021", "12/2021", TIPO_SALARIO_MINIMO, percentual=D("0.30"))],
        ate="12/2021",
    )
    assert len(parcelas) == 12
    assert parcelas[0].competencia == Competencia(2021, 1)
    assert parcelas[0].principal == D("330.00")
    assert parcelas[0].detalhe == "30% × R$ 1.100,00"
    assert parcelas[0].vencimento == date(2021, 1, 10)
    assert all(p.principal == D("330.00") for p in parcelas)
    assert parcelas[-1].numero == 12


def test_periodo_longo_com_mudanca_de_salario() -> None:
    parcelas = gerar_parcelas(
        [_bloco("01/2024", "12/2025", TIPO_SALARIO_MINIMO, percentual=D("0.50"))],
        ate="12/2025",
    )
    assert len(parcelas) == 24
    assert parcelas[0].principal == D("706.00")
    assert parcelas[12].principal == D("759.00")
    assert parcelas[12].detalhe == "50% × R$ 1.518,00"


def test_blocos_com_regras_diferentes() -> None:
    regras = [
        _bloco("01/2021", "06/2023", TIPO_SALARIO_MINIMO, percentual=D("0.30")),
        _bloco("07/2023", "12/2024", TIPO_FIXO, valor=D("700")),
        _bloco("01/2025", None, TIPO_FIXO, valor=D("900")),
    ]
    parcelas = gerar_parcelas(regras, ate="09/2026")
    assert len(parcelas) == 69
    assert parcelas[0].principal == D("330.00")
    p_2023_06 = next(p for p in parcelas if p.competencia == Competencia(2023, 6))
    p_2023_07 = next(p for p in parcelas if p.competencia == Competencia(2023, 7))
    p_2025_01 = next(p for p in parcelas if p.competencia == Competencia(2025, 1))
    p_2026_09 = parcelas[-1]
    assert p_2023_06.principal == D("396.00")
    assert p_2023_06.detalhe == "30% × R$ 1.320,00"
    assert p_2023_07.principal == D("700.00")
    assert p_2025_01.principal == D("900.00")
    assert p_2026_09.competencia == Competencia(2026, 9)
    assert p_2026_09.principal == D("900.00")
    assert [p.numero for p in parcelas] == list(range(1, 70))


def test_lacuna_entre_blocos_e_rejeitada() -> None:
    regras = [
        _bloco("01/2021", "06/2023", TIPO_FIXO, valor=D("700")),
        _bloco("08/2023", "12/2024", TIPO_FIXO, valor=D("700")),
    ]
    with pytest.raises(ValueError) as exc:
        gerar_parcelas(regras, ate="12/2024")
    assert "lacuna" in str(exc.value)


def test_sobreposicao_entre_blocos_e_rejeitada() -> None:
    regras = [
        _bloco("01/2021", "06/2023", TIPO_FIXO, valor=D("700")),
        _bloco("06/2023", "12/2024", TIPO_FIXO, valor=D("800")),
    ]
    with pytest.raises(ValueError) as exc:
        gerar_parcelas(regras, ate="12/2024")
    assert "sobreposição" in str(exc.value)


def test_blocos_desordenados_e_rejeitados() -> None:
    regras = [
        _bloco("01/2025", None, TIPO_FIXO, valor=D("900")),
        _bloco("01/2024", "12/2024", TIPO_FIXO, valor=D("700")),
    ]
    with pytest.raises(ValueError) as exc:
        gerar_parcelas(regras, ate="12/2025")
    assert "ordenados" in str(exc.value)


def test_periodo_fora_da_cobertura_do_salario_minimo() -> None:
    with pytest.raises(CoverageError) as exc:
        gerar_parcelas(
            [_bloco("01/1993", "12/1993", TIPO_SALARIO_MINIMO, percentual=D("0.30"))],
            ate="12/1993",
        )
    assert "01/1993" in str(exc.value)


def test_vencimento_dia_31_e_ajustado_para_o_mes() -> None:
    parcelas = gerar_parcelas(
        [_bloco("01/2025", "03/2025", TIPO_FIXO, valor=D("100"))],
        ate="03/2025",
        dia_vencimento=31,
    )
    assert parcelas[0].vencimento == date(2025, 1, 31)
    assert parcelas[1].vencimento == date(2025, 2, 28)
    assert parcelas[2].vencimento == date(2025, 3, 31)


def test_regras_invalidas() -> None:
    with pytest.raises(ValueError):
        RegraAlimento(inicio=Competencia(2025, 1), fim=None, tipo="outro")
    with pytest.raises(ValueError):
        RegraAlimento(inicio=Competencia(2025, 1), fim=None, tipo=TIPO_SALARIO_MINIMO)
    with pytest.raises(ValueError):
        RegraAlimento(
            inicio=Competencia(2025, 1),
            fim=None,
            tipo=TIPO_SALARIO_MINIMO,
            percentual=D("0"),
        )
    with pytest.raises(ValueError):
        RegraAlimento(inicio=Competencia(2025, 1), fim=None, tipo=TIPO_FIXO)
    with pytest.raises(ValueError):
        RegraAlimento(inicio=Competencia(2025, 6), fim=Competencia(2025, 1), tipo=TIPO_FIXO, valor=D("10"))
    with pytest.raises(ValueError):
        gerar_parcelas([], ate="12/2025")
    with pytest.raises(ValueError):
        gerar_parcelas(
            [_bloco("01/2025", "12/2025", TIPO_FIXO, valor=D("100"))],
            ate="12/2025",
            dia_vencimento=32,
        )
    with pytest.raises(ValueError):
        gerar_parcelas(
            [_bloco("01/2025", "12/2025", TIPO_FIXO, valor=D("100"))],
            ate="12/2024",
        )


def test_percentual_de_salario_minimo_sem_bloco_de_fim() -> None:
    parcelas = gerar_parcelas(
        [_bloco("01/2026", None, TIPO_SALARIO_MINIMO, percentual=D("0.30"))],
        ate="12/2026",
    )
    assert len(parcelas) == 12
    assert all(p.principal == D("486.30") for p in parcelas)
