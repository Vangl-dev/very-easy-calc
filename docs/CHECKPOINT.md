# Ponto de interrupção — Etapa 5 (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 5: modelo de parcelas (multa, honorários, pagamentos, saldo) e agregação de cálculos*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend
.venv/bin/python -m pytest        # use sempre workdir explícito (cwd padrão do tool é o caminho antigo)
```

## O que já está pronto (commits)

1. `e1d29be` Etapa 0 — estrutura, README, .gitignore, .env.example.
2. `45d1668` Etapa 1 — FastAPI, SQLite, registry de indexadores, Tabela Prática TJSP.
3. `2b1a2f1` Etapa 2 — motor de correção monetária (Decimal, ROUND_HALF_UP, cobertura explícita).
4. `6df8372` Etapa 3 — Taxa Legal (BCB SGS 29543 oficial) + juros com 3 eras configuráveis.
5. `d41547c` Etapa 4 — salário mínimo (Ipeadata) + gerador de parcelas de alimentos.
6. Etapa 5 — bases de cálculo, encargos (multa/honorários), parcela composta, agregação `calcular()`.

Situação conhecida: **127 testes verdes** após a Etapa 5.

## Etapa 5 — o que foi commitado

Módulos novos:

- `app/engine/bases.py` — `BASE_PRINCIPAL`/`BASE_CORRIGIDO`/`BASE_COM_JUROS`, `ROTULOS_BASE`, `ValoresBase`, `construir_bases()`.
- `app/engine/encargos.py` — `ConfigEncargo`, `ResultadoEncargo`, `calcular_encargo()`, `Pagamento`, `total_pagamentos()`.
- `app/engine/configuracao.py` — `ConfiguracaoCalculo` (data_base + correção/juros/multa/honorários padrão).
- `app/engine/parcela.py` — `ParcelaInput` (configs `| None` que caem para a configuração geral), `ResultadoParcela`, `calcular_parcela(p, configuracao=...)`.
- `app/engine/calculo.py` — `calcular()`, `ResumoCalculo`, `ResultadoCalculo`, `coletar_bases()`, `BaseUtilizada`.

Testes novos: `tests/test_engine_encargos.py`, `tests/test_engine_calculo.py`, `tests/test_engine_parcela.py`.

Alterações:

- `app/core/money.py`: `percentual_txt()` (corrige `rstrip("0")` que virava `30%`→`3%`); `juros.py` e `alimentos.py` usam o helper.
- `app/engine/juros.py`: `ConfigJuros.incidencia` → `ConfigJuros.base` (`BASE_*`), validada no `__post_init__`.
- `app/engine/alimentos.py`: `Parcela.usou_salario_minimo` + `para_entrada()` / `entradas_de_alimentos()`.
- `tests/test_indexers_salario_minimo.py`: proveniência Ipeadata comparada com `round_brl` (centavos), sem artefato de float.

## Próximas etapas

- **Etapa 6:** API de cálculos — `POST /api/calculos` com versionamento `VEC-AAAA-NNNNNN`, persistência do JSON do cálculo, `GET /api/calculos/{codigo}`.
- **Etapa 7:** memória de cálculo ("Por que este valor?") + PDF (ReportLab) e XLSX (openpyxl).
- **Etapa 8:** frontend React (Vite + TS + Tailwind).

## Regras que não mudam

- `Decimal` + `ROUND_HALF_UP`; juros arredondados por trecho; `principal + correcao == valor_corrigido`.
- Nunca inventar dados, fontes ou doutrina; bases só via scripts oficiais (`backend/scripts/update_*.py`).
- Testar após cada etapa; só declarar "pronto" depois de pytest verde.
- Pasta: `/home/vanessa/Projetos/very-easy-calc`; commit por etapa com
  `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
