from datetime import date
from decimal import Decimal

import pytest

from app.core.money import brl
from app.engine.bases import (
    BASE_COM_JUROS,
    BASE_CORRIGIDO,
    BASE_PRINCIPAL,
    ValoresBase,
    construir_bases,
    rotulo_base,
)
from app.engine.encargos import ConfigEncargo, Pagamento, calcular_encargo, total_pagamentos

D = Decimal


def test_bases_se_geram_em_ordem() -> None:
    bases = construir_bases(D("1000"), D("250"), D("30"))
    assert bases == ValoresBase(
        principal=D("1000.00"),
        corrigido=D("1250.00"),
        com_juros=D("1280.00"),
    )
    assert bases.valor(BASE_PRINCIPAL) == D("1000.00")
    assert bases.valor(BASE_CORRIGIDO) == D("1250.00")
    assert bases.valor(BASE_COM_JUROS) == D("1280.00")


def test_rotulo_base_valida() -> None:
    assert rotulo_base(BASE_PRINCIPAL) == "principal histórico"
    with pytest.raises(ValueError, match="base de cálculo inválida"):
        rotulo_base("qualquer_coisa")


def test_encargo_nao_aplicado_zera() -> None:
    bases = construir_bases(D("1000"), D("0"), D("0"))
    r = calcular_encargo(ConfigEncargo(), bases, nome="Multa")
    assert r.aplicado is False
    assert r.valor == D("0.00")
    assert "não aplicado" in r.motivo


def test_multa_2_por_cento_sobre_corrigido() -> None:
    bases = construir_bases(D("1000"), D("250"), D("30"))
    cfg = ConfigEncargo(aplicar=True, percentual=D("0.02"), base=BASE_CORRIGIDO)
    r = calcular_encargo(cfg, bases, nome="Multa")
    assert r.valor == D("25.00")
    assert r.percentual == D("0.02")
    assert r.base_valor == D("1250.00")
    assert brl(r.base_valor) == "R$ 1.250,00"


def test_honorarios_sobre_principal_e_com_juros() -> None:
    bases = construir_bases(D("1000"), D("250"), D("30"))
    sobre_principal = calcular_encargo(
        ConfigEncargo(aplicar=True, percentual=D("0.10"), base=BASE_PRINCIPAL),
        bases,
        nome="Honorários",
    )
    sobre_com_juros = calcular_encargo(
        ConfigEncargo(aplicar=True, percentual=D("0.10"), base=BASE_COM_JUROS),
        bases,
        nome="Honorários",
    )
    assert sobre_principal.valor == D("100.00")
    assert sobre_com_juros.valor == D("128.00")


def test_encargo_de_valor_fixo() -> None:
    bases = construir_bases(D("1000"), D("0"), D("0"))
    r = calcular_encargo(
        ConfigEncargo(aplicar=True, valor_fixo=D("150.555"), base=BASE_PRINCIPAL),
        bases,
        nome="Multa",
    )
    assert r.valor == D("150.56")
    assert r.percentual is None


def test_encargo_exige_um_valor() -> None:
    with pytest.raises(ValueError, match="exige percentual ou valor fixo"):
        ConfigEncargo(aplicar=True)
    with pytest.raises(ValueError, match="não ambos"):
        ConfigEncargo(aplicar=True, percentual=D("0.1"), valor_fixo=D("10"))
    with pytest.raises(ValueError, match="negativo"):
        ConfigEncargo(aplicar=True, percentual=D("-0.1"))


def test_encargo_base_invalida() -> None:
    with pytest.raises(ValueError, match="base de cálculo inválida"):
        ConfigEncargo(aplicar=True, percentual=D("0.1"), base="xyz")


def test_pagamento_soma_e_valida() -> None:
    pagamentos = [
        Pagamento(date(2026, 3, 10), D("100")),
        Pagamento(date(2026, 4, 10), D("150.505")),
    ]
    assert total_pagamentos(pagamentos) == D("250.51")
    with pytest.raises(ValueError, match="não pode ser negativo"):
        Pagamento(date(2026, 5, 10), D("-1"))
