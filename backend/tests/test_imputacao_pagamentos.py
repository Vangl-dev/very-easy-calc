"""Pagamentos abatidos na data em que foram feitos (art. 354 do CC)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app

DATA_FINAL = "2026-09-30"
INICIO_JUROS = "2024-03-01"
DATA_PAGAMENTO = "2025-07-29"


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


def _verba(id_: str, valor: str, data: str, pagamentos: list[dict] | None = None) -> dict:
    return {
        "id": id_,
        "tipo": "valor",
        "nome": id_,
        "valor": valor,
        "data_base": data,
        "correcao": {"aplicar": True, "indexador": "tjsp_tabela_pratica", "termo_inicial": data},
        "juros": {"aplicar": True, "modalidade": "taxa_legal", "base": "corrigido", "inicio": INICIO_JUROS},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "regimes": [],
        "pagamentos": pagamentos or [],
    }


def _payload(valor_pago: str, criterio: str = "data_pagamento", consolidados=None) -> dict:
    pagamento = {"data": DATA_PAGAMENTO, "valor": valor_pago, "descricao": "penhora"}
    return {
        "tipo": "parcelas",
        "titulo": "Imputação",
        "processo": "",
        "parte": "",
        "data_base": DATA_FINAL,
        "criterio_pagamentos": criterio,
        "verbas": [
            _verba("entrada", "36800.00", "2020-10-19", [pagamento]),
            _verba("parcelas", "14689.70", "2022-02-06"),
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "encargos_consolidados": consolidados or [],
    }


def _post(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _d(valor: str) -> Decimal:
    return Decimal(valor)


def test_payload_antigo_continua_deduzindo_o_valor_nominal(client: TestClient) -> None:
    payload = _payload("1881.86")
    del payload["criterio_pagamentos"]
    corpo = _post(client, payload)

    assert corpo["resumo"]["pagamentos"] == "1881.86"
    assert corpo["imputacao_pagamentos"] == []
    assert corpo["memoria"]["criterios"]["pagamentos_criterio"] == "nominal"


def test_pagamento_menor_que_os_juros_e_atualizado_ate_a_data_final(client: TestClient) -> None:
    nominal = _post(client, _payload("1881.86", criterio="nominal"))
    corpo = _post(client, _payload("1881.86"))

    [imputacao] = corpo["imputacao_pagamentos"]
    [item] = imputacao["itens"]
    assert item["parcela"] == 1
    assert item["principal"] == "0.00"
    # Só quita juros: a base dos juros futuros não muda.
    assert corpo["resumo"]["juros"] == nominal["resumo"]["juros"]
    esperado = (Decimal("1881.86") * _d(item["fator"])).quantize(Decimal("0.01"))
    assert abs(_d(imputacao["valor_atualizado"]) - esperado) <= Decimal("0.01")
    assert corpo["resumo"]["pagamentos"] == imputacao["valor_atualizado"]
    assert _d(corpo["resumo"]["saldo"]) == _d(corpo["resumo"]["total"]) - _d(
        imputacao["valor_atualizado"]
    )
    assert corpo["memoria"]["criterios"]["pagamentos_criterio"] == "data_pagamento"


def test_pagamento_quita_juros_vencidos_antes_do_principal(client: TestClient) -> None:
    sem_pagamento = _post(client, _payload("0.01"))
    corpo = _post(client, _payload("30000.00"))

    [imputacao] = corpo["imputacao_pagamentos"]
    itens = {item["parcela"]: item for item in imputacao["itens"]}
    # Juros das duas parcelas primeiro; o resto vai ao principal da mais antiga.
    assert _d(itens[1]["juros"]) > 0 and _d(itens[2]["juros"]) > 0
    assert _d(itens[1]["principal"]) > 0
    assert itens[2]["principal"] == "0.00"
    soma = sum(_d(i["juros"]) + _d(i["principal"]) for i in imputacao["itens"])
    assert _d(imputacao["valor_atualizado"]) == soma

    # O principal abatido deixa de render juros depois do pagamento.
    assert _d(corpo["resumo"]["juros"]) < _d(sem_pagamento["resumo"]["juros"])
    entrada = corpo["parcelas"][0]
    bases = [t["rotulo"] for t in entrada["juros"]["trechos"]]
    assert any("base" in rotulo for rotulo in bases)
    assert entrada["juros"]["trechos"][-1]["inicio"] == "2025-07-30"


def test_excedente_abate_encargos_e_avisa_o_que_sobrou(client: TestClient) -> None:
    consolidados = [
        {"id": "m523", "tipo": "multa", "ordem": 1,
         "componentes": ["principal_corrigido", "juros_individuais"], "percentual": "0.10"},
    ]
    corpo = _post(client, _payload("200000.00", consolidados=consolidados))

    assert corpo["resumo"]["saldo"] == "0.00"
    [imputacao] = corpo["imputacao_pagamentos"]
    assert _d(imputacao["encargos"]) > 0
    assert any("excedem todo o débito" in aviso for aviso in corpo["avisos"])
