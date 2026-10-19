from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi.testclient import TestClient

from app import db
from app.api.serializacao import _criterio_em
from app.engine.juros import (
    MODALIDADE_REGIMES,
    TIPO_SELIC_MENOS_IPCA,
    ConfigJuros,
    RegraJuros,
    _selic_menos_ipca_de,
    calcular_juros,
)
from app.indexers import CoverageError, obter
from app.indexers.ipca import KEY as IpcaKey
from app.main import create_app

DATA_FINAL = "2026-09-30"
PRINCIPAL = "30018.44"


def _taxa_monetaria(serie, mes: str) -> Decimal:
    comp = (int(mes[:4]), int(mes[5:7]))
    anterior = (comp[0], comp[1] - 1) if comp[1] > 1 else (comp[0] - 1, 12)
    return serie.valor(f"{comp[0]:04d}-{comp[1]:02d}") / serie.valor(
        f"{anterior[0]:04d}-{anterior[1]:02d}"
    ) - 1


def _esperado_selic_menos_ipca(base: Decimal, inicio: date, fim: date) -> Decimal:
    """SELIC mensal menos o IPCA mensal, com piso zero e pro rata por dias."""
    return _esperado_com_indexador(base, inicio, fim, obter(IpcaKey))


def _esperado_com_indexador(base: Decimal, inicio: date, fim: date, serie) -> Decimal:
    selic = obter("selic")
    total = Decimal(0)
    cursor = inicio
    while cursor <= fim:
        ultimo = date(cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1])
        limite = min(ultimo, fim)
        dias = Decimal((limite - cursor).days + 1)
        taxa = max(Decimal(0), selic.taxa(cursor) - _taxa_monetaria(serie, cursor.strftime("%Y-%m")))
        total += base * taxa * (dias / Decimal(ultimo.day))
        cursor = limite + timedelta(days=1)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@pytest.fixture()
