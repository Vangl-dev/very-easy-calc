from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

FONTE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json"
FONTE_LABEL = "SELIC - Serie SGS 11 do Banco Central do Brasil"
SAIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "selic.json"
PROVENIENCIA = Path(__file__).resolve().parents[1] / "app" / "data" / "selic_bcb_raw.json"

INICIAL = "01/01/2023"


def baixar(url: str = FONTE_URL) -> list[dict]:
    alvo = f"{url}&dataInicial={INICIAL}"
    with urllib.request.urlopen(alvo, timeout=60) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    if not isinstance(dados, list) or not dados:
        raise SystemExit("resposta vazia ou inválida da API do BCB")
    return dados


def agrupar_por_mes(brutos: list[dict]) -> list[tuple[int, int, Decimal]]:
    """Taxa SELIC diária (% a.d.) acumulada em fator mensal por competência."""
    por_mes: dict[tuple[int, int], Decimal] = {}
    for registro in brutos:
        dia, mes, ano = registro["data"].split("/")
        chave = (int(ano), int(mes))
        taxa = Decimal(registro["valor"]) / Decimal(100)
        por_mes[chave] = por_mes.get(chave, Decimal(1)) * (Decimal(1) + taxa)
    return [(ano, mes, por_mes[(ano, mes)]) for ano, mes in sorted(por_mes)]


def normalizar(brutos: list[dict]) -> list[dict]:
    acumulado = Decimal(1)
    fatores: list[dict] = []
    hoje = date.today()
    for ano, mes, mensal in agrupar_por_mes(brutos):
        # só competências fechadas entram na base oficial
        if (ano, mes) >= (hoje.year, hoje.month):
            continue
        acumulado *= mensal
        fatores.append(
            {
                "year": ano,
                "month": mes,
                "factor": float(acumulado.quantize(Decimal("0.00000001"))),
                "mensal": float(mensal.quantize(Decimal("0.00000001"))),
                "sourceDate": f"01/{mes:02d}/{ano:04d}",
            }
        )
    if not fatores:
        raise SystemExit("nenhuma competência fechada na resposta do BCB")
    return fatores


def validar(fatores: list[dict]) -> list[str]:
    problemas: list[str] = []
    anterior = None
    for registro in fatores:
        atual = (registro["year"], registro["month"])
        if anterior is not None:
            ano, mes = anterior
            esperado = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
            if atual != esperado:
                problemas.append(
                    f"lacuna entre {ano}-{mes:02d} e {atual[0]}-{atual[1]:02d}"
                )
        anterior = atual
    vistos = set()
    anterior_valor = None
    for registro in fatores:
        chave = (registro["year"], registro["month"])
        if chave in vistos:
            problemas.append(f"competência duplicada: {chave}")
        vistos.add(chave)
        if registro["factor"] <= 0:
            problemas.append(f"fator não positivo em {chave}")
        if anterior_valor is not None and registro["factor"] < anterior_valor:
            problemas.append(f"fator decrescente em {chave}")
        anterior_valor = registro["factor"]
    return problemas


def montar(fatores: list[dict], atualizado_em: str | None = None) -> dict:
    ultimo = fatores[-1]
    return {
        "metadata": {
            "source": "Banco Central do Brasil",
            "sourceUrl": FONTE_URL,
            "sourceLabel": FONTE_LABEL,
            "version": f"{ultimo['year']:04d}.{ultimo['month']:02d}",
            "updatedAt": atualizado_em or date.today().isoformat(),
            "lastMonth": f"{ultimo['year']:04d}-{ultimo['month']:02d}",
            "totalRecords": len(fatores),
            "note": "Fator acumulado da taxa SELIC (SGS 11) por competência.",
        },
        "factors": fatores,
    }


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza a base da SELIC (BCB SGS 11)")
    parser.add_argument("--dry-run", action="store_true", help="não grava o arquivo")
    parser.add_argument("--arquivo", type=Path, help="usa JSON local no formato da API")
    args = parser.parse_args(argv)

    brutos = json.loads(args.arquivo.read_text(encoding="utf-8")) if args.arquivo else baixar()
    if not args.arquivo:
        PROVENIENCIA.write_text(json.dumps(brutos, ensure_ascii=False, indent=2), encoding="utf-8")

    fatores = normalizar(brutos)
    problemas = validar(fatores)
    if problemas:
        print("VALIDACAO FALHOU:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1

    documento = montar(fatores)
    if args.dry_run:
        print(json.dumps(documento["metadata"], ensure_ascii=False, indent=2))
        return 0

    SAIDA.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(documento["metadata"], ensure_ascii=False, indent=2))
    print(f"gravado: {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
