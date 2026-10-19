from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import db
from app.indexers import obter
from app.main import create_app

DATA_FINAL = "2026-09-30"
AJUIZAMENTO = "2022-06-15"
CITACAO = "2022-09-10"
LIMITE_REGIME_1 = "2024-08-27"
INICIO_REGIME_2 = "2024-08-28"


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


def _verba(alteracoes: dict | None = None) -> dict:
    verba = {
        "id": "principal",
        "tipo": "valor",
        "nome": "Condenação",
        "valor": "30018.44",
        "data_base": AJUIZAMENTO,
        "correcao": {
            "aplicar": True,
            "indexador": "tjsp_tabela_pratica",
            "termo_inicial": AJUIZAMENTO,
        },
        "juros": {
            "aplicar": True,
            "modalidade": "taxa_legal",
            "inicio": CITACAO,
            "base": "corrigido",
        },
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "regimes": [],
    }
    verba.update(alteracoes or {})
    return verba


def _payload(verbas: list[dict]) -> dict:
    return {
        "tipo": "parcelas",
        "titulo": "Regimes de atualização",
        "processo": "0000000-00.2022.8.26.0000",
        "parte": "Autor",
        "data_base": DATA_FINAL,
        "verbas": verbas,
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [],
    }


def _regimes() -> list[dict]:
    """Regime 1 até 27/08/2024 (TJSP + 1% a.m.) e regime 2 desde 28/08/2024 (SELIC)."""
    return [
        {
            "data_inicio": None,
            "data_fim": LIMITE_REGIME_1,
            "correcao": "tjsp_tabela_pratica",
            "juros": {
                "aplicar": True,
                "modalidade": "fixa",
                "taxa": "0.01",
                "unidade": "mensal",
                "base": "corrigido",
            },
            "criterio": None,
        },
        {
            "data_inicio": INICIO_REGIME_2,
            "data_fim": None,
            "correcao": "selic",
            "juros": {
                "aplicar": True,
                "modalidade": "selic",
                "base": "corrigido",
            },
            "criterio": "selic",
        },
    ]


def _payload_regimes() -> dict:
    return _payload([_verba({"regimes": _regimes()})])


def _post(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_calculo_simples_continua_funcionando(client: TestClient) -> None:
    body = _post(client, _payload([_verba()]))
    parcela = body["parcelas"][0]

    assert parcela["principal"] == "30018.44"
    assert parcela["correcao"]["aplicado"] is True
    assert parcela["correcao"]["segmentos"] == []
    assert parcela["correcao"]["indexador"] == "tjsp_tabela_pratica"
    assert parcela["juros"]["aplicado"] is True
    assert parcela["juros"]["modalidade"] == "taxa_legal"
    assert parcela["juros"]["indexador"] == "taxa_legal"
    assert float(body["resumo"]["total"]) > 30018.44


def test_verba_sem_correcao_continua_funcionando(client: TestClient) -> None:
    body = _post(
        client,
        _payload([_verba({"correcao": {"aplicar": False}})]),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["aplicado"] is False
    assert parcela["correcao"]["correcao"] == "0.00"
    assert parcela["juros"]["aplicado"] is True
    assert parcela["juros"]["indexador"] == "taxa_legal"
    assert float(parcela["total"]) == pytest.approx(
        30018.44 + float(parcela["juros"]["juros"]), abs=0.05
    )


def test_verba_sem_juros_continua_funcionando(client: TestClient) -> None:
    body = _post(
        client,
        _payload([_verba({"juros": {"aplicar": False, "modalidade": "taxa_legal"}})]),
    )
    parcela = body["parcelas"][0]

    assert parcela["juros"]["aplicado"] is False
    assert parcela["juros"]["juros"] == "0.00"
    assert parcela["correcao"]["aplicado"] is True


def test_verba_sem_correcao_e_sem_juros_continua_funcionando(
    client: TestClient,
) -> None:
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "correcao": {"aplicar": False},
                        "juros": {"aplicar": False, "modalidade": "taxa_legal"},
                    }
                )
            ]
        ),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["aplicado"] is False
    assert parcela["juros"]["aplicado"] is False
    assert parcela["total"] == "30018.44"
    assert body["resumo"]["total"] == "30018.44"


def test_dois_regimes_consecutivos_sao_aceitos(client: TestClient) -> None:
    body = _post(client, _payload_regimes())
    parcela = body["parcelas"][0]

    assert parcela["principal"] == "30018.44"
    assert parcela["correcao"]["aplicado"] is True
    assert parcela["juros"]["aplicado"] is True
    assert float(body["resumo"]["total"]) > 30018.44


