from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import db
from app.export.comum import brl_memoria, dec_memoria
from app.export.pdf import gerar_pdf
from app.export.xlsx import gerar_xlsx
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


def _memoria_fixa() -> dict:
    return {
        "esquema": "memoria-calculo/1.0",
        "codigo": "VEC-2026-000001",
        "tipo": "alimentos",
        "identificacao": {
            "titulo": "Pensão alimentícia",
            "processo": "0001234-56.2021.8.26.0100",
            "parte": "Autor",
            "app_name": "Very Easy Calc",
            "app_version": "1.0.0",
            "data_geracao": "2026-10-01T12:00:00+00:00",
            "data_base": "2026-08-31",
        },
        "criterios": {
            "data_base": "2026-08-31",
            "correcao": {"aplicar": False, "indexador": "tjsp_tabela_pratica"},
            "juros": {"aplicar": False, "modalidade": "taxa_legal"},
            "multa": {"aplicar": False},
            "honorarios": {"aplicar": False},
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
            "pagamentos_informados": [
                {"competencia": "2021-01", "data": "2026-01-10", "valor": "100.00"}
            ],
        },
        "bases": [
            {
                "key": "salario_minimo",
                "nome": "Salário mínimo",
                "versao": "2026.12",
                "fonte": "Ipeadata / Ministério da Economia",
                "fonte_url": "https://ipeadata.gov.br",
                "papel": "Composição do principal",
                "cobertura": "07/1994 a 12/2026",
            }
        ],
        "resumo": {
            "qtd_parcelas": 2,
            "periodo_inicio": "2021-01-10",
            "periodo_fim": "2021-02-10",
            "principal": "660.00",
            "correcao": "0.00",
            "juros": "0.00",
            "multa": "0.00",
            "honorarios": "0.00",
            "total": "660.00",
            "pagamentos": "100.00",
            "saldo": "560.00",
            "adicional": "0.00",
        },
        "parcelas": [
            {
                "numero": 1,
                "competencia": "2021-01",
                "competencia_rotulo": "01/2021",
                "vencimento": "2021-01-10",
                "descricao": "30% do salário mínimo (30% × R$ 1.100,00)",
                "principal": "330.00",
                "salario_minimo": "1100.00",
                "percentual": "0.30",
                "tipo_regra": "salario_minimo",
                "origem": "30% do salário mínimo",
                "detalhe": "30% × R$ 1.100,00",
                "regra": {
                    "tipo": "salario_minimo",
                    "origem": "30% do salário mínimo",
                    "detalhe": "30% × R$ 1.100,00",
                    "salario_minimo": "1100.00",
                    "percentual": "0.30",
                },
                "correcao": {
                    "aplicado": False,
                    "principal": "330.00",
                    "valor_corrigido": "330.00",
                    "correcao": "0.00",
                    "motivo": "Correção monetária não aplicada",
                },
                "juros": {
                    "aplicado": False,
                    "base": "330.00",
                    "incidencia": "valor corrigido",
                    "modalidade": "taxa_legal",
                    "juros": "0.00",
                    "motivo": "Juros não aplicados",
                },
                "multa": {"aplicado": False, "valor": "0.00", "motivo": "Multa não aplicado"},
                "honorarios": {
                    "aplicado": False,
                    "valor": "0.00",
                    "motivo": "Honorários não aplicado",
                },
                "pagamentos": [
                    {"data": "2026-01-10", "valor": "100.00", "descricao": "depósito"}
                ],
                "total": "330.00",
                "total_pago": "100.00",
                "saldo": "230.00",
                "adicional": "0.00",
            },
            {
                "numero": 2,
                "competencia": "2021-02",
                "competencia_rotulo": "02/2021",
                "vencimento": "2021-02-10",
                "descricao": "30% do salário mínimo (30% × R$ 1.100,00)",
                "principal": "330.00",
                "salario_minimo": "1100.00",
                "percentual": "0.30",
                "tipo_regra": "salario_minimo",
                "origem": "30% do salário mínimo",
                "detalhe": "30% × R$ 1.100,00",
                "regra": {
                    "tipo": "salario_minimo",
                    "origem": "30% do salário mínimo",
                    "detalhe": "30% × R$ 1.100,00",
                    "salario_minimo": "1100.00",
                    "percentual": "0.30",
                },
                "correcao": {
                    "aplicado": False,
                    "principal": "330.00",
                    "valor_corrigido": "330.00",
                    "correcao": "0.00",
                    "motivo": "Correção monetária não aplicada",
                },
                "juros": {
                    "aplicado": False,
                    "base": "330.00",
                    "incidencia": "valor corrigido",
                    "modalidade": "taxa_legal",
                    "juros": "0.00",
                    "motivo": "Juros não aplicados",
                },
                "multa": {"aplicado": False, "valor": "0.00", "motivo": "Multa não aplicado"},
                "honorarios": {
                    "aplicado": False,
                    "valor": "0.00",
                    "motivo": "Honorários não aplicado",
                },
                "pagamentos": [],
                "total": "330.00",
                "total_pago": "0.00",
                "saldo": "330.00",
                "adicional": "0.00",
            },
        ],
        "avisos": [],
    }