def client(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    with TestClient(application) as c:
        yield c
    db.reset()


def _correcao(inicio: str = "2025-02-12") -> dict:
    return {
        "aplicar": True,
        "indexador": "tjsp_tabela_pratica",
        "termo_inicial": inicio,
    }


def _juros(inicio: str = "2025-03-31") -> dict:
    return {
        "aplicar": True,
        "modalidade": "taxa_legal",
        "inicio": inicio,
        "base": "corrigido",
    }


def _sem_juros() -> dict:
    return {"aplicar": False, "modalidade": "taxa_legal"}


def _verba(alteracoes: dict | None = None) -> dict:
    verba = {
        "id": "principal",
        "tipo": "valor",
        "nome": "Condenação",
        "valor": PRINCIPAL,
        "data_base": "2025-02-12",
        "correcao": _correcao(),
        "juros": _juros(),
        "multa": {"aplicar": False},
        "honorarios": {"aplicar": False},
        "regimes": [],
    }
    verba.update(alteracoes or {})
    return verba


def _payload(verbas: list[dict], data_base: str = DATA_FINAL) -> dict:
    return {
        "tipo": "parcelas",
        "titulo": "Regime temporal de correção e juros",
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


def test_piso_mensal_zero_quando_a_correcao_supera_a_selic() -> None:
    """Fev/2025: IPCA-IBGE acima da SELIC — os juros do mês ficam em zero."""
    ipca = obter("ipca")
    selic = obter("selic")
    ipca_fev = ipca.valor("2025-02") / ipca.valor("2025-01") - 1
    assert ipca_fev > selic.taxa("2025-02")
    assert _selic_menos_ipca_de(date(2025, 2, 15), None) == Decimal(0)

    # Jun/2025: SELIC acima do IPCA — a taxa fica positiva, sem piso
    ipca_jun = ipca.valor("2025-06") / ipca.valor("2025-05") - 1
    assert ipca_jun < selic.taxa("2025-06")
    assert _selic_menos_ipca_de(date(2025, 6, 15), None) == (
        selic.taxa("2025-06") - ipca_jun
    )
    assert _selic_menos_ipca_de(date(2025, 6, 15), None) > 0


def test_sem_juros_a_resolucao_automatica_nao_ocorre(client: TestClient) -> None:
    """Sem juros não há trechos de regime: vale o indexador configurado na verba."""
    body = _post(
        client,
        _payload([_verba({"correcao": _correcao(), "juros": _sem_juros()})]),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["aplicado"] is True
    assert parcela["correcao"]["indexador"] == "tjsp_tabela_pratica"
    assert parcela["correcao"]["segmentos"] == []
    assert parcela["juros"]["aplicado"] is False
    assert parcela["juros"]["juros"] == "0.00"
    assert float(parcela["total"]) == pytest.approx(
        float(PRINCIPAL) + float(parcela["correcao"]["correcao"]), abs=0.02
    )

    bases = {b["key"] for b in body["bases"]}
    assert "tjsp_tabela_pratica" in bases
    assert "selic" not in bases
    assert "taxa_legal" not in bases
    # correção isolada não envolve a correção subtraída dos juros
    assert "ipca" not in bases


def test_somente_juros_usa_selic_menos_ipca(client: TestClient) -> None:
    body = _post(
        client,
        _payload([_verba({"correcao": {"aplicar": False}, "juros": _juros()})]),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["aplicado"] is False
    juros = parcela["juros"]
    assert juros["aplicado"] is True
    assert juros["modalidade"] == "regimes"
    assert juros["indexador"] == "selic"
    assert juros["indexador_fonte"] == "Banco Central do Brasil"
    assert juros["trechos"][0]["rotulo"] == "SELIC menos correção monetária"
    assert juros["trechos"][0]["inicio"] == "2025-03-31"
    assert juros["trechos"][0]["fim"] == DATA_FINAL
    assert "piso mensal zero" in juros["trechos"][0]["taxa_rotulo"]
    assert "IPCA (IBGE)" in juros["trechos"][0]["taxa_rotulo"]
    assert "Tabela Prática" not in juros["trechos"][0]["taxa_rotulo"]
    assert "Taxa Legal" not in juros["trechos"][0]["taxa_rotulo"]
    assert float(juros["juros"]) > 0
    assert float(juros["juros"]) == pytest.approx(
        float(juros["trechos"][0]["valor"]), abs=0.02
    )

    # o componente subtraído é a série do IBGE, não a Tabela Prática
    assert Decimal(juros["trechos"][0]["valor"]) == _esperado_selic_menos_ipca(
        Decimal(PRINCIPAL), date(2025, 3, 31), date(2026, 9, 30)
    )

    bases = {b["key"]: b for b in body["bases"]}
    assert "selic" in bases
    assert "taxa_legal" not in bases
    assert "ipca" in bases
    assert bases["ipca"]["papel"] == "Juros"
    assert bases["ipca"]["fonte"] == "IBGE"
    assert "tjsp_tabela_pratica" not in bases


def test_juros_isolados_nao_usam_acidentalmente_a_tabela_pratica(
    client: TestClient,
) -> None:
    """A regra SELIC−IPCA não pode cair na IPCA-E/AASP nem na Taxa Legal."""
    body = _post(
        client,
        _payload([_verba({"correcao": {"aplicar": False}, "juros": _juros()})]),
    )
    juros = body["parcelas"][0]["juros"]
    regra = juros["trechos"][0]

    ipca = obter("ipca")
    tjsp = obter("tjsp_tabela_pratica")
    correto = _esperado_selic_menos_ipca(
        Decimal(PRINCIPAL), date(2025, 3, 31), date(2026, 9, 30)
    )
    com_ipca_e = _esperado_com_indexador(
        Decimal(PRINCIPAL), date(2025, 3, 31), date(2026, 9, 30), tjsp
    )

    assert Decimal(regra["valor"]) == correto
    assert Decimal(regra["valor"]) != com_ipca_e
    # a janela fev→mar/2025 já distingue as duas séries
    assert ipca.valor("2025-03") / ipca.valor("2025-02") != (
        tjsp.valor("2025-03") / tjsp.valor("2025-02")
    )


def test_juros_isolados_segue_o_pro_rata_do_mes() -> None:
    """Meio mês cobrado proporcionalmente aos dias, pela taxa mensal do regime."""
    inicio, fim = date(2025, 6, 1), date(2025, 6, 15)
    base = Decimal("30000.00")
    resultado = calcular_juros(
        base,
        inicio,
        fim,
        ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_REGIMES,
            regras=(
                RegraJuros(
                    rotulo="SELIC menos correção monetária",
                    inicio=date(2025, 6, 1),
                    fim=date(2025, 6, 30),
                    tipo=TIPO_SELIC_MENOS_IPCA,
                    indexador=IpcaKey,
                ),
            ),
        ),
    )

    ipca = obter("ipca")
    selic = obter("selic")
    taxa_mes = selic.taxa("2025-06") - _taxa_monetaria(ipca, "2025-06")
    esperado = (base * taxa_mes * (Decimal(15) / Decimal(30))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    assert resultado.trechos[0].dias == 15
    assert resultado.trechos[0].inicio == inicio
    assert resultado.trechos[0].fim == fim
    assert resultado.juros == esperado
    # meio mês vale exatamente metade da taxa mensal aplicada ao mês inteiro
    mes_inteiro = calcular_juros(
        base,
        date(2025, 6, 1),
        date(2025, 6, 30),
        ConfigJuros(
            aplicar=True,
            modalidade=MODALIDADE_REGIMES,
            regras=(
                RegraJuros(
                    rotulo="SELIC menos correção monetária",
                    inicio=date(2025, 6, 1),
                    fim=date(2025, 6, 30),
                    tipo=TIPO_SELIC_MENOS_IPCA,
                    indexador=IpcaKey,
                ),
            ),
        ),
    )
    assert abs(mes_inteiro.juros - esperado * 2) <= Decimal("0.02")


def test_juros_isolados_fora_da_cobertura_retornam_erro_explicito(
    client: TestClient,
) -> None:
    """Data final além da cobertura vira 422, nunca um cálculo silencioso."""
    response = client.post(
        "/api/calculos",
        json=_payload(
            [
                _verba(
                    {
                        "correcao": {"aplicar": False},
                        "juros": {
                            "aplicar": True,
                            "modalidade": "taxa_legal",
                            "inicio": "2026-09-01",
                            "base": "corrigido",
                        },
                    }
                )
            ],
            data_base="2026-10-31",
        ),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["erro"] == "cobertura_insuficiente"


def test_componente_monetario_fora_da_cobertura_do_ipca_erro_explicito() -> None:
    from app.engine.juros import _taxa_monetaria_de

    with pytest.raises(CoverageError) as excinfo:
        _taxa_monetaria_de(date(2026, 10, 1), IpcaKey)
    assert "IPCA (IBGE)" in str(excinfo.value)
    assert "10/2026" in str(excinfo.value)


def test_correcao_e_juros_usam_selic_integral(client: TestClient) -> None:
    body = _post(client, _payload([_verba()]))
    parcela = body["parcelas"][0]

    segmentos = parcela["correcao"]["segmentos"]
    assert [s["indexador"] for s in segmentos] == ["ipca", "selic"]
    assert parcela["juros"]["modalidade"] == "regimes"
    assert parcela["juros"]["trechos"][0]["rotulo"] == "SELIC integral"
    assert "juros embutidos na correção" in parcela["juros"]["trechos"][0]["taxa_rotulo"]
    assert parcela["juros"]["juros"] == "0.00"
    assert float(parcela["total"]) > float(PRINCIPAL)

    bases = {b["key"] for b in body["bases"]}
    assert "taxa_legal" not in bases
    assert "selic" in bases


def test_correcao_antes_dos_juros_divide_em_dois_criterios(client: TestClient) -> None:
    body = _post(client, _payload([_verba()]))
    parcela = body["parcelas"][0]

    segmentos = parcela["correcao"]["segmentos"]
    assert segmentos[0]["indexador"] == "ipca"
    assert segmentos[0]["indexador_fonte"] == "IBGE"
    assert segmentos[0]["termo_inicial"] == "2025-02"
    # a competência de março (onde começam os juros) ainda é só correção
    assert segmentos[0]["termo_final"] == "2025-03"
    assert segmentos[1]["indexador"] == "selic"
    # a SELIC parte do mesmo ponto em que o IPCA termina: sem a fronteira
    # compartilhada a transição mar/2025 → abr/2025 ficaria fora do produto
    assert segmentos[1]["termo_inicial"] == "2025-03"
    assert segmentos[1]["termo_final"] == "2026-09"

    trechos = parcela["juros"]["trechos"]
    assert len(trechos) == 1
    assert trechos[0]["inicio"] == "2025-03-31"
    assert trechos[0]["fim"] == DATA_FINAL


def test_juros_antes_da_correcao_divide_em_dois_criterios(client: TestClient) -> None:
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "data_base": "2025-02-12",
                        "correcao": _correcao("2025-04-15"),
                        "juros": _juros("2025-02-12"),
                    }
                )
            ]
        ),
    )
    parcela = body["parcelas"][0]

    trechos = parcela["juros"]["trechos"]
    assert len(trechos) == 2
    assert trechos[0]["rotulo"] == "SELIC menos correção monetária"
    assert trechos[0]["inicio"] == "2025-02-12"
    assert trechos[0]["fim"] == "2025-04-14"
    assert "piso mensal zero" in trechos[0]["taxa_rotulo"]
    assert float(trechos[0]["valor"]) > 0
    assert trechos[1]["rotulo"] == "SELIC integral"
    assert trechos[1]["inicio"] == "2025-04-15"
    assert trechos[1]["fim"] == DATA_FINAL
    assert float(trechos[1]["valor"]) == 0

    segmentos = parcela["correcao"]["segmentos"]
    assert [s["indexador"] for s in segmentos] == ["selic"]
    assert segmentos[0]["termo_inicial"] == "2025-04"
    assert segmentos[0]["termo_final"] == "2026-09"

    # o trecho de juros isolados também subtrai o IPCA do IBGE
    assert "IPCA (IBGE)" in trechos[0]["taxa_rotulo"]
    assert "Tabela Prática" not in trechos[0]["taxa_rotulo"]
    bases = {b["key"] for b in body["bases"]}
    assert "ipca" in bases
    assert "tjsp_tabela_pratica" not in bases

    assert float(parcela["juros"]["juros"]) == pytest.approx(
        float(trechos[0]["valor"]), abs=0.02
    )