def test_periodo_e_dividido_na_data_de_mudanca(client: TestClient) -> None:
    body = _post(client, _payload_regimes())
    parcela = body["parcelas"][0]

    segmentos = parcela["correcao"]["segmentos"]
    assert len(segmentos) == 2
    assert segmentos[0]["indexador"] == "tjsp_tabela_pratica"
    assert segmentos[0]["termo_inicial"] == "2022-06"
    # a troca acontece em 28/08/2024: a competência de referência é 2024-08 e
    # os dois segmentos encerram/começam nela, para o produto não perder a
    # transição entre a Tabela Prática e a SELIC
    assert segmentos[0]["termo_final"] == "2024-08"
    assert segmentos[1]["indexador"] == "selic"
    assert segmentos[1]["termo_inicial"] == "2024-08"
    assert segmentos[1]["termo_final"] == "2026-09"

    trechos = parcela["juros"]["trechos"]
    assert len(trechos) == 2
    assert trechos[0]["inicio"] == CITACAO
    assert trechos[0]["fim"] == LIMITE_REGIME_1
    assert trechos[1]["inicio"] == INICIO_REGIME_2
    assert trechos[1]["fim"] == DATA_FINAL
    assert (
        float(trechos[0]["valor"]) + float(trechos[1]["valor"])
        == pytest.approx(float(parcela["juros"]["juros"]), abs=0.05)
    )


def test_selic_e_identificada_como_selic_e_nao_como_taxa_legal(
    client: TestClient,
) -> None:
    body = _post(client, _payload_regimes())
    parcela = body["parcelas"][0]
    juros = parcela["juros"]

    assert juros["indexador"] == "selic"
    assert juros["indexador_fonte"] == "Banco Central do Brasil"
    assert parcela["correcao"]["indexador"] == "selic"

    rotulos = [t["rotulo"] for t in juros["trechos"]]
    assert "SELIC" in rotulos
    assert all("Taxa Legal" not in rotulo for rotulo in rotulos)
    assert all("Taxa Legal" not in (t["taxa_rotulo"] or "") for t in juros["trechos"])

    bases = {b["key"]: b for b in body["bases"]}
    assert bases["selic"]["nome"] == "SELIC (BCB)"
    assert "taxa_legal" not in bases


def test_taxa_legal_existente_continua_funcionando(client: TestClient) -> None:
    body = _post(client, _payload([_verba()]))
    juros = body["parcelas"][0]["juros"]

    assert juros["indexador"] == "taxa_legal"
    assert juros["indexador_fonte"] == "Banco Central do Brasil"
    rotulos = [t["rotulo"] for t in juros["trechos"]]
    assert "Taxa Legal, art. 406 do CC" in rotulos
    assert "SELIC" not in rotulos

    bases = {b["key"]: b for b in body["bases"]}
    assert bases["taxa_legal"]["nome"] == "Taxa Legal (BCB SGS 29543)"
    assert "selic" not in bases


def test_memoria_registra_os_dois_regimes(client: TestClient) -> None:
    body = _post(client, _payload_regimes())
    memoria = body["memoria"]

    regimes = memoria["verbas"][0]["regimes"]
    assert len(regimes) == 2
    assert regimes[0]["data_inicio"] is None
    assert regimes[0]["data_fim"] == LIMITE_REGIME_1
    assert regimes[0]["correcao"] == "tjsp_tabela_pratica"
    assert regimes[0]["juros"]["modalidade"] == "fixa"
    assert regimes[0]["juros"]["taxa"] == "0.01"
    assert regimes[1]["data_inicio"] == INICIO_REGIME_2
    assert regimes[1]["data_fim"] is None
    assert regimes[1]["criterio"] == "selic"
    assert regimes[1]["correcao"] == "selic"
    assert regimes[1]["juros"]["modalidade"] == "selic"
    assert regimes[1]["juros"]["taxa"] is None

    assert memoria["criterios"]["verbas"][0]["regimes"][1]["criterio"] == "selic"

    parcela = memoria["parcelas"][0]
    assert [s["indexador"] for s in parcela["correcao"]["segmentos"]] == [
        "tjsp_tabela_pratica",
        "selic",
    ]
    assert [t["rotulo"] for t in parcela["juros"]["trechos"]] == [
        "1% ao mês",
        "SELIC",
    ]