def test_export_pdf_inexistente_404(client: TestClient) -> None:
    assert client.get("/api/calculos/VEC-2026-000099/pdf").status_code == 404
    assert client.get("/api/calculos/VEC-2026-000099/xlsx").status_code == 404


def test_pdf_gerado_e_nao_vazio(client: TestClient) -> None:
    codigo = client.post("/api/calculos", json=_payload_alimentos()).json()["codigo"]
    response = client.get(f"/api/calculos/{codigo}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].endswith(f'filename="{codigo}.pdf"')
    conteudo = response.content
    assert len(conteudo) > 500
    assert conteudo.startswith(b"%PDF")


def test_pdf_contem_cabecalho_e_memoria(client: TestClient) -> None:
    memoria = _memoria_fixa()
    pdf = gerar_pdf(memoria)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800
    # ReportLab grava metadados legíveis no PDF
    assert b"Very Easy Calc" in pdf or b"VEC-2026-000001" in pdf


def test_pdf_muitas_parcelas_gera_documento(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/2021",
                    "fim": None,
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "09/2026",
        },
        pagamentos=[],
    )
    corpo = client.post("/api/calculos", json=payload).json()
    assert corpo["resumo"]["qtd_parcelas"] == 69
    pdf = client.get(f"/api/calculos/{corpo['codigo']}/pdf").content
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
    memoria_pdf = gerar_pdf(corpo["memoria"])
    assert memoria_pdf.startswith(b"%PDF")
    assert len(memoria_pdf) > 5000


def test_xlsx_gerado_e_nao_vazio(client: TestClient) -> None:
    codigo = client.post("/api/calculos", json=_payload_alimentos()).json()["codigo"]
    response = client.get(f"/api/calculos/{codigo}/xlsx")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert response.headers["content-disposition"].endswith(f'filename="{codigo}.xlsx"')
    conteudo = response.content
    assert len(conteudo) > 800
    assert conteudo[:2] == b"PK"


def test_xlsx_planilhas_e_valores_da_memoria() -> None:
    memoria = _memoria_fixa()
    xlsx = gerar_xlsx(memoria)
    wb = load_workbook(io.BytesIO(xlsx))
    assert wb.sheetnames == ["Resumo", "Parcelas"]

    resumo = wb["Resumo"]
    valores_resumo = {}
    for linha in resumo.iter_rows(min_row=1, max_col=2, values_only=True):
        if linha[0] and linha[1] is not None:
            valores_resumo[str(linha[0])] = linha[1]
    assert valores_resumo["Código"] == "VEC-2026-000001"
    assert valores_resumo["Versão do app"] == "1.0.0"
    assert valores_resumo["Data-base"] == "2026-08-31"
    assert valores_resumo["Principal"] == 660.0
    assert valores_resumo["Total"] == 660.0
    assert valores_resumo["Saldo"] == 560.0
    assert valores_resumo["Pagamentos"] == 100.0
    assert valores_resumo["Parcelas"] == 2

    parcelas = wb["Parcelas"]
    cabecalhos = [c.value for c in next(parcelas.iter_rows(min_row=1, max_row=1))]
    assert "Salário mínimo" in cabecalhos
    assert "Percentual" in cabecalhos
    assert "Principal" in cabecalhos
    assert "Saldo" in cabecalhos
    assert "Total" in cabecalhos

    primeira = [c.value for c in next(parcelas.iter_rows(min_row=2, max_row=2))]
    mapa = dict(zip(cabecalhos, primeira, strict=False))
    assert mapa["Competência"] == "01/2021"
    assert float(mapa["Salário mínimo"]) == 1100.0
    assert float(mapa["Percentual"]) == 0.3
    assert float(mapa["Principal"]) == 330.0
    assert float(mapa["Pagamentos"]) == 100.0
    assert float(mapa["Saldo"]) == 230.0
    assert float(mapa["Total"]) == 330.0
    assert isinstance(mapa["Principal"], (int, float))
    assert isinstance(mapa["Salário mínimo"], (int, float))
    assert not isinstance(mapa["Principal"], str)
    assert not isinstance(mapa["Salário mínimo"], str)


