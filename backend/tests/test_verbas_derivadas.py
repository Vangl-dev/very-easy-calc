from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app
from app.engine.verbas import resolver_verbas


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


class _VerbaFake:
    """Objeto mínimo no formato do schema para testes unitários do motor."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.tipo = kwargs.get("tipo", "valor")
        self.nome = kwargs["nome"]
        self.valor = kwargs.get("valor")
        self.data_base = kwargs["data_base"]
        self.descricao = kwargs.get("descricao", "")
        self.base_verba_id = kwargs.get("base_verba_id")
        self.percentual = kwargs.get("percentual")


def _payload_derivada(**kwargs) -> dict:
    base = {
        "tipo": "parcelas",
        "titulo": "Verba derivada 12%",
        "processo": "0000000-00.2024.8.26.0000",
        "parte": "Autor",
        "data_base": "2026-09-30",
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
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Motor (resolver_verbas)
# ---------------------------------------------------------------------------


def test_resolver_verba_base_e_derivada_12_por_cento() -> None:
    resolvidas = resolver_verbas(
        [
            _VerbaFake(
                id="causa",
                nome="Valor da causa",
                valor="44000.00",
                data_base="2022-08-30",
            ),
            _VerbaFake(
                id="hon",
                tipo="percentual",
                nome="Honorários",
                base_verba_id="causa",
                percentual="0.12",
                data_base="2022-08-30",
            ),
        ]
    )
    assert resolvidas[0].principal == pytest.approx(44000.00)
    assert resolvidas[1].tipo == "percentual"
    assert resolvidas[1].principal == pytest.approx(5280.00)
    assert resolvidas[1].base_verba_id == "causa"


def test_resolver_rejeita_base_inexistente() -> None:
    with pytest.raises(ValueError, match="não existe"):
        resolver_verbas(
            [
                _VerbaFake(id="base", nome="A", valor="10", data_base="2024-01-01"),
                _VerbaFake(
                    nome="B",
                    tipo="percentual",
                    base_verba_id="inexistente",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_rejeita_percentual_sem_base() -> None:
    with pytest.raises(ValueError, match="exige base_verba_id"):
        resolver_verbas(
            [
                _VerbaFake(
                    nome="B",
                    tipo="percentual",
                    percentual="0.10",
                    data_base="2024-01-01",
                )
            ]
        )


def test_resolver_rejeita_percentual_sem_percentual() -> None:
    with pytest.raises(ValueError, match="exige percentual"):
        resolver_verbas(
            [
                _VerbaFake(id="base", nome="A", valor="100", data_base="2024-01-01"),
                _VerbaFake(
                    nome="B",
                    tipo="percentual",
                    base_verba_id="base",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_rejeita_percentual_invalido() -> None:
    with pytest.raises(ValueError, match="percentual"):
        resolver_verbas(
            [
                _VerbaFake(id="base", nome="A", valor="100", data_base="2024-01-01"),
                _VerbaFake(
                    nome="B",
                    tipo="percentual",
                    base_verba_id="base",
                    percentual="abc",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_rejeita_percentual_fora_da_faixa_de_fracao() -> None:
    with pytest.raises(ValueError, match="fração"):
        resolver_verbas(
            [
                _VerbaFake(id="base", nome="A", valor="100", data_base="2024-01-01"),
                _VerbaFake(
                    nome="B",
                    tipo="percentual",
                    base_verba_id="base",
                    percentual="12",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_rejeita_ciclo_direto() -> None:
    with pytest.raises(ValueError, match="circular"):
        resolver_verbas(
            [
                _VerbaFake(
                    id="A",
                    nome="A",
                    tipo="percentual",
                    base_verba_id="B",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
                _VerbaFake(
                    id="B",
                    nome="B",
                    tipo="percentual",
                    base_verba_id="A",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_rejeita_ciclo_indireto() -> None:
    with pytest.raises(ValueError, match="circular"):
        resolver_verbas(
            [
                _VerbaFake(
                    id="A",
                    nome="A",
                    tipo="percentual",
                    base_verba_id="C",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
                _VerbaFake(
                    id="B",
                    nome="B",
                    tipo="percentual",
                    base_verba_id="A",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
                _VerbaFake(
                    id="C",
                    nome="C",
                    tipo="percentual",
                    base_verba_id="B",
                    percentual="0.10",
                    data_base="2024-01-01",
                ),
            ]
        )


def test_resolver_permite_duas_verbas_na_mesma_base() -> None:
    resolvidas = resolver_verbas(
        [
            _VerbaFake(id="base", nome="Base", valor="1000", data_base="2024-01-01"),
            _VerbaFake(
                id="h1",
                tipo="percentual",
                nome="H1",
                base_verba_id="base",
                percentual="0.10",
                data_base="2024-01-01",
            ),
            _VerbaFake(
                id="h2",
                tipo="percentual",
                nome="H2",
                base_verba_id="base",
                percentual="0.05",
                data_base="2024-02-01",
            ),
        ]
    )
    assert resolvidas[0].principal == pytest.approx(1000)
    assert resolvidas[1].principal == pytest.approx(100)
    assert resolvidas[2].principal == pytest.approx(50)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_verba_derivada_principal_5280_com_datas_proprias(client: TestClient) -> None:
    payload = _payload_derivada()
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["resumo"]["qtd_parcelas"] == 2
    causa = body["parcelas"][0]
    sucumb = body["parcelas"][1]

    assert causa["principal"] == "44000.00"
    assert sucumb["principal"] == "5280.00"

    # datas próprias da verba derivada (não herdadas em silêncio)
    assert sucumb["inicio_correcao"] == "2022-08"
    assert sucumb["inicio_juros"] == "2026-04-24"
    assert sucumb["vencimento"] == "2022-08-30"

    # verba-base continua normal
    assert causa["correcao"]["aplicado"] is True
    assert causa["juros"]["aplicado"] is True

    # memória registra a derivação
    memoria_verbas = {v["id"]: v for v in body["memoria"]["verbas"]}
    assert memoria_verbas["causa"]["tipo"] == "valor"
    assert memoria_verbas["sucumbencia"]["tipo"] == "percentual"
    assert memoria_verbas["sucumbencia"]["base_verba_id"] == "causa"
    assert memoria_verbas["sucumbencia"]["percentual"] == "0.12"
    assert memoria_verbas["sucumbencia"]["valor"] == "5280.00"


def test_api_verba_derivada_sem_herancade_datas_da_base(client: TestClient) -> None:
    """Derivada com datas diferentes da base não pode herdar as datas dela."""
    payload = _payload_derivada()
    payload["verbas"][1]["data_base"] = "2024-01-15"
    payload["verbas"][1]["correcao"] = {
        "aplicar": True,
        "indexador": "tjsp_tabela_pratica",
        "termo_inicial": "2024-01",
    }
    payload["verbas"][1]["juros"] = {
        "aplicar": True,
        "modalidade": "taxa_legal",
        "inicio": "2024-02-01",
        "base": "corrigido",
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    sucumb = response.json()["parcelas"][1]
    assert sucumb["principal"] == "5280.00"
    assert sucumb["vencimento"] == "2024-01-15"
    assert sucumb["inicio_correcao"] == "2024-01"
    assert sucumb["inicio_juros"] == "2024-02-01"


def test_api_base_inexistente_retorna_422(client: TestClient) -> None:
    payload = _payload_derivada()
    payload["verbas"][1]["base_verba_id"] = "nao_existe"
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    assert "não existe" in response.json()["mensagem"]


def test_api_ciclo_retorna_422(client: TestClient) -> None:
    payload = _payload_derivada()
    payload["verbas"][0]["tipo"] = "percentual"
    payload["verbas"][0]["valor"] = None
    payload["verbas"][0]["base_verba_id"] = "sucumbencia"
    payload["verbas"][0]["percentual"] = "0.50"
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 422
    assert "circular" in response.json()["mensagem"]


def test_api_duas_derivadas_da_mesma_base(client: TestClient) -> None:
    payload = _payload_derivada(
        verbas=[
            {
                "id": "causa",
                "nome": "Valor da causa",
                "valor": "44000.00",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            },
            {
                "id": "suc",
                "tipo": "percentual",
                "nome": "Sucumbência",
                "base_verba_id": "causa",
                "percentual": "0.12",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            },
            {
                "id": "cumprimento",
                "tipo": "percentual",
                "nome": "Cumprimento",
                "base_verba_id": "causa",
                "percentual": "0.10",
                "data_base": "2023-01-10",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            },
        ]
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    parcelas = response.json()["parcelas"]
    assert parcelas[0]["principal"] == "44000.00"
    assert parcelas[1]["principal"] == "5280.00"
    assert parcelas[2]["principal"] == "4400.00"


def test_api_payload_valor_sem_tipo_continua_funcional(client: TestClient) -> None:
    """Compatibilidade: verbas antigas sem tipo/id continuam iguais."""
    payload = _payload_derivada(
        verbas=[
            {
                "nome": "Valor da causa",
                "valor": "44000.00",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            },
            {
                "nome": "Honorários sucumbenciais (12%)",
                "valor": "5280.00",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
            },
        ]
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    parcelas = response.json()["parcelas"]
    assert parcelas[0]["principal"] == "44000.00"
    assert parcelas[1]["principal"] == "5280.00"


def test_regressao_civel_verbas_valor_mantem_totais(client: TestClient) -> None:
    """O cálculo cível já validado (sem verbas derivadas) continua igual."""
    custas = [
        ("440.00", "2022-08-15", "2022-08"),
        ("29.70", "2022-08-30", "2022-08"),
        ("16.00", "2022-11-21", "2022-11"),
        ("29.70", "2023-07-20", "2023-07"),
        ("342.60", "2023-10-23", "2023-10"),
        ("362.37", "2026-04-28", "2026-04"),
    ]

    def verba(nome, valor, data_base, termo, com_juros=False):
        return {
            "nome": nome,
            "valor": valor,
            "data_base": data_base,
            "correcao": {
                "aplicar": True,
                "indexador": "tjsp_tabela_pratica",
                "termo_inicial": termo,
            },
            "juros": (
                {
                    "aplicar": True,
                    "modalidade": "taxa_legal",
                    "inicio": "2026-04-24",
                    "base": "corrigido",
                }
                if com_juros
                else {"aplicar": False}
            ),
            "multa": {"aplicar": False},
            "honorarios": {"aplicar": False},
            "pagamentos": [],
        }

    verbas = [
        verba("Valor da causa", "44000.00", "2022-08-30", "2022-08", com_juros=True),
        verba(
            "Honorários sucumbenciais (12%)",
            "5280.00",
            "2022-08-30",
            "2022-08",
            com_juros=True,
        ),
    ]
    verbas.extend(
        verba(f"Custas - {data}", valor, data, termo) for valor, data, termo in custas
    )

    payload = {
        "tipo": "parcelas",
        "titulo": "Regressão cível verbas valor",
        "processo": "0000000-00.2024.8.26.0000",
        "parte": "Autor",
        "data_base": "2026-09-30",
        "verbas": verbas,
        "correcao": {"aplicar": False},
        "juros": {"aplicar": False},
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "pagamentos": [],
    }
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["resumo"]["qtd_parcelas"] == 8
    assert body["resumo"]["principal"] == "50500.37"
    assert body["resumo"]["total"] == "62026.39"
    assert body["parcelas"][0]["principal"] == "44000.00"
    assert body["parcelas"][1]["principal"] == "5280.00"
    assert body["parcelas"][1]["inicio_correcao"] == "2022-08"
    assert body["parcelas"][1]["inicio_juros"] == "2026-04-24"
    for parcela in body["parcelas"][2:]:
        assert parcela["juros"]["aplicado"] is False
        assert parcela["inicio_juros"] is None


def test_regressao_civel_com_verba_derivada_mesmo_principal(client: TestClient) -> None:
    """Mesmo cível, honorários como verba derivada 12% → principal 5280 e totais coerentes."""
    payload = _payload_derivada(
        titulo="Cível com verba derivada",
        verbas=[
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
            },
        ],
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    causa, sucumb = body["parcelas"]

    assert causa["principal"] == "44000.00"
    assert sucumb["principal"] == "5280.00"
    # correção da derivada usa o mesmo fator da base (mesmo período), mas principal é o dela
    assert sucumb["correcao"]["razao"] == causa["correcao"]["razao"]
    doze = (float(causa["correcao"]["valor_corrigido"]) * 0.12)
    assert abs(float(sucumb["correcao"]["valor_corrigido"]) - doze) < 0.02
    # a verba-base é apenas referência: fica fora da soma do resumo
    assert float(body["resumo"]["principal"]) == pytest.approx(5280.00)


def test_total_geral_exclui_verba_de_referencia(client: TestClient) -> None:
    """Verba usada só como base não entra no total; derivada e verba normal entram."""
    payload = _payload_derivada(
        titulo="Cível com verba de referência",
        verbas=[
            {
                "id": "causa",
                "tipo": "valor",
                "nome": "Valor da causa",
                "valor": "44000.00",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
            },
            {
                "id": "sucumb",
                "tipo": "percentual",
                "nome": "Honorários de sucumbência",
                "base_verba_id": "causa",
                "percentual": "0.12",
                "data_base": "2022-08-30",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
            },
            {
                "id": "custa",
                "tipo": "valor",
                "nome": "Custas",
                "valor": "1000.00",
                "data_base": "2023-05-10",
                "correcao": {"aplicar": False},
                "juros": {"aplicar": False},
                "multa": {"aplicar": False},
                "honorarios": {"aplicar": False},
            },
        ],
    )
    response = client.post("/api/calculos", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()

    causa, sucumb, custa = body["parcelas"]

    # a referência continua existindo e sendo a base da derivada
    assert causa["principal"] == "44000.00"
    assert sucumb["principal"] == "5280.00"  # 12% de 44.000,00
    assert custa["principal"] == "1000.00"

    # total geral: só a derivada (5.280,00) + a verba normal (1.000,00)
    assert body["resumo"]["principal"] == "6280.00"
    assert body["resumo"]["total"] == "6280.00"
    assert float(body["resumo"]["total"]) == pytest.approx(
        float(sucumb["total"]) + float(custa["total"])
    )
    assert float(body["resumo"]["total"]) != pytest.approx(
        float(causa["total"]) + float(sucumb["total"]) + float(custa["total"])
    )
