from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


def _payload_alimentos(**kwargs) -> dict:
    base = {
        "tipo": "alimentos",
        "titulo": "Pensão alimentícia",
        "processo": "0001234-56.2021.8.26.0100",
        "parte": "Autor",
        "data_base": "2026-08-31",
        "alimentos": {
            "regras": [
                {
                    "inicio": "01/2021",
                    "fim": "12/2021",
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "12/2021",
            "dia_vencimento": 10,
        },
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    base.update(kwargs)
    return base


def test_post_alimentos_gera_codigo_e_parcelas_por_competencia(client: TestClient) -> None:
    response = client.post("/api/calculos", json=_payload_alimentos())
    assert response.status_code == 201
    body = response.json()
    assert body["codigo"].startswith("VEC-")
    assert body["codigo"].count("-") == 2
    ano, seq = body["codigo"].split("-")[1:]
    assert len(ano) == 4 and ano.isdigit()
    assert len(seq) == 6 and seq.isdigit()
    assert body["tipo"] == "alimentos"
    assert body["app_version"] == "1.0.0"
    assert body["resumo"]["qtd_parcelas"] == 12
    assert body["resumo"]["principal"] == "3960.00"
    assert len(body["parcelas"]) == 12
    assert body["parcelas"][0]["competencia"] == "2021-01"
    assert body["parcelas"][0]["principal"] == "330.00"
    assert body["parcelas"][0]["salario_minimo"] == "1100.00"
    assert body["parcelas"][0]["percentual"] == "0.30"
    assert body["parcelas"][0]["vencimento"] == "2021-01-10"
    assert body["parcelas"][-1]["competencia"] == "2021-12"
    assert body["parcelas"][-1]["principal"] == "330.00"
    assert any(b["key"] == "salario_minimo" for b in body["bases"])
    base_sm = next(b for b in body["bases"] if b["key"] == "salario_minimo")
    assert base_sm["versao"] == "2026.12"
    assert base_sm["papel"] == "Composição do principal"


def test_post_alimentos_respeita_salario_minimo_por_competencia(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/2023",
                    "fim": "12/2023",
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "12/2023",
            "dia_vencimento": 10,
        }
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    por_comp = {p["competencia"]: p for p in body["parcelas"]}
    assert por_comp["2023-01"]["salario_minimo"] == "1302.00"
    assert por_comp["2023-01"]["principal"] == "390.60"
    assert por_comp["2023-04"]["salario_minimo"] == "1302.00"
    assert por_comp["2023-04"]["principal"] == "390.60"
    assert por_comp["2023-05"]["salario_minimo"] == "1320.00"
    assert por_comp["2023-05"]["principal"] == "396.00"
    assert por_comp["2023-05"]["detalhe"] == "30% × R$ 1.320,00"
    assert por_comp["2023-12"]["salario_minimo"] == "1320.00"
    assert por_comp["2023-12"]["principal"] == "396.00"
    assert body["resumo"]["qtd_parcelas"] == 12


def test_post_alimentos_blocos_diferentes(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/2021",
                    "fim": "06/2023",
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                },
                {
                    "inicio": "07/2023",
                    "fim": "12/2024",
                    "tipo": "fixo",
                    "valor": "700.00",
                },
                {
                    "inicio": "01/2025",
                    "fim": None,
                    "tipo": "fixo",
                    "valor": "900.00",
                },
            ],
            "ate": "03/2025",
            "dia_vencimento": 10,
        }
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["resumo"]["qtd_parcelas"] == 51
    por_comp = {p["competencia"]: p for p in body["parcelas"]}
    assert por_comp["2021-01"]["principal"] == "330.00"
    assert por_comp["2021-01"]["tipo_regra"] == "salario_minimo"
    assert por_comp["2023-04"]["salario_minimo"] == "1302.00"
    assert por_comp["2023-05"]["salario_minimo"] == "1320.00"
    assert por_comp["2023-07"]["principal"] == "700.00"
    assert por_comp["2023-07"]["salario_minimo"] is None
    assert por_comp["2023-07"]["tipo_regra"] == "fixo"
    assert por_comp["2025-01"]["principal"] == "900.00"
    assert por_comp["2025-03"]["principal"] == "900.00"
    assert [p["numero"] for p in body["parcelas"]] == list(range(1, 52))


def test_post_alimentos_com_pagamentos_por_competencia(client: TestClient) -> None:
    payload = _payload_alimentos(
        pagamentos=[
            {
                "competencia": "2021-01",
                "data": "2026-01-10",
                "valor": "100.00",
                "descricao": "depósito parcial",
            },
            {
                "competencia": "2021-02",
                "data": "2026-02-10",
                "valor": "330.00",
            },
        ]
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    por_comp = {p["competencia"]: p for p in body["parcelas"]}
    assert por_comp["2021-01"]["total_pago"] == "100.00"
    assert por_comp["2021-01"]["saldo"] == "230.00"
    assert por_comp["2021-01"]["pagamentos"][0]["descricao"] == "depósito parcial"
    assert por_comp["2021-02"]["total_pago"] == "330.00"
    assert por_comp["2021-02"]["saldo"] == "0.00"
    assert por_comp["2021-03"]["saldo"] == "330.00"
    assert body["resumo"]["pagamentos"] == "430.00"
    assert body["resumo"]["saldo"] == "3530.00"


def test_post_alimentos_com_correcao_e_juros(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/2021",
                    "fim": "12/2021",
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "12/2021",
        },
        correcao={"aplicar": True, "indexador": "tjsp_tabela_pratica"},
        juros={"aplicar": True, "modalidade": "taxa_legal"},
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    parcela = body["parcelas"][0]
    assert parcela["correcao"]["aplicado"] is True
    assert parcela["correcao"]["indexador"] == "tjsp_tabela_pratica"
    assert parcela["correcao"]["valor_corrigido"] > parcela["principal"]
    assert parcela["juros"]["aplicado"] is True
    assert parcela["total"] > parcela["principal"]
    chaves_bases = {b["key"] for b in body["bases"]}
    assert "tjsp_tabela_pratica" in chaves_bases
    assert "taxa_legal" in chaves_bases
    assert "salario_minimo" in chaves_bases


def test_post_parcelas_manuais(client: TestClient) -> None:
    payload = {
        "tipo": "parcelas",
        "titulo": "Cobrança manual",
        "data_base": "2026-08-31",
        "parcelas": [
            {
                "numero": 1,
                "vencimento": "2024-07-10",
                "principal": "1000.00",
                "descricao": "parcela única",
                "pagamentos": [{"data": "2026-01-10", "valor": "400.00"}],
            }
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["tipo"] == "parcelas"
    assert body["resumo"]["qtd_parcelas"] == 1
    parcela = body["parcelas"][0]
    assert parcela["numero"] == 1
    assert parcela["principal"] == "1000.00"
    assert parcela["competencia"] == "2024-07"
    assert parcela["total_pago"] == "400.00"
    assert parcela["saldo"] == "600.00"
    assert parcela["salario_minimo"] is None


def test_get_calculo_por_codigo(client: TestClient) -> None:
    criado = client.post("/api/calculos", json=_payload_alimentos()).json()
    codigo = criado["codigo"]
    response = client.get(f"/api/calculos/{codigo}")
    assert response.status_code == 200
    body = response.json()
    assert body["codigo"] == codigo
    assert body["resumo"] == criado["resumo"]
    assert body["parcelas"] == criado["parcelas"]
    assert body["bases"] == criado["bases"]
    assert body["titulo"] == "Pensão alimentícia"


def test_get_calculo_inexistente_retorna_404(client: TestClient) -> None:
    response = client.get("/api/calculos/VEC-2026-999999")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["erro"] == "nao_encontrado"


def test_listar_calculos_inclui_novo_registro(client: TestClient) -> None:
    criado = client.post("/api/calculos", json=_payload_alimentos()).json()
    response = client.get("/api/calculos")
    assert response.status_code == 200
    linhas = response.json()
    assert len(linhas) == 1
    assert linhas[0]["codigo"] == criado["codigo"]
    assert linhas[0]["tipo"] == "alimentos"
    assert linhas[0]["processo"] == "0001234-56.2021.8.26.0100"


def test_codigos_sequenciais_distintos(client: TestClient) -> None:
    primeiro = client.post("/api/calculos", json=_payload_alimentos()).json()
    segundo = client.post(
        "/api/calculos",
        json=_payload_alimentos(titulo="Segundo cálculo"),
    ).json()
    assert primeiro["codigo"] != segundo["codigo"]
    assert primeiro["codigo"].endswith("000001")
    assert segundo["codigo"].endswith("000002")


def test_post_sem_alimentos_no_tipo_alimentos_422(client: TestClient) -> None:
    payload = _payload_alimentos()
    payload["alimentos"] = None
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    assert response.json()["erro"] == "validacao"


def test_post_periodo_fora_da_cobertura_422(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/1993",
                    "fim": "12/1993",
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "12/1993",
        }
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["erro"] == "cobertura_insuficiente"
    assert body["indexador"] == "Salário mínimo"


def test_post_pagamento_alimentos_sem_competencia_422(client: TestClient) -> None:
    payload = _payload_alimentos(
        pagamentos=[{"data": "2026-01-10", "valor": "10.00"}]
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    assert response.json()["erro"] == "validacao"


def test_post_payload_invalido_422(client: TestClient) -> None:
    response = client.post("/api/calculos", json={"tipo": "desconhecido", "data_base": "2026-08-31"})
    assert response.status_code == 422


def test_resultado_preserva_metadados_para_relatorio(client: TestClient) -> None:
    payload = _payload_alimentos(
        pagamentos=[{"competencia": "2021-01", "data": "2026-03-10", "valor": "50.00"}],
        correcao={"aplicar": False},
        juros={"aplicar": False},
    )
    body = client.post("/api/calculos", json=payload).json()
    parcela = body["parcelas"][0]
    for campo in (
        "competencia",
        "salario_minimo",
        "percentual",
        "principal",
        "pagamentos",
        "saldo",
        "correcao",
        "juros",
        "total",
    ):
        assert campo in parcela
    assert parcela["competencia_rotulo"] == "01/2021"
    assert parcela["origem"] == "30% do salário mínimo"
    assert body["payload"]["alimentos"]["regras"][0]["percentual"] == "0.30"
    assert body["data_base"] == "2026-08-31"