def test_xlsx_api_valores_correspondem_a_memoria(client: TestClient) -> None:
    corpo = client.post("/api/calculos", json=_payload_alimentos()).json()
    memoria = corpo["memoria"]
    xlsx = client.get(f"/api/calculos/{corpo['codigo']}/xlsx").content
    wb = load_workbook(io.BytesIO(xlsx))
    parcelas = wb["Parcelas"]
    cabecalhos = [c.value for c in next(parcelas.iter_rows(min_row=1, max_row=1))]
    linhas = list(parcelas.iter_rows(min_row=2, values_only=True))
    assert len(linhas) == memoria["resumo"]["qtd_parcelas"]
    for memoria_p, linha in zip(memoria["parcelas"], linhas, strict=True):
        mapa = dict(zip(cabecalhos, linha, strict=False))
        assert mapa["Competência"] == memoria_p["competencia_rotulo"]
        assert mapa["Principal"] == float(memoria_p["principal"])
        assert mapa["Salário mínimo"] == float(memoria_p["salario_minimo"])
        assert mapa["Percentual"] == float(memoria_p["percentual"])
        assert mapa["Saldo"] == float(memoria_p["saldo"])
        assert mapa["Total"] == float(memoria_p["total"])
        assert mapa["Pagamentos"] == float(memoria_p["total_pago"])


def test_xlsx_muitas_parcelas(client: TestClient) -> None:
    payload = _payload_alimentos(
        alimentos={
            "regras": [
                {
                    "inicio": "01/2021",
                    "fim": None,
                    "tipo": "salario_minimo",
                    "percentual": "0.30",
                }
            ],
            "ate": "09/2026",
        },
        pagamentos=[],
    )
    corpo = client.post("/api/calculos", json=payload).json()
    xlsx = client.get(f"/api/calculos/{corpo['codigo']}/xlsx").content
    wb = load_workbook(io.BytesIO(xlsx))
    parcelas = wb["Parcelas"]
    linhas = [linha for linha in parcelas.iter_rows(min_row=2, values_only=True) if linha[0]]
    assert len(linhas) == 69
    assert linhas[0][0] == 1
    assert linhas[-1][0] == 69


def test_export_nao_recalcula_valores(client: TestClient) -> None:
    """Exportação usa a memória; valores não divergem do cálculo."""
    corpo = client.post("/api/calculos", json=_payload_alimentos()).json()
    memoria = corpo["memoria"]
    assert memoria["parcelas"][0]["principal"] == "330.00"
    assert memoria["parcelas"][0]["total"] == "330.00"
    assert memoria["parcelas"][0]["saldo"] == "230.00"

    xlsx = gerar_xlsx(memoria)
    wb = load_workbook(io.BytesIO(xlsx))
    parcelas = wb["Parcelas"]
    cabecalhos = [c.value for c in next(parcelas.iter_rows(min_row=1, max_row=1))]
    primeira = dict(
        zip(cabecalhos, next(parcelas.iter_rows(min_row=2, max_row=2, values_only=True)), strict=False)
    )
    assert primeira["Principal"] == float(memoria["parcelas"][0]["principal"])
    assert primeira["Saldo"] == float(memoria["parcelas"][0]["saldo"])
    assert brl_memoria(memoria["parcelas"][0]["principal"]) == "R$ 330,00"
    assert dec_memoria(memoria["parcelas"][0]["principal"]) is not None


def test_comum_converte_sem_recalcular() -> None:
    assert dec_memoria("330.00") is not None
    assert str(dec_memoria("330.00")) == "330.00"
    assert brl_memoria("1100.00") == "R$ 1.100,00"
    assert brl_memoria(None) == ""