def test_correcao_e_juros_na_mesma_competencia_mantem_o_criterio_historico(
    client: TestClient,
) -> None:
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "correcao": _correcao("2025-03-31"),
                        "juros": _juros("2025-03-31"),
                    }
                )
            ]
        ),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["segmentos"] == []
    assert parcela["correcao"]["indexador"] == "tjsp_tabela_pratica"
    assert parcela["juros"]["modalidade"] == "taxa_legal"
    assert parcela["juros"]["indexador"] == "taxa_legal"
    assert parcela["juros"]["trechos"][0]["rotulo"] == "Taxa Legal, art. 406 do CC"

    bases = {b["key"] for b in body["bases"]}
    assert "taxa_legal" in bases
    assert "selic" not in bases


def test_regimes_explicitos_tem_precedencia_sobre_o_regime_automatico(
    client: TestClient,
) -> None:
    regimes = [
        {
            "data_inicio": None,
            "data_fim": None,
            "correcao": "tjsp_tabela_pratica",
            "juros": {
                "aplicar": True,
                "modalidade": "fixa",
                "taxa": "0.01",
                "unidade": "mensal",
                "base": "corrigido",
            },
            "criterio": None,
        }
    ]
    body = _post(client, _payload([_verba({"regimes": regimes})]))
    juros = body["parcelas"][0]["juros"]

    assert juros["modalidade"] == "regimes"
    assert juros["trechos"][0]["rotulo"] == "1% ao mês"
    assert "SELIC" not in juros["trechos"][0]["rotulo"]
    assert "selic" not in {b["key"] for b in body["bases"]}


