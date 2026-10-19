from datetime import date
from decimal import Decimal

import pytest

from app.engine.encargos_consolidados import EncargoConsolidado, calcular_encargos_consolidados
from app.engine.juros import ConfigJuros


def _parcelas():
    return [
        {"numero": 1, "verba": {"id": "a"}, "principal": "1000.00",
         "correcao": {"valor_corrigido": "1100.00"}, "juros": {"aplicado": False, "juros": "0.00"}},
        {"numero": 2, "verba": {"id": "b"}, "principal": "2000.00",
         "correcao": {"valor_corrigido": "2300.00"}, "juros": {"aplicado": False, "juros": "0.00"}},
    ]


def test_multa_e_honorarios_consolidados_em_ordem():
    resultado = calcular_encargos_consolidados([
        EncargoConsolidado("multa", "multa", 10, (), ("principal_corrigido",), (), Decimal(".10")),
        EncargoConsolidado("hon", "honorarios", 20, (), ("principal_corrigido",), ("multa",), Decimal(".15")),
    ], _parcelas())
    assert resultado[0]["base"]["valor"] == "3400.00"
    assert resultado[0]["valor"] == "340.00"
    assert resultado[1]["base"]["valor"] == "3740.00"
    assert resultado[1]["valor"] == "561.00"


def test_verba_selecionada_e_arredondamento_unico():
    parcelas = _parcelas()
    parcelas[0]["correcao"]["valor_corrigido"] = "100.04"
    parcelas[1]["correcao"]["valor_corrigido"] = "100.04"
    resultado = calcular_encargos_consolidados([
        EncargoConsolidado("m", "multa", 1, ("a", "b"), ("principal_corrigido",), (), Decimal(".10")),
    ], parcelas)
    assert resultado[0]["valor"] == "20.01"


def test_juros_consolidado_rejeita_juros_individuais():
    parcelas = _parcelas()
    parcelas[0]["juros"] = {"aplicado": True, "juros": "1.00"}
    with pytest.raises(ValueError, match="juros individuais"):
        calcular_encargos_consolidados([
            EncargoConsolidado("j", "juros", 1, (), ("principal_corrigido",), (), Decimal(".01"),
                                juros=ConfigJuros(aplicar=False), inicio=date(2026, 1, 1), fim=date(2026, 1, 31)),
        ], parcelas)
