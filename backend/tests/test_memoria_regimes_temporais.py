from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import db
from app.engine.memoria import ESQUEMA_MEMORIA
from app.main import create_app

DATA_FINAL = "2026-09-30"
PRINCIPAL = "30018.44"


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
        "valor": PRINCIPAL,
        "data_base": "2025-02-12",
        "correcao": {
            "aplicar": True,
            "indexador": "tjsp_tabela_pratica",
            "termo_inicial": "2025-02-12",
        },
        "juros": {
            "aplicar": True,
            "modalidade": "taxa_legal",
            "inicio": "2025-03-31",
            "base": "corrigido",
        },
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "regimes": [],
    }
    verba.update(alteracoes or {})
    return verba


def _payload(verbas: list[dict], data_base: str = DATA_FINAL) -> dict:
    return {
        "tipo": "parcelas",
        "titulo": "Memória dos regimes temporais",
        "processo": "0000000-00.2025.8.26.0000",
        "parte": "Autor",
        "data_base": data_base,
        "verbas": verbas,
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [],
    }


def _post(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _caso_principal(client: TestClient) -> dict:
    return _post(client, _payload([_verba()]))


def _temporais(body: dict) -> dict:
    memoria = body["memoria"]
    parcela = memoria["parcelas"][0]
    assert "segmentos_temporais" in parcela, "memória sem segmentos temporais"
    return parcela["segmentos_temporais"]


def _correcoes(temporais: dict) -> list[dict]:
    return [s for s in temporais["segmentos"] if s["tipo"] == "correcao"]


def _juros_de(temporais: dict) -> list[dict]:
    return [s for s in temporais["segmentos"] if s["tipo"] == "juros"]


# 1 ---------------------------------------------------------------------------


def test_memoria_contem_os_dois_segmentos_do_caso_principal(client: TestClient) -> None:
    body = _caso_principal(client)
    temporais = _temporais(body)

    correcoes = _correcoes(temporais)
    assert len(correcoes) == 2
    assert [s["periodo"]["termo_inicial"] for s in correcoes] == ["2025-02", "2025-03"]
    assert [s["periodo"]["termo_final"] for s in correcoes] == ["2025-03", "2026-09"]
    assert [s["periodo"]["unidade"] for s in correcoes] == ["competencia"] * 2
    assert len(_juros_de(temporais)) == 1

    assert temporais["origem"] == "regime_automatico"
    assert body["memoria"]["esquema"] == ESQUEMA_MEMORIA
    assert body["resumo"]["total"] == "37028.53"


# 2 ---------------------------------------------------------------------------


def test_primeiro_segmento_identifica_ipca_ibge(client: TestClient) -> None:
    primeiro = _correcoes(_temporais(_caso_principal(client)))[0]

    assert primeiro["criterio"] == "somente_correcao"
    assert primeiro["indexador"] == "ipca"
    assert primeiro["serie"] == {
        "key": "ipca",
        "nome": "IPCA (IBGE)",
        "fonte": "IBGE",
        "versao": "2026.09",
    }
    assert primeiro["periodo"]["data_inicio"] == "2025-02-01"
    assert primeiro["periodo"]["data_fim"] == "2025-03-31"
    assert Decimal(primeiro["fator_inicial"]) == Decimal("7205.03")
    assert Decimal(primeiro["fator_final"]) == Decimal("7245.38")
    assert Decimal(primeiro["fator_acumulado"]) == (
        Decimal(primeiro["fator_final"]) / Decimal(primeiro["fator_inicial"])
    )
    assert primeiro["valor_base"] == PRINCIPAL
    assert "IPCA — IBGE" in primeiro["criterio_rotulo"]
    assert "Tabela Prática" not in json.dumps(_temporais(_caso_principal(client)))


# 3 ---------------------------------------------------------------------------


def test_segundo_segmento_identifica_selic_integral(client: TestClient) -> None:
    correcoes = _correcoes(_temporais(_caso_principal(client)))
    segundo = correcoes[1]
    trecho = _juros_de(_temporais(_caso_principal(client)))[0]

    assert segundo["criterio"] == "correcao_e_juros"
    assert segundo["indexador"] == "selic"
    assert segundo["serie"] == {
        "key": "selic",
        "nome": "SELIC (BCB)",
        "fonte": "Banco Central do Brasil",
        "versao": "2026.09",
    }
    assert Decimal(segundo["fator_inicial"]) == Decimal("1.29083439")
    assert Decimal(segundo["fator_final"]) == Decimal("1.58341029")
    assert Decimal(segundo["fator_acumulado"]) == (
        Decimal(segundo["fator_final"]) / Decimal(segundo["fator_inicial"])
    )
    assert segundo["valor_resultante"] == "37028.53"
    assert "SELIC integral" in segundo["criterio_rotulo"]

    assert "SELIC integral" in trecho["taxa_rotulo"]
    assert trecho["periodo"] == {
        "data_inicio": "2025-03-31",
        "data_fim": DATA_FINAL,
        "unidade": "data",
    }
    assert trecho["dias"] == 549


# 4 ---------------------------------------------------------------------------


def test_fronteira_compartilhada_fica_documentada(client: TestClient) -> None:
    temporais = _temporais(_caso_principal(client))
    correcoes = _correcoes(temporais)

    # a convenção explica que a razão do segundo começa no índice do primeiro
    assert "compartilham a mesma competência de referência" in temporais[
        "convencao"
    ]["fronteira_compartilhada"]
    assert correcoes[0]["periodo"]["termo_final"] == correcoes[1]["periodo"]["termo_inicial"]
    assert correcoes[0]["periodo"]["termo_final"] == "2025-03"

    # e o produto das razões é exatamente a razão total do motor
    produto = Decimal(1)
    for s in correcoes:
        produto *= Decimal(s["fator_acumulado"])
    razao_motor = Decimal(_caso_principal(client)["parcelas"][0]["correcao"]["razao"])
    assert produto == razao_motor


# 5 ---------------------------------------------------------------------------


def test_memoria_nao_soma_juros_novo_sobre_o_segmento_selic_integral(
    client: TestClient,
) -> None:
    body = _caso_principal(client)
    trecho = _juros_de(_temporais(body))[0]

    assert trecho["juros_incorporados"] is True
    assert trecho["valor_resultante"] == "0.00"
    assert _correcoes(_temporais(body))[1]["juros_incorporados"] is True
    assert "juros embutidos" in trecho["taxa_rotulo"]
    assert "selic_integral" in _temporais(body)["convencao"]

    # o total continua sendo principal + correção, sem juros em separado
    assert body["resumo"]["juros"] == "0.00"
    assert Decimal(body["resumo"]["total"]) == (
        Decimal(body["resumo"]["principal"]) + Decimal(body["resumo"]["correcao"])
    )


# 6 ---------------------------------------------------------------------------


def test_juros_isolados_mostram_selic_menos_ipca_ibge(client: TestClient) -> None:
    body = _post(
        client, _payload([_verba({"correcao": {"aplicar": False}})])
    )
    temporais = _temporais(body)
    trecho = _juros_de(temporais)[0]

    assert temporais["origem"] == "regime_automatico"
    assert trecho["criterio"] == "somente_juros"
    assert "SELIC − IPCA (IBGE)" in trecho["taxa_rotulo"]
    assert "Tabela Prática" not in trecho["taxa_rotulo"]
    assert trecho["piso_mensal_zero"] is True
    assert trecho["proporcional_aos_dias"] is True
    assert trecho["dias"] == 549
    assert Decimal(trecho["valor_resultante"]) == Decimal("4355.45")

    envolvidas = {s["key"]: s for s in trecho["series_envolvidas"]}
    assert set(envolvidas) == {"selic", "ipca"}
    assert envolvidas["selic"]["fonte"] == "Banco Central do Brasil"
    assert envolvidas["ipca"] == {
        "key": "ipca",
        "nome": "IPCA (IBGE)",
        "fonte": "IBGE",
        "versao": "2026.09",
    }
    assert "tjsp_tabela_pratica" not in envolvidas


# 7 ---------------------------------------------------------------------------


def test_fontes_e_versoes_correspondem_as_bases_do_motor(client: TestClient) -> None:
    body = _caso_principal(client)
    bases = {b["key"]: b for b in body["memoria"]["bases"]}
    temporais = _temporais(body)

    for segmento in temporais["segmentos"]:
        chave = segmento.get("indexador")
        if not chave:
            continue
        assert segmento["serie"]["nome"] == bases[chave]["nome"]
        assert segmento["serie"]["fonte"] == bases[chave]["fonte"]
        assert segmento["serie"]["versao"] == bases[chave]["versao"]

    assert set(bases) == {"ipca", "selic"}
    assert bases["ipca"]["fonte"] == "IBGE"
    assert bases["selic"]["fonte"] == "Banco Central do Brasil"


# 8 ---------------------------------------------------------------------------


def test_taxa_legal_continua_identificada_separadamente(client: TestClient) -> None:
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "juros": {
                            "aplicar": True,
                            "modalidade": "taxa_legal",
                            "inicio": "2024-03-15",
                            "base": "corrigido",
                        }
                    }
                )
            ]
        ),
    )
    memoria = body["memoria"]
    parcela = memoria["parcelas"][0]

    assert "segmentos_temporais" not in parcela
    assert "regime_temporal" not in parcela
    assert parcela["juros"]["modalidade"] == "taxa_legal"
    assert parcela["juros"]["indexador"] == "taxa_legal"
    assert parcela["juros"]["indexador_fonte"] == "Banco Central do Brasil"
    assert {b["key"] for b in memoria["bases"]} == {"tjsp_tabela_pratica", "taxa_legal"}


