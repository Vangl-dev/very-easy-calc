from __future__ import annotations

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


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Very Easy Calc"
    assert body["version"] == "1.0.0"


def test_indexers_listados_e_versionados(client: TestClient) -> None:
    response = client.get("/api/indexers")
    assert response.status_code == 200
    body = response.json()
    assert body["app_version"] == "1.0.0"
    assert len(body["indexers"]) == 3
    item = next(i for i in body["indexers"] if i["key"] == "tjsp_tabela_pratica")
    assert item["version"] == "2026.08"
    assert item["registrada"] is True
    assert item["cobertura"] == {"inicio": "01/1992", "fim": "08/2026", "total": 416}
    assert item["kind"] == "correcao"
    assert item["unidade"] == "fator acumulado"


def test_calculos_inicialmente_vazio(client: TestClient) -> None:
    response = client.get("/api/calculos")
    assert response.status_code == 200
    assert response.json() == []
