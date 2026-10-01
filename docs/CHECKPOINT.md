# Ponto de interrupção — Etapa 7B (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 7B: exportação PDF/XLSX a partir da memória de cálculo*.

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
6. `9e57740` Etapa 5 — bases, encargos, parcela composta, agregação `calcular()`.
7. `adc6afb` Etapa 6 — API de cálculos (`POST /api/calculos`, `GET /api/calculos/{codigo}`), código `VEC-AAAA-NNNNNN`.
8. `f7af1db` Etapa 7A — memória de cálculo (`memoria-calculo/1.0`) em `memoria_json`.
9. Etapa 7B — PDF (ReportLab) e XLSX (openpyxl) a partir exclusivamente da memória.

Situação conhecida: **163 testes verdes** após a Etapa 7B.

## Etapa 7B — o que foi commitado

- `app/export/comum.py` — helpers de leitura da memória (Decimal/BRL/%); sem recálculo.
- `app/export/pdf.py` — `gerar_pdf(memoria)`: cabeçalho Very Easy Calc, identificação, critérios, bases, resumo, tabela de parcelas com paginação/cabeçalho-rodapé.
- `app/export/xlsx.py` — `gerar_xlsx(memoria)`: planilhas `Resumo` e `Parcelas`; valores monetários como números.
- `app/main.py` — `GET /api/calculos/{codigo}/pdf` e `.../xlsx` (404 se ausente).
- `tests/test_export_relatorios.py` — 10 testes.

### Regras da exportação

- Fonte exclusiva: `memoria_json`.
- Não recalcula, não consulta indexadores, não aplica regras novas.
- Alimentos: competência, salário mínimo, percentual/regra, principal, pagamento, saldo, correção, juros, total.
- XLSX: `Salário mínimo`, `Percentual`, `Principal` etc. como números (não texto).

## Próximas etapas

- **Etapa 8:** frontend React (Vite + TS + Tailwind).

## Regras que não mudam

- `Decimal` + `ROUND_HALF_UP`; juros arredondados por trecho; `principal + correcao == valor_corrigido`.
- Nunca inventar dados, fontes ou doutrina; bases só via scripts oficiais (`backend/scripts/update_*.py`).
- Testar após cada etapa; só declarar "pronto" depois de pytest verde.
- Pasta: `/home/vanessa/Projetos/very-easy-calc`; commit por etapa com
  `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
