from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import db
from app.engine.memoria import ESQUEMA_MEMORIA
from app.indexers.overrides import limpar_overrides_ativos
from app.main import create_app

D = Decimal

CUSTAS = [
    ("440.00", "2022-08-15", "2022-08"),
    ("29.70", "2022-08-30", "2022-08"),
    ("16.00", "2022-11-21", "2022-11"),
    ("29.70", "2023-07-20", "2023-07"),
    ("342.60", "2023-10-23", "2023-10"),
    ("362.37", "2026-04-28", "2026-04"),
]

DATA_FINAL = "2026-09-30"


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    limpar_overrides_ativos()
    db.reset()


def _verba(nome: str, valor: str, data_base: str, *, termo_inicial: str,
           juros: dict | None = None) -> dict:
    return {
        "nome": nome,
        "valor": valor,
        "data_base": data_base,
        "descricao": "",
        "correcao": {
            "aplicar": True,
            "indexador": "tjsp_tabela_pratica",
            "termo_inicial": termo_inicial,
        },
        "juros": juros
        if juros is not None
        else {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [],
        "parcelas": [],
    }


def payload_civel() -> dict:
    juros_base = {
        "aplicar": True,
        "modalidade": "taxa_legal",
        "inicio": "2026-04-24",
        "base": "corrigido",
    }
    verbas = [
        _verba("Valor da causa", "44000.00", "2022-08-30",
               termo_inicial="2022-08", juros=juros_base),
        _verba("Honorários sucumbenciais (12%)", "5280.00", "2022-08-30",
               termo_inicial="2022-08", juros=juros_base),
    ]
    verbas.extend(
        _verba(f"Custas - {data}", valor, data, termo_inicial=termo)
        for valor, data, termo in CUSTAS
    )
    return {
        "tipo": "parcelas",
        "titulo": "TESTE 1 — Cível por verbas independentes",
        "processo": "0000000-00.2024.8.26.0000",
        "parte": "Autor",
        "data_base": DATA_FINAL,
        "verbas": verbas,
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [],
    }


def payload_alimentos() -> dict:
    return {
        "tipo": "alimentos",
        "titulo": "TESTE 2 — Alimentos 85% do salário mínimo",
        "processo": "0000000-00.2023.8.26.0000",
        "parte": "Exequente",
        "data_base": DATA_FINAL,
        "alimentos": {
            "regras": [
                {
                    "inicio": "04/2023",
                    "fim": None,
                    "tipo": "salario_minimo",
                    "percentual": "0.85",
                    "descricao": "85% do salário mínimo",
                }
            ],
            "ate": "09/2026",
            "dia_vencimento": 10,
        },
        "correcao": {"aplicar": True, "indexador": "tjsp_tabela_pratica"},
        "juros": {
            "aplicar": True,
            "modalidade": "fixa",
            "taxa": "0.01",
            "unidade": "mensal",
            "base": "corrigido",
        },
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [
            {
                "competencia": f"2026-{mes:02d}",
                "data": f"2026-{mes:02d}-10",
                "valor": "200.00",
                "descricao": "pagamento parcial",
            }
            for mes in range(1, 10)
        ],
    }


def test_civel_verbas_independentes_com_data_final_30_09_2026(client: TestClient) -> None:
    response = client.post("/api/calculos", json=payload_civel())
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["data_base"] == DATA_FINAL
    parcelas = body["parcelas"]
    assert len(parcelas) == 8
    assert body["resumo"]["qtd_parcelas"] == 8
    assert body["resumo"]["principal"] == "50500.37"
    assert body["resumo"]["pagamentos"] == "0.00"

    base = parcelas[0]
    assert base["principal"] == "44000.00"
    assert base["inicio_correcao"] == "2022-08"
    assert base["inicio_juros"] == "2026-04-24"
    assert base["correcao"]["aplicado"] is True
    assert base["correcao"]["termo_final"] == "2026-09"
    assert base["juros"]["aplicado"] is True
    assert D(base["juros"]["juros"]) > 0

    honorarios = parcelas[1]
    assert honorarios["principal"] == "5280.00"  # 12% de 44.000,00
    assert honorarios["inicio_correcao"] == "2022-08"
    assert honorarios["inicio_juros"] == "2026-04-24"
    # a correção dos honorários acompanha a regra da verba/base
    assert honorarios["correcao"]["razao"] == base["correcao"]["razao"]
    doze_por_cento = (D(base["correcao"]["valor_corrigido"]) * D("0.12")).quantize(D("0.01"))
    assert honorarios["correcao"]["valor_corrigido"] == str(doze_por_cento)
    assert D(honorarios["juros"]["juros"]) > 0

    # datas de correção e juros permanecem independentes por verba
    assert base["inicio_correcao"] != base["inicio_juros"]
    for parcela in parcelas:
        assert parcela["multa"]["aplicado"] is False
        assert parcela["honorarios"]["aplicado"] is False
        assert parcela["honorarios"]["valor"] == "0.00"
        assert parcela["total_pago"] == "0.00"
        assert parcela["saldo"] == parcela["total"]

    for parcela, (valor, data, termo) in zip(parcelas[2:], CUSTAS, strict=True):
        assert parcela["principal"] == valor
        assert parcela["vencimento"] == data
        assert parcela["inicio_correcao"] == termo
        assert parcela["correcao"]["aplicado"] is True
        assert parcela["correcao"]["termo_final"] == "2026-09"
        assert parcela["juros"]["aplicado"] is False
        assert "explícito" in parcela["juros"]["motivo"]
        assert parcela["inicio_juros"] is None
        assert parcela["juros"]["juros"] == "0.00"

    bases = {b["key"]: b for b in body["bases"]}
    assert bases["tjsp_tabela_pratica"]["versao"] == "2026.09"
    assert bases["tjsp_tabela_pratica"]["papel"] == "Correção monetária"
    assert "taxa_legal" in bases

    memoria = body["memoria"]
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    assert len(memoria["verbas"]) == 8
    assert memoria["verbas"][0]["inicio_correcao"] == "2022-08"
    assert memoria["verbas"][0]["inicio_juros"] == "2026-04-24"


def test_alimentos_parcela_a_mesma_com_pagamentos_parciais(client: TestClient) -> None:
    response = client.post("/api/calculos", json=payload_alimentos())
    assert response.status_code == 201, response.text
    body = response.json()
    parcelas = body["parcelas"]

    assert body["data_base"] == DATA_FINAL
    assert body["resumo"]["qtd_parcelas"] == 42  # abr/2023 a set/2026
    assert body["resumo"]["pagamentos"] == "1800.00"  # 9 × R$ 200,00

    competencias = [p["competencia"] for p in parcelas]
    assert competencias[0] == "2023-04"
    assert competencias[-1] == "2026-09"
    assert len(set(competencias)) == 42
    assert competencias == sorted(competencias)

    por_competencia = {p["competencia"]: p for p in parcelas}

    # cada competência usa o salário mínimo vigente nela (nunca o atual)
    assert por_competencia["2023-04"]["salario_minimo"] == "1302.00"
    assert por_competencia["2023-04"]["principal"] == "1106.70"
    assert por_competencia["2023-05"]["salario_minimo"] == "1320.00"
    assert por_competencia["2023-05"]["principal"] == "1122.00"
    assert por_competencia["2026-01"]["salario_minimo"] == "1621.00"
    assert por_competencia["2026-01"]["principal"] == "1377.85"

    for parcela in parcelas:
        assert parcela["percentual"] == "0.85"
        assert "85%" in parcela["detalhe"]
        assert parcela["vencimento"][8:10] == "10"
        assert parcela["correcao"]["aplicado"] is True
        assert parcela["correcao"]["termo_inicial"] == parcela["competencia"]
        assert parcela["correcao"]["termo_final"] == "2026-09"
        assert parcela["juros"]["aplicado"] is True
        assert parcela["juros"]["modalidade"] == "fixa"
        assert parcela["juros"]["trechos"][0]["inicio"] == parcela["vencimento"]
        assert "1% ao mês" in parcela["juros"]["trechos"][0]["rotulo"]

    # pagamentos parciais por competência (jan/2026 em diante)
    for mes in range(1, 10):
        parcela = por_competencia[f"2026-{mes:02d}"]
        assert parcela["total_pago"] == "200.00"
        assert len(parcela["pagamentos"]) == 1
        assert parcela["diferenca"] == str(D(parcela["principal"]) - D("200.00"))
        assert parcela["saldo"] == str(D(parcela["total"]) - D("200.00"))
        # o pagamento parcial não bloqueia a atualização do saldo remanescente
        assert D(parcela["total"]) > D(parcela["principal"])
        assert D(parcela["saldo"]) > D(parcela["diferenca"])

    for parcela in parcelas:
        if parcela["competencia"] < "2026-01":
            assert parcela["total_pago"] == "0.00"
            assert parcela["diferenca"] == parcela["principal"]
            assert parcela["saldo"] == parcela["total"]

    bases = {b["key"]: b for b in body["bases"]}
    assert bases["tjsp_tabela_pratica"]["versao"] == "2026.09"
    assert bases["salario_minimo"]["papel"] == "Composição do principal"

    memoria = body["memoria"]
    assert memoria["esquema"] == ESQUEMA_MEMORIA
    assert memoria["parcelas"][0]["salario_minimo"] == "1302.00"
    assert memoria["parcelas"][0]["percentual"] == "0.85"