def test_datas_anteriores_ao_regime_mantem_taxa_legal(client: TestClient) -> None:
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "correcao": _correcao("2024-01-15"),
                        "juros": _juros("2024-03-15"),
                    }
                )
            ]
        ),
    )
    parcela = body["parcelas"][0]

    assert parcela["correcao"]["segmentos"] == []
    assert parcela["juros"]["modalidade"] == "taxa_legal"
    assert "taxa_legal" in {b["key"] for b in body["bases"]}


def test_juros_inicio_anterior_ao_regime_mantem_taxa_legal(client: TestClient) -> None:
    body = _post(
        client,
        _payload([_verba({"juros": _juros("2024-03-15")})]),
    )
    parcela = body["parcelas"][0]

    assert parcela["juros"]["modalidade"] == "taxa_legal"
    assert "selic" not in {b["key"] for b in body["bases"]}


def test_caso_principal_30018_44(client: TestClient) -> None:
    """R$ 30.018,44 — correção 12/02/2025, juros 31/03/2025, final 30/09/2026."""
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "correcao": _correcao("2025-02-12"),
                        "juros": _juros("2025-03-31"),
                    }
                )
            ]
        ),
    )
    parcela = body["parcelas"][0]

    assert parcela["principal"] == PRINCIPAL

    # 12/02/2025 → 30/03/2025: somente correção (IPCA — IBGE)
    # 31/03/2025 → 30/09/2026: correção + juros → SELIC integral
    segmentos = parcela["correcao"]["segmentos"]
    assert segmentos[0]["indexador"] == "ipca"
    assert segmentos[0]["termo_inicial"] == "2025-02"
    assert segmentos[0]["termo_final"] == "2025-03"
    assert segmentos[1]["indexador"] == "selic"
    assert segmentos[1]["termo_inicial"] == "2025-03"
    assert segmentos[1]["termo_final"] == "2026-09"
    assert segmentos[0]["termo_final"] == segmentos[1]["termo_inicial"]

    trecho = parcela["juros"]["trechos"][0]
    assert trecho["rotulo"] == "SELIC integral"
    assert trecho["inicio"] == "2025-03-31"
    assert trecho["fim"] == DATA_FINAL
    assert trecho["valor"] == "0.00"

    # memória derivada das séries oficiais efetivamente usadas:
    # IPCA-IBGE fev→mar × SELIC mar→set, sobre o principal
    ipca = obter("ipca")
    selic = obter("selic")
    fator = (ipca.valor("2025-03") / ipca.valor("2025-02")) * (
        selic.valor("2026-09") / selic.valor("2025-03")
    )
    esperado = (Decimal(PRINCIPAL) * fator).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert Decimal(parcela["total"]) == esperado
    assert parcela["total"] == "37028.53"
    assert parcela["correcao"]["correcao"] == "7010.09"
    # a referência manual de R$ 36.858,206 não é reproduzível com o IPCA-IBGE
    # e a SELIC oficiais; por isso não é usada como alvo de aceitação aqui
    assert Decimal(parcela["total"]) != Decimal("36858.21")