# 9 ---------------------------------------------------------------------------


def test_regimes_explicitos_continuam_representados(client: TestClient) -> None:
    regimes = [
        {
            "data_inicio": None,
            "data_fim": "2024-08-27",
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
            "data_inicio": "2024-08-28",
            "data_fim": None,
            "correcao": "selic",
            "juros": {"aplicar": True, "modalidade": "selic", "base": "corrigido"},
            "criterio": "selic",
        },
    ]
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "data_base": "2022-06-15",
                        "regimes": regimes,
                        "correcao": {
                            "aplicar": True,
                            "indexador": "tjsp_tabela_pratica",
                            "termo_inicial": "2022-06-15",
                        },
                        "juros": {
                            "aplicar": True,
                            "modalidade": "taxa_legal",
                            "inicio": "2022-09-10",
                            "base": "corrigido",
                        },
                    }
                )
            ]
        ),
    )
    memoria = body["memoria"]
    declarados = memoria["criterios"]["verbas"][0]["regimes"]
    assert len(declarados) == 2
    assert declarados[0]["correcao"] == "tjsp_tabela_pratica"
    assert declarados[1]["criterio"] == "selic"

    temporais = _temporais(body)
    assert temporais["origem"] == "segmentacao_da_verba"
    assert "regime_temporal" not in memoria["parcelas"][0]
    segmentos = _correcoes(temporais)
    assert [s["indexador"] for s in segmentos] == ["tjsp_tabela_pratica", "selic"]
    assert segmentos[0]["periodo"]["termo_final"] == segmentos[1]["periodo"]["termo_inicial"]


