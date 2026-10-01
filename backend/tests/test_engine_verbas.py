from datetime import date
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.calculo import ConfiguracaoCalculo, calcular
from app.engine.correcao import ConfigCorrecao
from app.engine.encargos import ConfigEncargo
from app.engine.juros import (
    ConfigJuros,
    MODALIDADE_FIXA,
    MODALIDADE_NAO_APLICAR,
)
from app.engine.parcela import ParcelaInput, calcular_parcela

D = Decimal


def _config_data_base() -> ConfiguracaoCalculo:
    """Config global neutra: sem correção/juros/encargos por padrão."""
    return ConfiguracaoCalculo(
        data_base=date(2026, 8, 31),
        correcao=ConfigCorrecao(aplicar=False),
        juros=ConfigJuros(aplicar=False),
        multa=ConfigEncargo(aplicar=False),
        honorarios=ConfigEncargo(aplicar=False),
    )


def test_config_juros_aceita_inicio_e_fim_opcionais() -> None:
    cfg = ConfigJuros(
        aplicar=True,
        modalidade=MODALIDADE_FIXA,
        taxa=D("0.01"),
        inicio=date(2024, 3, 15),
        fim=date(2026, 8, 31),
    )
    assert cfg.inicio == date(2024, 3, 15)
    assert cfg.fim == date(2026, 8, 31)


def test_config_juros_rejeita_inicio_posterior_ao_fim() -> None:
    with pytest.raises(ValueError, match="posterior"):
        ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_FIXA,
            taxa=D("0.01"),
            inicio=date(2026, 8, 31),
            fim=date(2024, 1, 1),
        )


def test_duas_parcelas_com_juros_em_datas_diferentes_ficam_independentes() -> None:
    """Verba/dano moral vs honorários: início de juros próprio, sem contaminar a outra."""
    configuracao = _config_data_base()

    dano_moral = ParcelaInput(
        numero=1,
        vencimento=date(2020, 5, 10),
        principal=D("20000.00"),
        descricao="Dano moral",
        correcao=ConfigCorrecao(
            aplicar=True,
            indexador="tjsp_tabela_pratica",
            termo_inicial=Competencia(2020, 5),
            termo_final=Competencia(2026, 8),
        ),
        juros=ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_FIXA,
            taxa=D("0.01"),
            inicio=date(2024, 3, 15),
            fim=date(2026, 8, 31),
            base="corrigido",
        ),
    )
    honorarios = ParcelaInput(
        numero=2,
        vencimento=date(2023, 8, 1),
        principal=D("5000.00"),
        descricao="Honorários",
        correcao=ConfigCorrecao(
            aplicar=True,
            indexador="tjsp_tabela_pratica",
            termo_inicial=Competencia(2023, 8),
            termo_final=Competencia(2026, 8),
        ),
        juros=ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_FIXA,
            taxa=D("0.01"),
            inicio=date(2023, 8, 1),
            fim=date(2026, 8, 31),
            base="corrigido",
        ),
    )

    r1 = calcular_parcela(dano_moral, configuracao=configuracao)
    r2 = calcular_parcela(honorarios, configuracao=configuracao)

    # datas de correção independentes
    assert r1.correcao.termo_inicial == Competencia(2020, 5)
    assert r2.correcao.termo_inicial == Competencia(2023, 8)
    assert r1.correcao.termo_final == Competencia(2026, 8)
    assert r2.correcao.termo_final == Competencia(2026, 8)
    assert r1.correcao.correcao != r2.correcao.correcao

    # datas de juros independentes (não usar o vencimento do outro)
    assert r1.juros.trechos[0].inicio == date(2024, 3, 15)
    assert r2.juros.trechos[0].inicio == date(2023, 8, 1)
    assert r1.juros.trechos[0].fim == date(2026, 8, 31)
    assert r2.juros.trechos[0].fim == date(2026, 8, 31)
    assert r1.juros.juros != r2.juros.juros

    # totais distintos e coerentes com cada verba
    assert r1.total != r2.total
    assert r1.saldo == r1.total
    assert r2.saldo == r2.total

    # agregação também preserva independência
    resultado = calcular(configuracao, [dano_moral, honorarios])
    assert resultado.resumo.qtd_parcelas == 2
    p1, p2 = resultado.parcelas
    assert p1.correcao.termo_inicial == Competencia(2020, 5)
    assert p2.correcao.termo_inicial == Competencia(2023, 8)
    assert p1.juros.trechos[0].inicio == date(2024, 3, 15)
    assert p2.juros.trechos[0].inicio == date(2023, 8, 1)
    assert resultado.resumo.total == (p1.total + p2.total).quantize(D("0.01"))


def test_juros_sem_inicio_usa_vencimento_da_parcela() -> None:
    """Compatibilidade: sem ConfigJuros.inicio, mantém vencimento → data_base."""
    configuracao = _config_data_base()
    parcela = ParcelaInput(
        numero=1,
        vencimento=date(2024, 7, 10),
        principal=D("1000.00"),
        juros=ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_FIXA,
            taxa=D("0.01"),
        ),
    )
    r = calcular_parcela(parcela, configuracao=configuracao)
    assert r.juros.trechos[0].inicio == date(2024, 7, 10)
    assert r.juros.trechos[0].fim == date(2026, 8, 31)


def test_config_global_neutra_nao_contamina_parcelas_com_config_propria() -> None:
    configuracao = ConfiguracaoCalculo(
        data_base=date(2026, 8, 31),
        correcao=ConfigCorrecao(aplicar=True, termo_inicial=Competencia(2025, 1)),
        juros=ConfigJuros(aplicar=True, modalidade=MODALIDADE_NAO_APLICAR),
        multa=ConfigEncargo(aplicar=True, percentual=D("0.02")),
        honorarios=ConfigEncargo(aplicar=False),
    )
    parcela = ParcelaInput(
        numero=1,
        vencimento=date(2021, 1, 10),
        principal=D("1000.00"),
        correcao=ConfigCorrecao(
            aplicar=True,
            indexador="tjsp_tabela_pratica",
            termo_inicial=Competencia(2021, 1),
            termo_final=Competencia(2026, 8),
        ),
        juros=ConfigJuros(aplicar=False),
        multa=ConfigEncargo(aplicar=False),
    )
    r = calcular_parcela(parcela, configuracao=configuracao)
    assert r.correcao.termo_inicial == Competencia(2021, 1)
    assert r.juros.aplicado is False
    assert r.multa.aplicado is False
    assert r.multa.valor == D("0.00")
