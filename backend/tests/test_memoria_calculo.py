from __future__ import annotations

import json

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
        "pagamentos": [
            {
                "competencia": "2021-01",
                "data": "2026-01-10",
                "valor": "100.00",
                "descricao": "depósito",
            }
        ],
    }
    base.update(kwargs)
    return base


def test_memoria_presente_no_post_e_preserva_valores(client: TestClient) -> None:
    response = client.post("/api/calculos", json=_payload_alimentos())
    assert response.status_code == 201
    body = response.json()
    memoria = body["memoria"]
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    assert memoria["codigo"] == body["codigo"]
    assert memoria["tipo"] == "alimentos"
    assert memoria["identificacao"]["app_name"] == "Very Easy Calc"
    assert memoria["identificacao"]["app_version"] == "1.0.0"
    assert memoria["identificacao"]["data_base"] == "2026-08-31"
    assert memoria["identificacao"]["titulo"] == "Pensão alimentícia"
    assert memoria["identificacao"]["processo"] == "0001234-56.2021.8.26.0100"
    assert memoria["identificacao"]["data_geracao"]
    assert memoria["resumo"] == body["resumo"]
    assert memoria["parcelas"][0]["principal"] == body["parcelas"][0]["principal"] == "330.00"
    assert memoria["parcelas"][0]["saldo"] == "230.00"
    assert memoria["parcelas"][0]["total_pago"] == "100.00"
    assert memoria["parcelas"][0]["diferenca"] == "230.00"
    assert memoria["parcelas"][0]["pagamentos"][0]["valor"] == "100.00"


def test_memoria_registra_criterios_e_regra_de_alimentos(client: TestClient) -> None:
    memoria = client.post("/api/calculos", json=_payload_alimentos()).json()["memoria"]
    criterios = memoria["criterios"]
    assert criterios["data_base"] == "2026-08-31"
    assert criterios["correcao"]["aplicar"] is False
    assert criterios["juros"]["aplicar"] is False
    assert criterios["multa"]["aplicar"] is False
    assert criterios["honorarios"]["aplicar"] is False
    assert criterios["alimentos"]["ate"] == "12/2021"
    assert criterios["alimentos"]["dia_vencimento"] == 10
    assert criterios["alimentos"]["regras"][0]["percentual"] == "0.30"
    assert criterios["alimentos"]["regras"][0]["tipo"] == "salario_minimo"
    assert criterios["pagamentos_informados"][0]["competencia"] == "2021-01"

    parcela = memoria["parcelas"][0]
    assert parcela["regra"]["tipo"] == "salario_minimo"
    assert parcela["regra"]["origem"] == "30% do salário mínimo"
    assert parcela["regra"]["detalhe"] == "30% × R$ 1.100,00"
    assert parcela["regra"]["salario_minimo"] == "1100.00"
    assert parcela["regra"]["percentual"] == "0.30"
    assert parcela["salario_minimo"] == "1100.00"
    assert parcela["percentual"] == "0.30"


def test_memoria_preserva_bases_versionadas(client: TestClient) -> None:
    memoria = client.post("/api/calculos", json=_payload_alimentos()).json()["memoria"]
    assert len(memoria["bases"]) >= 1
    base_sm = next(b for b in memoria["bases"] if b["key"] == "salario_minimo")
    assert base_sm["versao"] == "2026.12"
    assert base_sm["papel"] == "Composição do principal"
    assert base_sm["cobertura"]


def test_memoria_altera_salario_minimo_por_competencia(client: TestClient) -> None:
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
        },
        pagamentos=[],
    )
    memoria = client.post("/api/calculos", json=payload).json()["memoria"]
    por_comp = {p["competencia"]: p for p in memoria["parcelas"]}
    assert por_comp["2023-01"]["salario_minimo"] == "1302.00"
    assert por_comp["2023-01"]["principal"] == "390.60"
    assert por_comp["2023-05"]["salario_minimo"] == "1320.00"
    assert por_comp["2023-05"]["principal"] == "396.00"
    assert por_comp["2023-05"]["regra"]["detalhe"] == "30% × R$ 1.320,00"