# 10 --------------------------------------------------------------------------


def _payload_alimentos() -> dict:
    return {
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


def test_alimentos_nao_sofre_alteracao_numerica(client: TestClient) -> None:
    body = _post(client, _payload_alimentos())
    memoria = body["memoria"]
    parcela = memoria["parcelas"][0]

    # valores travados pelos testes de memória existentes
    assert body["resumo"]["total"] == "3960.00"
    assert parcela["principal"] == "330.00"
    assert parcela["saldo"] == "230.00"
    assert parcela["total_pago"] == "100.00"
    assert parcela["diferenca"] == "230.00"
    assert parcela["regra"]["salario_minimo"] == "1100.00"

    # e a apresentação existente permanece, sem os novos blocos
    assert "segmentos_temporais" not in parcela
    assert "regime_temporal" not in parcela
    assert memoria["criterios"]["verbas"] == []


# 11 --------------------------------------------------------------------------


def test_verbas_derivadas_preservam_bases_e_totais(client: TestClient) -> None:
    payload = {
        "tipo": "parcelas",
        "titulo": "Verba derivada 12%",
        "processo": "0000000-00.2024.8.26.0000",
        "parte": "Autor",
        "data_base": DATA_FINAL,
        "verbas": [
            {
                "id": "causa",
                "tipo": "valor",
                "nome": "Valor da causa",
                "valor": "44000.00",
                "data_base": "2022-08-30",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2022-08",
                },
                "juros": {
                    "aplicar": True,
                    "modalidade": "taxa_legal",
                    "inicio": "2026-04-24",
                    "base": "corrigido",
                },
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
                "pagamentos": [],
            },
            {
                "id": "sucumbencia",
                "tipo": "percentual",
                "nome": "Honorários de sucumbência",
                "base_verba_id": "causa",
                "percentual": "0.12",
                "data_base": "2022-08-30",
                "correcao": {
                    "aplicar": True,
                    "indexador": "tjsp_tabela_pratica",
                    "termo_inicial": "2022-08",
                },
                "juros": {
                    "aplicar": True,
                    "modalidade": "taxa_legal",
                    "inicio": "2026-04-24",
                    "base": "corrigido",
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
        "pagamentos": [],
    }
    body = _post(client, payload)
    memoria = body["memoria"]

    derivada = memoria["verbas"][1]
    assert derivada["tipo"] == "percentual"
    assert derivada["base_verba_id"] == "causa"
    assert derivada["percentual"] == "0.12"
    assert derivada["valor"] == "5280.00"

    por_id = {p["verba"]["id"]: p for p in memoria["parcelas"]}
    assert Decimal(por_id["sucumbencia"]["principal"]) == (
        Decimal(por_id["causa"]["principal"]) * Decimal("0.12")
    ).quantize(Decimal("0.01"))
    assert memoria["resumo"]["total"] == body["resumo"]["total"]
    # sem regime automático, a apresentação segue a existente
    assert "segmentos_temporais" not in por_id["sucumbencia"]
    assert "segmentos_temporais" not in por_id["causa"]


# 12 --------------------------------------------------------------------------


def test_erros_de_cobertura_permanecem_explicitos(client: TestClient) -> None:
    response = client.post(
        "/api/calculos",
        json=_payload(
            [
                _verba(
                    {
                        "correcao": {
                            "aplicar": True,
                            "indexador": "ipca",
                            "termo_inicial": "1979-11",
                        },
                        "juros": {"aplicar": False, "modalidade": "taxa_legal"},
                    }
                )
            ]
        ),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["erro"] == "cobertura_insuficiente"
    assert body["indexador"] == "IPCA (IBGE)"
    assert body["competencia_solicitada"] == "11/1979"


# guarda -----------------------------------------------------------------------


def test_memoria_nao_recalcula_valores_do_motor(client: TestClient) -> None:
    body = _caso_principal(client)
    resposta = body["parcelas"][0]
    parcela = body["memoria"]["parcelas"][0]

    assert parcela["principal"] == resposta["principal"]
    assert parcela["correcao"]["valor_corrigido"] == resposta["correcao"]["valor_corrigido"]
    assert parcela["correcao"]["razao"] == resposta["correcao"]["razao"]
    assert parcela["juros"]["juros"] == resposta["juros"]["juros"]
    assert parcela["total"] == resposta["total"]
    assert body["memoria"]["resumo"] == body["resumo"]


def test_valores_matematicos_do_caso_principal_inalterados(client: TestClient) -> None:
    body = _caso_principal(client)
    resumo = body["resumo"]
    correcao = body["parcelas"][0]["correcao"]

    assert resumo["principal"] == "30018.44"
    assert resumo["correcao"] == "7010.09"
    assert resumo["juros"] == "0.00"
    assert resumo["total"] == "37028.53"
    assert correcao["indexador"] == "selic"
    assert [s["indexador"] for s in correcao["segmentos"]] == ["ipca", "selic"]
    assert [s["termo_inicial"] for s in correcao["segmentos"]] == ["2025-02", "2025-03"]
    assert [s["termo_final"] for s in correcao["segmentos"]] == ["2025-03", "2026-09"]