def test_trecho_somente_correcao_usa_ipca_ibge_e_nao_a_tabela_pratica(
    client: TestClient,
) -> None:
    """O trecho automático de somente correção usa a série própria do IBGE."""
    body = _post(client, _payload([_verba()]))
    parcela = body["parcelas"][0]
    segmentos = parcela["correcao"]["segmentos"]

    assert [s["indexador"] for s in segmentos] == ["ipca", "selic"]
    primeiro = segmentos[0]
    assert primeiro["indexador"] == "ipca"
    assert primeiro["indexador_fonte"] == "IBGE"
    assert primeiro["indexador_versao"] == "2026.09"

    ipca = obter("ipca")
    tjsp = obter("tjsp_tabela_pratica")
    razao = Decimal(primeiro["razao"])
    assert Decimal(primeiro["fator_inicial"]) == ipca.valor("2025-02")
    assert Decimal(primeiro["fator_final"]) == ipca.valor("2025-03")
    assert razao == ipca.valor("2025-03") / ipca.valor("2025-02")
    # a Tabela Prática é a série IPCA-E/AASP: mesma janela, outra razão
    assert razao != tjsp.valor("2025-03") / tjsp.valor("2025-02")

    bases = {b["key"] for b in body["bases"]}
    assert "ipca" in bases
    assert "tjsp_tabela_pratica" not in bases
    assert "selic" in bases


def test_segmentos_consecutivos_nao_deixam_competencia_sem_atualizacao(
    client: TestClient,
) -> None:
    """A fronteira mar/2025 é compartilhada: nenhum mês fica fora do produto."""
    body = _post(client, _payload([_verba()]))
    parcela = body["parcelas"][0]
    segmentos = parcela["correcao"]["segmentos"]

    assert len(segmentos) == 2
    assert segmentos[0]["termo_final"] == segmentos[1]["termo_inicial"]

    ipca = obter("ipca")
    selic = obter("selic")
    encadeado = (ipca.valor("2025-03") / ipca.valor("2025-02")) * (
        selic.valor("2026-09") / selic.valor("2025-03")
    )
    assert Decimal(parcela["correcao"]["razao"]) == encadeado

    # se a SELIC recomeçasse em abr/2025 a transição mar→abr desaparecia
    com_lacuna = (ipca.valor("2025-03") / ipca.valor("2025-02")) * (
        selic.valor("2026-09") / selic.valor("2025-04")
    )
    assert Decimal(parcela["correcao"]["razao"]) != com_lacuna


