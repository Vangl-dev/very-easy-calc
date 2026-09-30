from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

FONTE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.29543/dados?formato=json"
FONTE_LABEL = "Taxa Legal - Serie SGS 29543 do Banco Central do Brasil"
SAIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "taxa_legal.json"
PROVENIENCIA = Path(__file__).resolve().parents[1] / "app" / "data" / "taxa_legal_bcb_raw.json"


def baixar(url: str = FONTE_URL) -> list[dict]:
    with urllib.request.urlopen(url, timeout=30) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    if not isinstance(dados, list) or not dados:
        raise SystemExit("resposta vazia ou inválida da API do BCB")
    return dados


def normalizar(brutos: list[dict]) -> list[dict]:
    fatores = []
    for registro in brutos:
        _dia, mes, ano = registro["data"].split("/")
        taxa = Decimal(registro["valor"]) / Decimal(100)
        fatores.append(
            {
                "year": int(ano),
                "month": int(mes),
                "factor": float(taxa),
                "sourceValue": registro["valor"],
                "sourceDate": registro["data"],
            }
        )
    fatores.sort(key=lambda r: (r["year"], r["month"]))
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
    for registro in fatores:
        chave = (registro["year"], registro["month"])
        if chave in vistos:
            problemas.append(f"competência duplicada: {chave}")
        vistos.add(chave)
        if registro["factor"] < 0:
            problemas.append(f"taxa negativa em {chave}")
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
        },
        "factors": fatores,
    }


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza a base da Taxa Legal (BCB SGS 29543)")
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
