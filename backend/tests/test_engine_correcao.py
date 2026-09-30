from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.correcao import ConfigCorrecao, calcular_correcao
from app.indexers import CoverageError, IndexerError

D = Decimal


def test_correcao_aplicada_exemplo_oficial() -> None:
    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(
            termo_inicial=Competencia(1995, 1),
            termo_final=Competencia(2026, 6),
        ),
    )
    assert resultado.aplicado is True
    assert resultado.fator_inicial == D("1.133251")
    assert resultado.fator_final == D("8.560658")
    assert resultado.valor_corrigido == D("7554.07")
    assert resultado.correcao == D("6554.07")
    assert resultado.principal + resultado.correcao == resultado.valor_corrigido
    assert resultado.indexador_versao == "2026.08"
    assert resultado.indexador_fonte == "AASP"
    assert resultado.fator_exibicao == D("7.554071")


def test_nao_aplicar_e_explicito() -> None:
    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(aplicar=False, termo_inicial=Competencia(2020, 1), termo_final=Competencia(2026, 1)),
    )
    assert resultado.aplicado is False
    assert resultado.valor_corrigido == D("1000.00")
    assert resultado.correcao == D("0.00")
    assert "não aplicada" in resultado.motivo
    assert "explícito" in resultado.motivo
    assert resultado.fator_exibicao is None


def test_termos_default_vindo_de_vencimento_e_data_base() -> None:
    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(),
        vencimento="2026-01-15",
        data_base="2026-08-30",
    )
    assert resultado.termo_inicial == Competencia(2026, 1)
    assert resultado.termo_final == Competencia(2026, 8)
    assert resultado.aplicado is True
    assert resultado.valor_corrigido > resultado.principal


def test_sem_periodo_informado_nao_calcula() -> None:
    resultado = calcular_correcao("1000", ConfigCorrecao())
    assert resultado.aplicado is False
    assert "termo inicial ou final não informado" in resultado.motivo


def test_mesmo_mes_nao_corrige() -> None:
    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(termo_inicial=Competencia(2026, 5), termo_final=Competencia(2026, 5)),
    )
    assert resultado.aplicado is True
    assert resultado.razao == D("1")
    assert resultado.correcao == D("0.00")


def test_fora_da_cobertura_nao_usa_indice_silenciosamente() -> None:
    with pytest.raises(CoverageError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(termo_inicial=Competencia(1991, 6), termo_final=Competencia(2026, 1)),
        )
    with pytest.raises(CoverageError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(termo_inicial=Competencia(2026, 1), termo_final=Competencia(2026, 9)),
        )


def test_termo_final_anterior_ao_inicial_rejeitado() -> None:
    with pytest.raises(ValueError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(termo_inicial=Competencia(2026, 5), termo_final=Competencia(2026, 1)),
        )


def test_indexador_de_juros_nao_serve_para_correcao() -> None:
    with pytest.raises(IndexerError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(
                indexador="salario_minimo",
                termo_inicial=Competencia(2026, 1),
                termo_final=Competencia(2026, 8),
            ),
        )


def test_principal_negativo_rejeitado() -> None:
    with pytest.raises(ValueError):
        calcular_correcao(
            "-100",
            ConfigCorrecao(termo_inicial=Competencia(2026, 1), termo_final=Competencia(2026, 2)),
        )


def test_arredondamento_half_up_nos_centavos() -> None:
    resultado = calcular_correcao(
        "0.01",
        ConfigCorrecao(termo_inicial=Competencia(2026, 1), termo_final=Competencia(2026, 8)),
    )
    assert resultado.valor_corrigido == D("0.01")
    assert resultado.valor_corrigido == resultado.valor_corrigido.quantize(D("0.01"))
    assert resultado.principal + resultado.correcao == resultado.valor_corrigido


def test_grande_quantidade_de_parcelas_e_estavel() -> None:
    total_correcao = Decimal("0.00")
    for i in range(1, 501):
        r = calcular_correcao(
            "330.00",
            ConfigCorrecao(
                termo_inicial=Competencia(2021, 1) if i <= 12 else Competencia(2021, 1 + (i % 12)),
                termo_final=Competencia(2026, 8),
            ),
        )
        total_correcao += r.correcao
        assert r.principal + r.correcao == r.valor_corrigido
    assert total_correcao > 0