def test_memoria_com_correcao_e_juros_nao_recalcula(client: TestClient) -> None:
    payload = _payload_alimentos(
        correcao={"aplicar": True, "indexador": "tjsp_tabela_pratica"},
        juros={"aplicar": True, "modalidade": "taxa_legal"},
        pagamentos=[],
    )
    body = client.post("/api/calculos", json=payload).json()
    memoria = body["memoria"]
    parcela_resposta = body["parcelas"][0]
    parcela_memoria = memoria["parcelas"][0]

    assert parcela_memoria["principal"] == parcela_resposta["principal"] == "330.00"
    assert parcela_memoria["correcao"]["valor_corrigido"] == parcela_resposta["correcao"][
        "valor_corrigido"
    ]
    assert parcela_memoria["juros"]["juros"] == parcela_resposta["juros"]["juros"]
    assert parcela_memoria["total"] == parcela_resposta["total"]
    assert parcela_memoria["saldo"] == parcela_resposta["saldo"]
    assert memoria["resumo"]["total"] == body["resumo"]["total"]
    assert memoria["criterios"]["correcao"]["aplicar"] is True
    assert memoria["criterios"]["juros"]["modalidade"] == "taxa_legal"

    chaves = {b["key"] for b in memoria["bases"]}
    assert "tjsp_tabela_pratica" in chaves
    assert "taxa_legal" in chaves
    assert "salario_minimo" in chaves


def test_memoria_parcelas_manuais_sem_regra_de_alimentos(client: TestClient) -> None:
    payload = {
        "tipo": "parcelas",
        "titulo": "Manual",
        "data_base": "2026-08-31",
        "parcelas": [
            {
                "numero": 1,
                "vencimento": "2024-07-10",
                "principal": "1000.00",
                "pagamentos": [{"data": "2026-01-10", "valor": "400.00"}],
            }
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    memoria = client.post("/api/calculos", json=payload).json()["memoria"]
    assert memoria["tipo"] == "parcelas"
    assert memoria["criterios"]["alimentos"] is None
    parcela = memoria["parcelas"][0]
    assert parcela["regra"] is None
    assert parcela["principal"] == "1000.00"
    assert parcela["saldo"] == "600.00"
    assert parcela["competencia"] == "2024-07"
    assert parcela["vencimento"] == "2024-07-10"


def test_get_memoria_endpoint(client: TestClient) -> None:
    criado = client.post("/api/calculos", json=_payload_alimentos()).json()
    codigo = criado["codigo"]
    response = client.get(f"/api/calculos/{codigo}/memoria")
    assert response.status_code == 200
    memoria = response.json()
    assert memoria["codigo"] == codigo
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    assert memoria["resumo"] == criado["resumo"]
    assert memoria["parcelas"] == criado["memoria"]["parcelas"]
    assert memoria["criterios"] == criado["memoria"]["criterios"]


def test_get_calculo_inclui_memoria(client: TestClient) -> None:
    criado = client.post("/api/calculos", json=_payload_alimentos()).json()
    body = client.get(f"/api/calculos/{criado['codigo']}").json()
    assert body["memoria"]["codigo"] == criado["codigo"]
    assert body["memoria"]["parcelas"] == criado["memoria"]["parcelas"]


def test_get_memoria_inexistente_404(client: TestClient) -> None:
    response = client.get("/api/calculos/VEC-2026-000099/memoria")
    assert response.status_code == 404


def test_memoria_persistida_no_banco(client: TestClient) -> None:
    criado = client.post("/api/calculos", json=_payload_alimentos()).json()
    with db.session_scope() as session:
        from sqlalchemy import select

        from app.models.entities import Calculo

        registro = session.scalar(
            select(Calculo).where(Calculo.codigo == criado["codigo"])
        )
        assert registro is not None
        memoria_db = json.loads(registro.memoria_json)
        assert memoria_db["codigo"] == criado["codigo"]
        assert memoria_db["parcelas"][0]["principal"] == "330.00"
        assert memoria_db["criterios"]["alimentos"]["ate"] == "12/2021"


def test_memoria_mantem_memoria_de_multa_e_honorarios(client: TestClient) -> None:
    payload = _payload_alimentos(
        correcao={"aplicar": False},
        juros={"aplicar": False},
        multa={"aplicar": True, "percentual": "0.02"},
        honorarios={"aplicar": True, "percentual": "0.10", "base": "principal"},
        pagamentos=[],
    )
    body = client.post("/api/calculos", json=payload).json()
    memoria = body["memoria"]
    parcela = memoria["parcelas"][0]
    assert parcela["multa"]["aplicado"] is True
    assert parcela["multa"]["valor"] == "6.60"
    assert parcela["honorarios"]["aplicado"] is True
    assert parcela["honorarios"]["valor"] == "33.00"
    assert parcela["total"] == body["parcelas"][0]["total"]
    assert memoria["criterios"]["multa"]["percentual"] == "0.02"
    assert memoria["criterios"]["honorarios"]["percentual"] == "0.10"
