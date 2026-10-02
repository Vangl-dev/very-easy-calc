from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

FONTE_ORIGEM = "AASP"
FONTE_URL = (
    "https://www.aasp.org.br/produtos-servicos/indices-economicos/"
    "indices-judiciais/tabela-pratica-para-calculo-de-atualizacao-monetaria-ipca-e/"
)
FONTE_LABEL = "Tabela Pratica do Tribunal de Justica de Sao Paulo (IPCA-E)"
SAIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "tjsp_tabela_pratica.json"
PROVENIENCIA = Path(__file__).resolve().parents[1] / "app" / "data" / "tjsp_aasp_raw.json"
MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
USER_AGENT = "very-easy-calc/1.0 (+atualizador oficial da Tabela Prática TJSP)"


def baixar(url: str = FONTE_URL) -> str:
    requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        corpo = resposta.read().decode("utf-8", "replace")
    if "Ano/Mês" not in corpo:
        raise SystemExit("página da AASP sem a tabela esperada (cabeçalho 'Ano/Mês')")
    return corpo


def _celulas(linha: str) -> list[str]:
    brutas = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", linha, flags=re.S | re.I)
    limpas = []
    for celula in brutas:
        texto = re.sub(r"<[^>]+>", " ", celula)
        texto = texto.replace("&nbsp;", " ").replace("&aacute;", "á")
        limpas.append(" ".join(texto.split()))
    return limpas


def extrair_linhas(pagina: str) -> list[dict]:
    linhas: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", pagina, flags=re.S | re.I):
        celulas = _celulas(tr)
        if not celulas or not re.fullmatch(r"\d{4}", celulas[0]):
            continue
        linhas.append({"year": int(celulas[0]), "cells": celulas[1:13]})
    if not linhas:
        raise SystemExit("nenhuma linha de ano foi encontrada na tabela da AASP")
    return linhas


def para_float(texto: str) -> float:
    normalizado = texto.strip().replace(" ", "")
    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    return float(normalizado)


def normalizar(linhas: list[dict]) -> list[dict]:
    fatores: list[dict] = []
    for linha in linhas:
        for indice, celula in enumerate(linha["cells"], start=1):
            if not celula:
                continue
            fatores.append(
                {
                    "year": linha["year"],
                    "month": indice,
                    "factor": para_float(celula),
                    "sourceValue": celula,
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
                problemas.append(f"lacuna entre {ano}-{mes:02d} e {atual[0]:04d}-{atual[1]:02d}")
        anterior = atual
    vistos: set[tuple[int, int]] = set()
    for registro in fatores:
        chave = (registro["year"], registro["month"])
        if chave in vistos:
            problemas.append(f"competência duplicada: {chave[0]:04d}-{chave[1]:02d}")
        vistos.add(chave)
        if registro["factor"] <= 0:
            problemas.append(f"fator inválido em {chave[0]:04d}-{chave[1]:02d}")
    return problemas


def carregar_existente() -> dict | None:
    if not SAIDA.exists():
        return None
    return json.loads(SAIDA.read_text(encoding="utf-8"))


def comparar_com_existente(fatores: list[dict]) -> list[str]:
    """O histórico publicado não pode divergir silenciosamente do que já está na base."""
    existente = carregar_existente()
    if not existente:
        return []
    anteriores = {
        (r["year"], r["month"]): float(r["factor"]) for r in existente.get("factors", [])
    }
    novos = {(r["year"], r["month"]): float(r["factor"]) for r in fatores}
    problemas: list[str] = []
    for chave, valor in sorted(anteriores.items()):
        if chave not in novos:
            problemas.append(f"a fonte publicada não tem mais {chave[0]:04d}-{chave[1]:02d}")
            continue
        if abs(novos[chave] - valor) > 1e-9:
            problemas.append(
                f"divergência em {chave[0]:04d}-{chave[1]:02d}: base {valor} vs fonte {novos[chave]}"
            )
    ultimo_existente = max(anteriores) if anteriores else None
    ultimo_novo = max(novos) if novos else None
    if ultimo_existente and ultimo_novo and ultimo_novo < ultimo_existente:
        problemas.append(
            f"a fonte publicada termina antes da base atual "
            f"({ultimo_novo[0]:04d}-{ultimo_novo[1]:02d} < {ultimo_existente[0]:04d}-{ultimo_existente[1]:02d})"
        )
    return problemas


def montar(fatores: list[dict], atualizado_em: str | None = None) -> dict:
    ultimo = fatores[-1]
    return {
        "metadata": {
            "source": FONTE_ORIGEM,
            "sourceUrl": FONTE_URL,
            "sourceLabel": FONTE_LABEL,
            "version": f"{ultimo['year']:04d}.{ultimo['month']:02d}",
            "updatedAt": atualizado_em or date.today().isoformat(),
            "lastMonth": f"{MESES[ultimo['month'] - 1]}/{ultimo['year']:04d}",
            "totalRecords": len(fatores),
        },
        "factors": [
            {"year": r["year"], "month": r["month"], "factor": r["factor"]} for r in fatores
        ],
    }


def _imprimir_problemas(rotulo: str, problemas: list[str]) -> None:
    print(f"{rotulo} FALHOU:", file=sys.stderr)
    for problema in problemas:
        print(f"  - {problema}", file=sys.stderr)


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atualiza a base da Tabela Prática TJSP (IPCA-E) a partir da AASP"
    )
    parser.add_argument("--dry-run", action="store_true", help="não grava o arquivo")
    parser.add_argument("--arquivo", type=Path, help="usa HTML local da página da AASP")
    args = parser.parse_args(argv)

    pagina = args.arquivo.read_text(encoding="utf-8") if args.arquivo else baixar()
    linhas = extrair_linhas(pagina)
    fatores = normalizar(linhas)

    problemas = validar(fatores) + comparar_com_existente(fatores)
    if problemas:
        _imprimir_problemas("VALIDACAO", problemas)
        return 1

    documento = montar(fatores)
    proveniencia = {
        "source": FONTE_ORIGEM,
        "sourceUrl": FONTE_URL,
        "retrievedAt": date.today().isoformat(),
        "rows": linhas,
    }

    if args.dry_run:
        print(json.dumps(documento["metadata"], ensure_ascii=False, indent=2))
        return 0

    SAIDA.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    PROVENIENCIA.write_text(
        json.dumps(proveniencia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(documento["metadata"], ensure_ascii=False, indent=2))
    print(f"gravado: {SAIDA}")
    print(f"proveniência: {PROVENIENCIA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
