from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.engine.memoria import ESQUEMA_MEMORIA
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


def _payload_verbas(**kwargs) -> dict:
    base = {
        "tipo": "parcelas",
        "titulo": "Cálculo com verbas",
        "processo": "0001234-56.2020.8.26.0100",
        "parte": "Autor",
        "data_base": "2026-08-31",
        "verbas": [
            {
                "nome": "Dano moral",
                "valor": "20000.00",
                "data_base": "2020-05-10",
                "descricao": "Dano moral",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2020-05",
                    "termo_final": "2026-08",
                },
                "juros": {
                    "aplicar": True,
                    "modalidade": "fixa",
                    "taxa": "0.01",
                    "unidade": "mensal",
                    "base": "corrigido",
                    "inicio": "2024-03-15",
                    "fim": "2026-08-31",
                },
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [],
            },
            {
                "nome": "Honorários",
                "valor": "5000.00",
                "data_base": "2023-08-01",
                "descricao": "Honorários",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2023-08",
                    "termo_final": "2026-08",
                },
                "juros": {
                    "aplicar": True,
                    "modalidade": "fixa",
                    "taxa": "0.01",
                    "unidade": "mensal",
                    "base": "corrigido",
                    "inicio": "2023-08-01",
                    "fim": "2026-08-31",
                },
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [],
            },
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    base.update(kwargs)
    return base


def test_duas_verbas_com_datas_diferentes_permanecem_independentes(client: TestClient) -> None:
    response = client.post("/api/calculos", json=_payload_verbas())
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["tipo"] == "parcelas"
    assert body["resumo"]["qtd_parcelas"] == 2
    assert len(body["parcelas"]) == 2

    p_dano = body["parcelas"][0]
    p_hon = body["parcelas"][1]

    assert p_dano["verba"]["nome"] == "Dano moral"
    assert p_hon["verba"]["nome"] == "Honorários"
    assert p_dano["principal"] == "20000.00"
    assert p_hon["principal"] == "5000.00"
    assert p_dano["vencimento"] == "2020-05-10"
    assert p_hon["vencimento"] == "2023-08-01"

    # correção com início próprio
    assert p_dano["correcao"]["termo_inicial"] == "2020-05"
    assert p_hon["correcao"]["termo_inicial"] == "2023-08"
    assert p_dano["inicio_correcao"] == "2020-05"
    assert p_hon["inicio_correcao"] == "2023-08"
    assert p_dano["correcao"]["correcao"] != p_hon["correcao"]["correcao"]

    # juros com início próprio (não o vencimento da outra verba)
    assert p_dano["inicio_juros"] == "2024-03-15"
    assert p_hon["inicio_juros"] == "2023-08-01"
    assert p_dano["juros"]["juros"] != p_hon["juros"]["juros"]

    # totais independentes
    assert p_dano["total"] != p_hon["total"]
    assert body["resumo"]["total"] == (
        float(p_dano["total"]) + float(p_hon["total"]) and body["resumo"]["total"]
    )

    # memória preserva verbas
    memoria = body["memoria"]
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    assert len(memoria["verbas"]) == 2
    assert memoria["verbas"][0]["nome"] == "Dano moral"
    assert memoria["verbas"][0]["data_base"] == "2020-05-10"
    assert memoria["verbas"][0]["inicio_correcao"] == "2020-05"
    assert memoria["verbas"][0]["inicio_juros"] == "2024-03-15"
    assert memoria["verbas"][1]["nome"] == "Honorários"
    assert memoria["verbas"][1]["inicio_juros"] == "2023-08-01"
    assert memoria["parcelas"][0]["verba"]["nome"] == "Dano moral"
    assert memoria["parcelas"][1]["verba"]["nome"] == "Honorários"


def test_verbas_ignoram_configs_globais_de_datas(client: TestClient) -> None:
    """Correção/juros globais não sobrescrevem as datas das verbas."""
    payload = _payload_verbas(
        correcao={
            "aplicar": True,
            "indexador": "tjsp_tabela_pratica",
            "termo_inicial": "2025-01",
            "termo_final": "2025-12",
        },
        juros={"aplicar": True, "modalidade": "taxa_legal", "base": "corrigido"},
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    p_dano = body["parcelas"][0]
    p_hon = body["parcelas"][1]
    assert p_dano["inicio_correcao"] == "2020-05"
    assert p_hon["inicio_correcao"] == "2023-08"
    assert p_dano["inicio_juros"] == "2024-03-15"
    assert p_hon["inicio_juros"] == "2023-08-01"


def test_verba_com_pagamento_abate_saldo(client: TestClient) -> None:
    payload = _payload_verbas(
        verbas=[
            {
                "nome": "Dano material",
                "valor": "1000.00",
                "data_base": "2024-01-10",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [
                    {"data": "2026-01-10", "valor": "250.00", "descricao": "parcial"}
                ],
            }
        ]
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    parcela = response.json()["parcelas"][0]
    assert parcela["total"] == "1000.00"
    assert parcela["total_pago"] == "250.00"
    assert parcela["diferenca"] == "750.00"
    assert parcela["saldo"] == "750.00"
    assert parcela["verba"]["nome"] == "Dano material"


def test_payload_com_parcelas_avulsas_continua_funcionando(client: TestClient) -> None:
    """Compatibilidade: caminho antigo sem verbas."""
    payload = {
        "tipo": "parcelas",
        "titulo": "Parcela avulsa",
        "data_base": "2026-08-31",
        "parcelas": [
            {
                "numero": 1,
                "vencimento": "2024-07-10",
                "principal": "1000.00",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            }
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["resumo"]["qtd_parcelas"] == 1
    assert body["parcelas"][0]["principal"] == "1000.00"
    assert body["memoria"]["verbas"] == []
