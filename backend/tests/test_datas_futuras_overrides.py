from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db
from app.engine.memoria import ESQUEMA_MEMORIA
from app.indexers.overrides import limpar_overrides_ativos
from app.main import create_app
from app.models.entities import IndexerOverride


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    limpar_overrides_ativos()
    db.reset()


def test_cobertura_oficial_tjsp(client: TestClient) -> None:
    body = client.get("/api/indexers/tjsp_tabela_pratica/cobertura").json()
    assert body["key"] == "tjsp_tabela_pratica"
    assert body["oficial"]["fim"] == "2026-09"
    assert body["oficial"]["version"] == "2026.09"
    assert body["manual"] == []
    assert body["cobertura_efetiva"]["fim"] == "2026-09"
    assert body["cobertura_efetiva"]["inclui_manual"] is False


def test_cadastro_manual_preenche_futuro_fora_da_oficial(client: TestClient) -> None:
    payload = {
        "competencia": "2026-10",
        "valor": "1.0123",
        "fonte": "Diário Oficial manual",
        "observacao": "vigência a partir de out/2026",
    }
    response = client.post("/api/indexers/tjsp_tabela_pratica/overrides", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "tjsp_tabela_pratica"
    assert body["competencia"] == "2026-10"
    assert float(body["valor"]) == 1.0123
    assert body["fonte"] == "Diário Oficial manual"

    cobertura = client.get("/api/indexers/tjsp_tabela_pratica/cobertura").json()
    assert cobertura["manual"][0]["competencia"] == "2026-10"
    assert cobertura["cobertura_efetiva"]["fim"] == "2026-10"
    assert cobertura["cobertura_efetiva"]["inclui_manual"] is True
    assert cobertura["oficial"]["fim"] == "2026-09"

    lista = client.get("/api/indexers/tjsp_tabela_pratica/overrides").json()
    assert len(lista["overrides"]) == 1


def test_cadastro_manual_nao_substitui_valor_oficial(client: TestClient) -> None:
    response = client.post(
        "/api/indexers/tjsp_tabela_pratica/overrides",
        json={
            "competencia": "2026-08",
            "valor": "9.99",
            "fonte": "tentativa de substituição",
        },
    )
    assert response.status_code == 422
    assert "não substitui histórico oficial" in response.json()["mensagem"]


def test_cadastro_manual_duplicado_e_rejeitado(client: TestClient) -> None:
    payload = {
        "competencia": "2027-01",
        "valor": "1.02",
        "fonte": "BCB",
    }
    assert client.post("/api/indexers/taxa_legal/overrides", json=payload).status_code == 201
    segundo = client.post("/api/indexers/taxa_legal/overrides", json=payload)
    assert segundo.status_code == 422
    assert "já existe cadastro manual" in segundo.json()["mensagem"]


def test_cadastro_manual_exige_fonte(client: TestClient) -> None:
    response = client.post(
        "/api/indexers/taxa_legal/overrides",
        json={"competencia": "2027-02", "valor": "1.0", "fonte": "  "},
    )
    assert response.status_code == 422


def test_sem_override_cobertura_futura_retorna_coverage_error(client: TestClient) -> None:
    payload = {
        "tipo": "atualizacao",
        "titulo": "Atualização futura",
        "data_base": "2026-10-31",
        "valor_base": {"valor": "10000.00", "data_base": "2024-01-15"},
        "correcao": {"aplicar": True, "indexador": "tjsp_tabela_pratica"},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["erro"] == "cobertura_insuficiente"
    assert body["indexador"] == "Tabela Prática TJSP"
    assert "09/2026" in body["mensagem"] or body["cobertura"]["fim"] == "09/2026"


def test_atualizacao_com_override_manual(client: TestClient) -> None:
    assert (
        client.post(
            "/api/indexers/tjsp_tabela_pratica/overrides",
            json={
                "competencia": "2026-10",
                "valor": "8.620000",
                "fonte": "Ata de vigência futura",
                "observacao": "continuação da série acumulada após 09/2026",
            },
        ).status_code
        == 201
    )
    payload = {
        "tipo": "atualizacao",
        "titulo": "Valor da causa",
        "processo": "000999-00.2024.8.26.0100",
        "data_base": "2026-10-31",
        "valor_base": {
            "valor": "10000.00",
            "data_base": "2024-01-15",
            "descricao": "valor da causa",
        },
        "correcao": {"aplicar": True, "indexador": "tjsp_tabela_pratica"},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["tipo"] == "atualizacao"
    memoria = body["memoria"]
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    atualizacao = memoria["atualizacao"]
    assert atualizacao["valor_original"] == "10000.00"
    assert atualizacao["data_base"] == "2024-01-15"
    assert atualizacao["data_final"] == "2026-10-31"
    assert atualizacao["indexador"] == "tjsp_tabela_pratica"
    assert atualizacao["fator_inicial"] is not None
    assert atualizacao["fator_final"] == "8.620000"
    assert atualizacao["razao"] is not None
    assert float(atualizacao["valor_corrigido"]) > 10000.0
    assert atualizacao["valor_atualizado"] == body["parcelas"][0]["total"]
    assert any(
        o["key"] == "tjsp_tabela_pratica" and o["competencia"] == "2026-10"
        for o in memoria["overrides_utilizados"]
    )
    bases = {b["key"]: b for b in memoria["bases"]}
    assert "tjsp_tabela_pratica" in bases
    assert bases["tjsp_tabela_pratica"]["versao"] == "2026.09"


def test_atualizacao_sem_data_final_usa_data_base_do_payload(client: TestClient) -> None:
    payload = {
        "tipo": "atualizacao",
        "data_base": "2026-08-31",
        "valor_base": {"valor": "5000.00", "data_base": "2023-06-01"},
        "correcao": {"aplicar": True},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    body = client.post("/api/calculos", json=payload).json()
    atualizacao = body["memoria"]["atualizacao"]
    assert atualizacao["data_final"] == "2026-08-31"
    assert float(atualizacao["valor_corrigido"]) > 5000.0


def test_atualizacao_rejeita_data_final_anterior(client: TestClient) -> None:
    payload = {
        "tipo": "atualizacao",
        "data_base": "2020-01-01",
        "valor_base": {"valor": "1000.00", "data_base": "2024-01-01"},
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    assert "anterior" in response.json()["mensagem"]


def test_alimentos_continua_funcionando_com_memoria_aditiva(client: TestClient) -> None:
    payload = {
        "tipo": "alimentos",
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
        },
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    body = client.post("/api/calculos", json=payload).json()
    assert body["resumo"]["qtd_parcelas"] == 12
    memoria = body["memoria"]
    assert memoria["atualizacao"] is None
    assert memoria["overrides_utilizados"] == []
    assert memoria["parcelas"][0]["principal"] == "330.00"


def test_export_continua_valido_com_memoria_1_1(client: TestClient) -> None:
    payload = {
        "tipo": "parcelas",
        "data_base": "2026-08-31",
        "parcelas": [
            {"numero": 1, "vencimento": "2024-07-10", "principal": "1000.00"}
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    codigo = client.post("/api/calculos", json=payload).json()["codigo"]
    pdf = client.get(f"/api/calculos/{codigo}/pdf")
    xlsx = client.get(f"/api/calculos/{codigo}/xlsx")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"


def test_overrides_nao_vazam_entre_calculos(client: TestClient) -> None:
    assert (
        client.post(
            "/api/indexers/taxa_legal/overrides",
            json={"competencia": "2027-03", "valor": "1.5", "fonte": "manual"},
        ).status_code
        == 201
    )
    with db.session_scope() as session:
        registros = session.scalars(select(IndexerOverride)).all()
        assert len(registros) == 1
    limpar_overrides_ativos()
    from app.indexers.overrides import override_ativo
    from app.core.competencia import Competencia

    assert override_ativo("taxa_legal", Competencia(2027, 3)) is None
