from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

FONTE_ORIGEM = "IBGE"
FONTE_URL = "https://sidra.ibge.gov.br/tabela/1737"
FONTE_LABEL = (
    "IPCA - Numero-indice (base: dezembro de 1993 = 100), SIDRA tabela 1737"
)
SIDRA_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados/1737"
TABELA = "1737"
VARIAVEL_NUMERO_INDICE = "2266"
SAIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "ipca.json"
PROVENIENCIA = Path(__file__).resolve().parents[1] / "app" / "data" / "ibge_sidra_raw.json"
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


def _ler(url: str) -> object:
    requisicao = urllib.request.Request(url, headers={"User-Agent": "very-easy-calc/1.0"})
    with urllib.request.urlopen(requisicao, timeout=120) as resposta:
        corpo = resposta.read()
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    return json.loads(corpo.decode("utf-8"))


def url_da_serie(inicio: int, fim: int) -> str:
    consulta = urllib.parse.urlencode({"localidades": "N1[all]"})
    return f"{SIDRA_BASE}/periodos/{inicio}-{fim}/variaveis/{VARIAVEL_NUMERO_INDICE}?{consulta}"


def baixar() -> tuple[dict, str]:
    """Cobertura declarada do SIDRA e URL completa da série."""
    metadados = _ler(f"{SIDRA_BASE}/metadados")
    if not isinstance(metadados, dict):
        raise SystemExit("metadados do SIDRA inválidos")
    periodicidade = metadados.get("periodicidade") or {}
    inicio = periodicidade.get("inicio")
    fim = periodicidade.get("fim")
    if not inicio or not fim:
        raise SystemExit("SIDRA não informou a cobertura da tabela 1737")
    return metadados, url_da_serie(int(inicio), int(fim))


def para_indice(periodos: dict) -> dict[str, str]:
    if not isinstance(periodos, dict) or not periodos:
        raise SystemExit("resposta vazia ou inválida do SIDRA")
    return {chave: str(valor) for chave, valor in periodos.items()}


def extrair_serie(resposta: object) -> dict[str, str]:
    try:
        serie = resposta[0]["resultados"][0]["series"][0]["serie"]
    except (TypeError, KeyError, IndexError) as exc:
        raise SystemExit("estrutura inesperada na resposta do SIDRA") from exc
    return para_indice(serie)


def normalizar(indice: dict[str, str]) -> list[dict]:
    fatores: list[dict] = []
    for chave in sorted(indice):
        if len(chave) != 6 or not chave.isdigit():
            raise SystemExit(f"período inválido do SIDRA: {chave!r}")
        ano, mes = int(chave[:4]), int(chave[4:])
        bruto = indice[chave]
        valor = Decimal(bruto)
        if valor <= 0:
            raise SystemExit(f"número-índice não positivo em {chave}: {bruto}")
        fatores.append(
            {
                "year": ano,
                "month": mes,
                "factor": float(valor),
                "sourceValue": bruto,
            }
        )
    if not fatores:
        raise SystemExit("nenhum período devolvido pelo SIDRA")
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
                    f"lacuna entre {ano}-{mes:02d} e {atual[0]:04d}-{atual[1]:02d}"
                )
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
        (r["year"], r["month"]): float(r["factor"])
        for r in existente.get("factors", [])
    }
    novos = {(r["year"], r["month"]): float(r["factor"]) for r in fatores}
    problemas: list[str] = []
    for chave, valor in sorted(anteriores.items()):
        if chave not in novos:
            problemas.append(
                f"a fonte publicada não tem mais {chave[0]:04d}-{chave[1]:02d}"
            )
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
            "lastMonth": f"{ultimo['year']:04d}-{ultimo['month']:02d}",
            "totalRecords": len(fatores),
            "note": (
                "Número-índice oficial do IPCA (SIDRA tabela 1737, variável 2266) "
                "por competência."
            ),
        },
        "factors": [
            {"year": r["year"], "month": r["month"], "factor": r["factor"]}
            for r in fatores
        ],
    }


def _imprimir_problemas(rotulo: str, problemas: list[str]) -> None:
    print(f"{rotulo} FALHOU:", file=sys.stderr)
    for problema in problemas:
        print(f"  - {problema}", file=sys.stderr)


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atualiza a base do IPCA (IBGE SIDRA 1737, número-índice)"
    )
    parser.add_argument("--dry-run", action="store_true", help="não grava o arquivo")
    parser.add_argument("--arquivo", type=Path, help="usa JSON local no formato do SIDRA")
    args = parser.parse_args(argv)

    if args.arquivo:
        bruto = json.loads(args.arquivo.read_text(encoding="utf-8"))
        metadados, url = {"nome": "IPCA"}, str(args.arquivo)
        resposta = bruto
    else:
        metadados, url = baixar()
        resposta = _ler(url)

    indice = extrair_serie(resposta)
    fatores = normalizar(indice)

    problemas = validar(fatores) + comparar_com_existente(fatores)
    if problemas:
        _imprimir_problemas("VALIDACAO", problemas)
        return 1

    documento = montar(fatores)
    proveniencia = {
        "source": FONTE_ORIGEM,
        "sourceUrl": url,
        "retrievedAt": date.today().isoformat(),
        "tabela": TABELA,
        "variavel": VARIAVEL_NUMERO_INDICE,
        "periodicidade": metadados.get("periodicidade"),
        "registros": indice,
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
