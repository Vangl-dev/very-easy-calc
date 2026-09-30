from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

FONTE_URL = (
    "https://www.ipeadata.gov.br/api/odata4/Metadados('MTE12_SALMIN12')/Valores"
)
FONTE_LABEL = (
    "Salário mínimo vigente — Ipeadata (série MTE12_SALMIN12, Ministério da Economia)"
)
COBERTURA_MINIMA = (1994, 7)
SAIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "salario_minimo.json"
PROVENIENCIA = Path(__file__).resolve().parents[1] / "app" / "data" / "salario_minimo_ipea_raw.json"

NOTA = (
    "Competências anteriores a 07/1994 não foram incluídas: a série da fonte traz "
    "valores de períodos anteriores ao Plano Real em unidade não comparável com o "
    "nominal em Reais. Antes de estender a cobertura, conferir os valores contra os "
    "decretos/leis de fixação de cada ano."
)


def baixar(url: str = FONTE_URL) -> list[dict]:
    with urllib.request.urlopen(url, timeout=60) as resposta:
        corpo = json.loads(resposta.read().decode("utf-8"))
    registros = corpo.get("value") if isinstance(corpo, dict) else None
    if not registros:
        raise SystemExit("resposta vazia ou inesperada da API do Ipeadata")
    return registros


def normalizar(brutos: list[dict]) -> list[dict]:
    fatores: list[dict] = []
    for registro in brutos:
        ano, mes = int(registro["VALDATA"][:4]), int(registro["VALDATA"][5:7])
        if (ano, mes) < COBERTURA_MINIMA:
            continue
        valor = Decimal(str(registro["VALVALOR"]))
        if valor != valor.quantize(Decimal("0.01")):
            raise SystemExit(f"valor nao monetario em {ano}-{mes:02d}: {registro['VALVALOR']}")
        fatores.append(
            {
                "year": ano,
                "month": mes,
                "factor": float(valor),
                "sourceValue": str(valor),
                "sourceDate": registro["VALDATA"][:10],
            }
        )
    fatores.sort(key=lambda r: (r["year"], r["month"]))
    return fatores


def validar(fatores: list[dict]) -> list[str]:
    problemas: list[str] = []
    anterior: tuple[int, int] | None = None
    vistos: set[tuple[int, int]] = set()
    for registro in fatores:
        atual = (registro["year"], registro["month"])
        if atual in vistos:
            problemas.append(f"competência duplicada: {atual}")
        vistos.add(atual)
        if anterior is not None:
            ano, mes = anterior
            esperado = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
            if atual != esperado:
                problemas.append(f"lacuna entre {ano}-{mes:02d} e {atual[0]}-{atual[1]:02d}")
        if Decimal(str(registro["factor"])) <= 0:
            problemas.append(f"valor não positivo em {atual}")
        anterior = atual
    return problemas


def montar(fatores: list[dict], atualizado_em: str | None = None) -> dict:
    ultimo = fatores[-1]
    return {
        "metadata": {
            "source": "Ipeadata / Ministério da Economia",
            "sourceUrl": FONTE_URL,
            "sourceLabel": FONTE_LABEL,
            "version": f"{ultimo['year']:04d}.{ultimo['month']:02d}",
            "updatedAt": atualizado_em or date.today().isoformat(),
            "lastMonth": f"{ultimo['year']:04d}-{ultimo['month']:02d}",
            "totalRecords": len(fatores),
            "note": NOTA,
        },
        "factors": fatores,
    }


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza a série do salário mínimo (Ipeadata)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arquivo", type=Path)
    args = parser.parse_args(argv)

    brutos = json.loads(args.arquivo.read_text(encoding="utf-8")) if args.arquivo else baixar()
    if not isinstance(brutos, list):
        raise SystemExit("JSON de origem deve ser uma lista de registros")
    if not args.arquivo:
        PROVENIENCIA.write_text(
            json.dumps(brutos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

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
