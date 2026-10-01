from datetime import date
from decimal import Decimal

import pytest

from app.core.competencia import Competencia
from app.engine.calculo import ConfiguracaoCalculo, calcular
from app.engine.correcao import ConfigCorrecao
from app.engine.encargos import ConfigEncargo, Pagamento
from app.engine.juros import ConfigJuros, MODALIDADE_NAO_APLICAR
from app.engine.parcela import ParcelaInput

D = Decimal


def _config(**kwargs) -> ConfiguracaoCalculo:
    dados = {
        "data_base": date(2026, 8, 31),
        "correcao": ConfigCorrecao(aplicar=False),
        "juros": ConfigJuros(aplicar=False),
        "multa": ConfigEncargo(aplicar=True, percentual=D("0.02")),
        "honorarios": ConfigEncargo(aplicar=False),
    }
    dados.update(kwargs)
    return ConfiguracaoCalculo(**dados)


def _entrada(numero: int, ano: int, mes: int, principal: str = "1000.00", **kwargs) -> ParcelaInput:
    return ParcelaInput(
        numero=numero,
        vencimento=date(ano, mes, 10),
        principal=D(principal),
        **kwargs,
    )


def test_resumo_soma_componentes() -> None:
    entradas = [_entrada(1, 2021, 1), _entrada(2, 2021, 2), _entrada(3, 2021, 3)]
    r = calcular(_config(), entradas)

    assert r.resumo.qtd_parcelas == 3
    assert r.resumo.periodo_inicio == date(2021, 1, 10)
    assert r.resumo.periodo_fim == date(2021, 3, 10)
    assert r.resumo.principal == D("3000.00")
    assert r.resumo.multa == D("60.00")
    assert r.resumo.correcao == D("0.00")
    assert r.resumo.juros == D("0.00")
    assert r.resumo.honorarios == D("0.00")
    assert r.resumo.total == D("3060.00")
    assert r.resumo.adicional == D("60.00")
    assert r.resumo.saldo == D("3060.00")
    assert r.avisos == ()


def test_total_igual_a_soma_das_parcelas() -> None:
    entradas = [_entrada(1, 2021, 1), _entrada(2, 2021, 2)]
    r = calcular(_config(), entradas)
    assert sum((p.total for p in r.parcelas), D("0.00")) == r.resumo.total


def test_pagamentos_zeram_saldo_quando_cobrem() -> None:
    entrada = _entrada(
        1,
        2021,
        1,
        pagamentos=(Pagamento(date(2026, 1, 10), D("1020.00")),),
    )
    r = calcular(_config(), [entrada])
    assert r.resumo.pagamentos == D("1020.00")
    assert r.resumo.saldo == D("0.00")
    assert r.avisos == ()


def test_aviso_quando_pagamento_excede() -> None:
    entrada = _entrada(
        1,
        2021,
        1,
        pagamentos=(Pagamento(date(2026, 1, 10), D("9999.00")),),
    )
    r = calcular(_config(), [entrada])
    assert any("acima do total" in a for a in r.avisos)


def test_sem_parcelas_levanta_erro() -> None:
    with pytest.raises(ValueError, match="ao menos uma parcela"):
        calcular(_config(), [])


def test_numero_repetido_levanta_erro() -> None:
    with pytest.raises(ValueError, match="repetido"):
        calcular(_config(), [_entrada(1, 2021, 1), _entrada(1, 2021, 2)])


def test_bases_utilizadas_da_correcao() -> None:
    r = calcular(
        ConfiguracaoCalculo(
            data_base=date(2026, 8, 31),
            correcao=ConfigCorrecao(
                aplicar=True,
                indexador="tjsp_tabela_pratica",
                termo_final=Competencia(2026, 8),
            ),
            juros=ConfigJuros(aplicar=False),
        ),
        [_entrada(1, 2021, 1)],
    )
    assert len(r.bases) == 1
    base = r.bases[0]
    assert base.key == "tjsp_tabela_pratica"
    assert base.papel == "Correção monetária"
    assert base.versao == "2026.08"
    assert base.fonte == "AASP"
    assert base.cobertura.startswith("01/1992")


def test_bases_utilizadas_sem_correcao_e_vazia() -> None:
    r = calcular(_config(), [_entrada(1, 2021, 1)])
    assert r.bases == ()


def test_correcao_e_juros_reais_no_resumo() -> None:
    r = calcular(
        ConfiguracaoCalculo(
            data_base=date(2026, 8, 31),
            correcao=ConfigCorrecao(
                aplicar=True,
                indexador="tjsp_tabela_pratica",
                termo_final=Competencia(2026, 8),
            ),
            juros=ConfigJuros(aplicar=True, modalidade=MODALIDADE_NAO_APLICAR),
            multa=ConfigEncargo(aplicar=False),
            honorarios=ConfigEncargo(aplicar=True, percentual=D("0.10"), base="principal"),
        ),
        [_entrada(1, 2021, 1, "10000.00")],
    )
    assert r.resumo.correcao > D("0.00")
    assert r.resumo.honorarios == D("1000.00")
    assert r.resumo.total == (
        r.resumo.principal + r.resumo.correcao + r.resumo.juros + r.resumo.honorarios
    )
    assert r.resumo.saldo == r.resumo.total
