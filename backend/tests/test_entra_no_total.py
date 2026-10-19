from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from reportlab.platypus import KeepTogether, Paragraph, Table

from app import db
from app.engine.verbas import resolver_verbas
from app.export.comum import criterios_txt, verbas_fora_do_total
from app.export.pdf import montar_historia
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
        "titulo": "Composição no total",
        "processo": "0001234-56.2021.8.26.0100",
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


def _verbas_por_id(memoria: dict) -> dict:
    return {v["id"]: v for v in memoria["verbas"]}


def _texto_historia(fluxo) -> str:
    partes: list[str] = []
    for item in fluxo:
        if isinstance(item, KeepTogether):
            partes.append(_texto_historia(item._content))
        elif isinstance(item, Paragraph):
            partes.append(item.getPlainText())
        elif isinstance(item, Table):
            for linha in item._cellvalues:
                for celula in linha:
                    if isinstance(celula, Paragraph):
                        partes.append(celula.getPlainText())
                    elif isinstance(celula, (list, tuple)):
                        partes.extend(
                            p.getPlainText()
                            for p in celula
                            if isinstance(p, Paragraph)
                        )
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Motor (resolver_verbas)
# ---------------------------------------------------------------------------


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
        self.entra_no_total = kwargs.get("entra_no_total")


def test_resolucao_explicita_prevalece_sobre_ser_base() -> None:
    resolvidas = resolver_verbas(
        [
            _VerbaFake(
                id="causa",
                nome="Valor da causa",
                valor="44000.00",
                data_base="2022-08-30",
                entra_no_total=True,
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
    assert resolvidas[0].referencia is True
    assert resolvidas[0].entra_no_total is True
    assert resolvidas[1].entra_no_total is True


def test_resolucao_sem_campo_usa_padrao_historico() -> None:
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
    assert resolvidas[0].referencia is True
    assert resolvidas[0].entra_no_total is False
    assert resolvidas[1].entra_no_total is True


# ---------------------------------------------------------------------------
# API e memória
# ---------------------------------------------------------------------------


def test_base_marcada_como_composta_soma_no_total(client: TestClient) -> None:
    verbas = _payload()["verbas"]
    verbas[0]["entra_no_total"] = True
    corpo = client.post("/api/calculos", json=_payload(verbas=verbas))
    assert corpo.status_code == 201
    memoria = corpo.json()["memoria"]

    por_id = _verbas_por_id(memoria)
    assert por_id["causa"]["entra_no_total"] is True
    assert por_id["sucumbencia"]["entra_no_total"] is True

    soma = sum(Decimal(p["total"]) for p in memoria["parcelas"])
    assert Decimal(memoria["resumo"]["total"]) == soma

    total_bloco = memoria["criterios"]["total_da_execucao"]
    assert total_bloco["verbas_fora_do_total"] == []
    assert "não muda essa marcação" in total_bloco["regra"]


def test_base_sem_campo_continua_fora_do_total(client: TestClient) -> None:
    corpo = client.post("/api/calculos", json=_payload())
    assert corpo.status_code == 201
    memoria = corpo.json()["memoria"]

    por_id = _verbas_por_id(memoria)
    assert por_id["causa"]["entra_no_total"] is False
    assert por_id["sucumbencia"]["entra_no_total"] is True

    soma_derivada = sum(
        Decimal(p["total"]) for p in memoria["parcelas"] if p["verba"]["id"] != "causa"
    )
    assert Decimal(memoria["resumo"]["total"]) == soma_derivada

    fora = memoria["criterios"]["total_da_execucao"]["verbas_fora_do_total"]
    assert [v["id"] for v in fora] == ["causa"]


def test_verba_sem_base_pode_ficar_fora_do_total(client: TestClient) -> None:
    verbas = _payload()["verbas"]
    verbas[0]["entra_no_total"] = False
    corpo = client.post("/api/calculos", json=_payload(verbas=verbas))
    assert corpo.status_code == 201
    memoria = corpo.json()["memoria"]

    por_id = _verbas_por_id(memoria)
    assert por_id["causa"]["entra_no_total"] is False

    soma_sucumbencia = sum(
        Decimal(p["total"]) for p in memoria["parcelas"] if p["verba"]["id"] == "sucumbencia"
    )
    assert Decimal(memoria["resumo"]["total"]) == soma_sucumbencia
    # as duas verbas continuam na memória, apenas uma compõe o total
    assert len(memoria["verbas"]) == 2
    assert len(memoria["parcelas"]) == 2


def test_entra_no_total_nao_booleano_rejeitado(client: TestClient) -> None:
    verbas = _payload()["verbas"]
    verbas[0]["entra_no_total"] = "sim"
    response = client.post("/api/calculos", json=_payload(verbas=verbas))
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------


def test_pdf_marca_verba_fora_do_total_e_explica_a_regra(client: TestClient) -> None:
    memoria = client.post("/api/calculos", json=_payload()).json()["memoria"]
    texto = _texto_historia(montar_historia(memoria))

    assert "não compõe o total da execução" in texto
    assert "VALOR DA CAUSA — FORA DO TOTAL" in texto
    # nenhum campo técnico vaza para o documento
    assert "base_verba_id" not in texto
    assert "entra_no_total" not in texto


def test_pdf_sem_exclusao_nao_emite_a_nota(client: TestClient) -> None:
    verbas = _payload()["verbas"]
    verbas[0]["entra_no_total"] = True
    memoria = client.post("/api/calculos", json=_payload(verbas=verbas)).json()["memoria"]
    texto = _texto_historia(montar_historia(memoria))

    assert "não compõe o total da execução" not in texto
    assert "FORA DO TOTAL" not in texto


def test_criterios_do_xlsx_explicam_a_regra_do_total() -> None:
    verbas = [
        {"id": "causa", "nome": "Valor da causa", "entra_no_total": False},
        {"id": "sucumbencia", "nome": "Honorários", "entra_no_total": True},
    ]
    assert [v["nome"] for v in verbas_fora_do_total(verbas)] == ["Valor da causa"]
    linhas = criterios_txt({"verbas": verbas})
    rotulos = [rotulo for rotulo, _ in linhas]
    assert "Total da execução" in rotulos
    regra = dict(linhas)["Total da execução"]
    assert "Valor da causa" in regra
    assert "base_verba_id" not in regra


def test_memoria_antiga_sem_campo_segue_o_padrao_historico() -> None:
    verbas = [
        {"id": "causa", "nome": "Valor da causa", "base_verba_id": None},
        {"id": "sucumbencia", "nome": "Honorários", "base_verba_id": "causa"},
    ]
    assert [v["id"] for v in verbas_fora_do_total(verbas)] == ["causa"]