def test_caso_funcional_dois_regimes(client: TestClient) -> None:
    """R$ 30.018,44 — TJSP + 1% a.m. até 27/08/2024 e SELIC a partir de 28/08/2024."""
    body = _post(client, _payload_regimes())
    parcela = body["parcelas"][0]

    assert body["data_base"] == DATA_FINAL
    assert parcela["principal"] == "30018.44"

    # a sentença manda SELIC quando correção e juros incidem conjuntamente
    assert parcela["correcao"]["indexador"] == "selic"
    assert parcela["juros"]["indexador"] == "selic"
    assert parcela["juros"]["modalidade"] == "regimes"

    # não sai TJSP + Taxa Legal no mesmo trecho final
    ultimo_segmento = parcela["correcao"]["segmentos"][-1]
    assert ultimo_segmento["indexador"] == "selic"
    ultimo_trecho = parcela["juros"]["trechos"][-1]
    assert ultimo_trecho["rotulo"] == "SELIC"
    assert "Taxa Legal" not in ultimo_trecho["taxa_rotulo"]

    resumo = body["resumo"]
    assert float(resumo["principal"]) == pytest.approx(30018.44)
    assert float(resumo["correcao"]) > 0
    assert float(resumo["juros"]) > 0
    assert float(resumo["total"]) == pytest.approx(
        30018.44 + float(resumo["correcao"]) + float(resumo["juros"]),
        abs=0.05,
    )
    assert body["avisos"] == []


def test_segmentos_consecutivos_nao_deixam_competencia_sem_atualizacao(
    client: TestClient,
) -> None:
    """Os dois regimes encerram/começam na mesma competência de referência."""
    body = _post(client, _payload_regimes())
    segmentos = body["parcelas"][0]["correcao"]["segmentos"]

    assert len(segmentos) == 2
    assert segmentos[0]["termo_final"] == segmentos[1]["termo_inicial"]

    tjsp = obter("tjsp_tabela_pratica")
    selic = obter("selic")
    encadeado = (tjsp.valor("2024-08") / tjsp.valor("2022-06")) * (
        selic.valor("2026-09") / selic.valor("2024-08")
    )
    assert Decimal(body["parcelas"][0]["correcao"]["razao"]) == encadeado

    # com a fronteira em 2024-07 a transição jul→ago/2024 ficaria de fora
    com_lacuna = (tjsp.valor("2024-07") / tjsp.valor("2022-06")) * (
        selic.valor("2026-09") / selic.valor("2024-08")
    )
    assert Decimal(body["parcelas"][0]["correcao"]["razao"]) != com_lacuna


def test_regimes_com_datas_declaradas_em_meses_distintos_sao_encadeados(
    client: TestClient,
) -> None:
    """Mesmo com data_fim e data_inicio em meses diferentes não há buraco."""
    regimes = [
        {
            "data_inicio": None,
            "data_fim": "2023-12-31",
            "correcao": "tjsp_tabela_pratica",
            "juros": None,
            "criterio": None,
        },
        {
            "data_inicio": "2024-08-28",
            "data_fim": None,
            "correcao": "selic",
            "juros": None,
            "criterio": None,
        },
    ]
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "regimes": regimes,
                        "juros": {"aplicar": False, "modalidade": "taxa_legal"},
                    }
                )
            ]
        ),
    )
    segmentos = body["parcelas"][0]["correcao"]["segmentos"]
    assert [
        (s["termo_inicial"], s["termo_final"], s["indexador"]) for s in segmentos
    ] == [
        ("2022-06", "2024-08", "tjsp_tabela_pratica"),
        ("2024-08", "2026-09", "selic"),
    ]


def test_regimes_sobrepostos_continuam_sendo_rejeitados(client: TestClient) -> None:
    regimes = [
        {
            "data_inicio": None,
            "data_fim": "2024-08-27",
            "correcao": "tjsp_tabela_pratica",
            "juros": None,
            "criterio": None,
        },
        {
            "data_inicio": AJUIZAMENTO,
            "data_fim": None,
            "correcao": "selic",
            "juros": None,
            "criterio": None,
        },
    ]
    response = client.post(
        "/api/calculos",
        json=_payload(
            [
                _verba(
                    {
                        "regimes": regimes,
                        "juros": {"aplicar": False, "modalidade": "taxa_legal"},
                    }
                )
            ]
        ),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["erro"] == "validacao"
    assert "sobrepõem" in body["mensagem"]
