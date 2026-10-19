from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.correcao import ConfigCorrecao, SegmentoCorrecao, calcular_correcao
from app.indexers import CoverageError, IndexerError, obter
from app.indexers.ipca import KEY as IpcaKey
from app.indexers.selic import KEY as SelicKey

D = Decimal


def test_correcao_aplicada_exemplo_oficial() -> None:
    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(
            termo_inicial=Competencia(1995, 1),
            termo_final=Competencia(2026, 9),
        ),
    )
    assert resultado.aplicado is True
    assert resultado.fator_inicial == D("1.133251")
    assert resultado.fator_final == D("8.566509")
    assert resultado.valor_corrigido == D("7559.23")
    assert resultado.correcao == D("6559.23")
    assert resultado.principal + resultado.correcao == resultado.valor_corrigido
    assert resultado.indexador_versao == "2026.09"
    assert resultado.indexador_fonte == "AASP"
    assert resultado.fator_exibicao == D("7.559234")


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
            ConfigCorrecao(termo_inicial=Competencia(2026, 1), termo_final=Competencia(2026, 10)),
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


def test_fronteira_compartilhada_nao_duplica_nem_perde_fatores() -> None:
    """Dois trechos do mesmo índice encerrando na mesma competência = um trecho só."""
    inicial, fronteira, final = (
        Competencia(2025, 2),
        Competencia(2025, 4),
        Competencia(2026, 9),
    )
    ipca = obter(IpcaKey)

    unico = calcular_correcao(
        "30018.44",
        ConfigCorrecao(
            aplicar=True,
            indexador=IpcaKey,
            termo_inicial=inicial,
            termo_final=final,
        ),
    )
    partido = calcular_correcao(
        "30018.44",
        ConfigCorrecao(
            aplicar=True,
            indexador=IpcaKey,
            termo_inicial=inicial,
            termo_final=final,
            segmentos=(
                SegmentoCorrecao(inicial, fronteira, IpcaKey),
                SegmentoCorrecao(fronteira, final, IpcaKey),
            ),
        ),
    )

    assert unico.razao == ipca.valor(final) / ipca.valor(inicial)
    assert partido.razao == unico.razao
    assert partido.valor_corrigido == unico.valor_corrigido
    assert len(partido.segmentos) == 2


def test_segmentos_distintos_encadeados_sem_competencia_fora_do_produto() -> None:
    """A fronteira compartilhada liga as duas séries sem buraco no meio."""
    ipca = obter(IpcaKey)
    selic = obter(SelicKey)
    inicio, fronteira, fim = Competencia(2025, 2), Competencia(2025, 4), Competencia(2026, 9)

    resultado = calcular_correcao(
        "1000",
        ConfigCorrecao(
            aplicar=True,
            indexador=IpcaKey,
            termo_inicial=inicio,
            termo_final=fim,
            segmentos=(
                SegmentoCorrecao(inicio, fronteira, IpcaKey),
                SegmentoCorrecao(fronteira, fim, SelicKey),
            ),
        ),
    )

    esperado = (ipca.valor(fronteira) / ipca.valor(inicio)) * (
        selic.valor(fim) / selic.valor(fronteira)
    )
    assert resultado.razao == esperado
    # sem a fronteira compartilhada a razão perderia a transição fev → abr/2025
    com_lacuna = (ipca.valor(fronteira) / ipca.valor(inicio)) * (
        selic.valor(fim) / selic.valor(fronteira.proxima)
    )
    assert resultado.razao != com_lacuna


def test_sobrepositao_real_de_segmentos_continua_sendo_rejeitada() -> None:
    with pytest.raises(ValueError, match="sobrepõem"):
        calcular_correcao(
            "1000",
            ConfigCorrecao(
                aplicar=True,
                indexador=IpcaKey,
                termo_inicial=Competencia(2025, 1),
                termo_final=Competencia(2026, 9),
                segmentos=(
                    SegmentoCorrecao(Competencia(2025, 1), Competencia(2025, 6), IpcaKey),
                    SegmentoCorrecao(Competencia(2025, 3), Competencia(2026, 9), SelicKey),
                ),
            ),
        )


def test_cobertura_insuficiente_do_ipca_continua_sendo_erro_explicito() -> None:
    with pytest.raises(CoverageError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(
                indexador=IpcaKey,
                termo_inicial=Competencia(1979, 11),
                termo_final=Competencia(2026, 9),
            ),
        )
    with pytest.raises(CoverageError):
        calcular_correcao(
            "1000",
            ConfigCorrecao(
                indexador=IpcaKey,
                termo_inicial=Competencia(2025, 1),
                termo_final=Competencia(2026, 10),
            ),
        )