def test_correcao_fora_da_cobertura_do_ipca_retorna_erro_explicito(
    client: TestClient,
) -> None:
    """Cobertura insuficiente vira 422, nunca um cálculo silencioso."""
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
                        "juros": _sem_juros(),
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
    assert body["cobertura"] == {"inicio": "12/1979", "fim": "09/2026"}


def test_selic_integral_nao_passa_pelo_selic_menos_ipca(client: TestClient) -> None:
    """Incidência conjunta permanece SELIC integral, sem subtrair IPCA."""
    body = _post(client, _payload([_verba()]))
    juros = body["parcelas"][0]["juros"]

    assert juros["modalidade"] == "regimes"
    assert juros["juros"] == "0.00"
    assert juros["trechos"][0]["rotulo"] == "SELIC integral"
    assert "juros embutidos" in juros["trechos"][0]["taxa_rotulo"]
    assert "piso mensal zero" not in juros["trechos"][0]["taxa_rotulo"]
    assert "SELIC −" not in juros["trechos"][0]["taxa_rotulo"]

    # o IPCA só entra no segmento de correção, nunca como juros
    bases = {b["key"]: b for b in body["bases"]}
    assert set(bases) == {"ipca", "selic"}
    assert bases["ipca"]["papel"] == "Correção monetária"


def test_taxa_legal_continua_intacta_e_nao_usa_o_ipca(client: TestClient) -> None:
    """Fora do regime a Taxa Legal continua como estava, sem tocar o IPCA."""
    body = _post(client, _payload([_verba({"juros": _juros("2024-03-15")})]))
    juros = body["parcelas"][0]["juros"]

    assert juros["modalidade"] == "taxa_legal"
    assert juros["indexador"] == "taxa_legal"
    assert juros["indexador_fonte"] == "Banco Central do Brasil"
    assert [t["rotulo"] for t in juros["trechos"]] == [
        "CC/2002 + CTN: 12% a.a.",
        "Taxa Legal, art. 406 do CC",
    ]
    assert "SELIC" not in juros["trechos"][0]["taxa_rotulo"]
    assert "SELIC" not in juros["trechos"][1]["taxa_rotulo"]
    assert "IPCA" not in juros["trechos"][1]["taxa_rotulo"]
    assert float(juros["juros"]) > 0

    bases = {b["key"] for b in body["bases"]}
    assert bases == {"tjsp_tabela_pratica", "taxa_legal"}


def test_regime_temporal_trechos_contiguos_sem_lacuna(client: TestClient) -> None:
    """Os trechos do regime cobrem o período sem lacuna e sem sobreposição.

    A janela de 'somente juros' termina na véspera do início da correção —
    a mesma data-limite da regra de juros que o motor aplica — e o trecho de
    correção + juros começa nesse início.
    """
    body = _post(
        client,
        _payload(
            [
                _verba(
                    {
                        "data_base": "2025-02-12",
                        "correcao": _correcao("2025-04-15"),
                        "juros": _juros("2025-02-12"),
                    }
                )
            ]
        ),
    )
    regime = body["memoria"]["verbas"][0]["regime_temporal"]
    assert regime["aplicada"] is True
    trechos = regime["trechos"]
    assert [t["criterio"] for t in trechos] == [
        "somente_juros",
        "correcao_e_juros",
    ]

    fim_primeiro = date.fromisoformat(trechos[0]["fim"])
    inicio_segundo = date.fromisoformat(trechos[1]["inicio"])
    assert fim_primeiro + timedelta(days=1) == inicio_segundo
    assert trechos[1]["inicio"] == "2025-04-15"

    # a data da troca já é integral; a véspera ainda é só juros
    assert _criterio_em(regime, trechos[1]["inicio"]) == "correcao_e_juros"
    assert _criterio_em(regime, trechos[0]["fim"]) == "somente_juros"
    # nenhum dia fica sem critério dentro do período do regime
    dia = date.fromisoformat(trechos[0]["inicio"])
    while dia <= date.fromisoformat(trechos[1]["fim"]):
        assert _criterio_em(regime, dia.isoformat()) is not None
        dia += timedelta(days=1)
