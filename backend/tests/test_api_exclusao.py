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


def _payload(**kwargs) -> dict:
    base = {
        "tipo": "parcelas",
        "titulo": "Cálculo para excluir",
        "processo": "0001234-56.2021.8.26.0100",
        "parte": "Autor",
        "data_base": "2026-08-31",
        "verbas": [
            {
                "nome": "Condenação",
                "valor": "30018.44",
                "data_base": "2025-02-12",
                "descricao": "Valor da causa",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2025-02-12",
                    "termo_final": "2026-08",
                },
                "juros": {"aplicar": False},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [],
            }
        ],
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
    }
    base.update(kwargs)
    return base


def test_delete_calculo_por_codigo(client: TestClient) -> None:
    codigo = client.post("/api/calculos", json=_payload()).json()["codigo"]

    response = client.delete(f"/api/calculos/{codigo}")

    assert response.status_code == 204
    assert client.get("/api/calculos").json() == []
    assert client.get(f"/api/calculos/{codigo}").status_code == 404


def test_delete_calculo_inexistente_404(client: TestClient) -> None:
    response = client.delete("/api/calculos/VEC-2026-999999")
    assert response.status_code == 404
    assert response.json()["detail"]["erro"] == "nao_encontrado"


def test_delete_calculos_remove_apenas_os_cadastrados(client: TestClient) -> None:
    primeiro = client.post("/api/calculos", json=_payload()).json()["codigo"]
    segundo = client.post("/api/calculos", json=_payload(titulo="Outro")).json()["codigo"]

    response = client.delete("/api/calculos")

    assert response.status_code == 200
    assert response.json() == {"excluidos": 2}
    assert client.get("/api/calculos").json() == []
    assert client.get(f"/api/calculos/{primeiro}").status_code == 404
    assert client.get(f"/api/calculos/{segundo}").status_code == 404


def test_delete_sem_registros_retorna_zero(client: TestClient) -> None:
    response = client.delete("/api/calculos")
    assert response.status_code == 200
    assert response.json() == {"excluidos": 0}


def test_verba_com_correcao_e_sem_juros_eh_gerada_normalmente(client: TestClient) -> None:
    """Exemplo real: R$ 30.018,44, correção desde 12/02/2025, juros desativados."""
    payload = _payload(
        verbas=[
            {
                "nome": "Condenação",
                "valor": "30018.44",
                "data_base": "2025-02-12",
                "descricao": "Valor da causa",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2025-02-12",
                    "termo_final": "2026-08",
                },
                "juros": {"aplicar": False, "inicio": None},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [],
            }
        ]
    )

    response = client.post("/api/calculos", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["resumo"]["qtd_parcelas"] == 1
    parcela = body["parcelas"][0]
    assert parcela["principal"] == "30018.44"
    assert parcela["correcao"]["aplicado"] is True
    assert parcela["juros"]["aplicado"] is False
    assert parcela["juros"]["juros"] == "0.00"
