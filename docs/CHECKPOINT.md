# Ponto de interrupção — Etapa 7A (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 7A: memória de cálculo como fonte única para PDF/XLSX*.

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
8. Etapa 7A — memória de cálculo (`memoria-calculo/1.0`) persistida em `memoria_json`.

Situação conhecida: **153 testes verdes** após a Etapa 7A.

## Etapa 7A — o que foi commitado

- `app/engine/memoria.py` — `ESQUEMA_MEMORIA`, `montar_memoria()`; monta a memória **a partir do resultado já calculado** (sem recalcular).
- `app/models/entities.py` — coluna `memoria_json` em `Calculo`.
- `app/db.py` — `ALTER TABLE` seguro para `memoria_json` se a tabela já existir.
- `app/api/service.py` — grava e devolve `memoria` no POST.
- `app/main.py` — GET inclui `memoria`; `GET /api/calculos/{codigo}/memoria`.
- `tests/test_memoria_calculo.py` — 11 testes.

### Estrutura da memória (`memoria-calculo/1.0`)

- `codigo` (VEC), `tipo`, `identificacao` (título/processo/parte/app/data/data_base)
- `criterios` — correção/juros/multa/honorários, regras de alimentos, pagamentos informados
- `bases` — key, versão, fonte, papel, cobertura
- `resumo` — totais já calculados
- `parcelas` — competência, vencimento, principal, pagamentos, saldo, correção, juros, multa/honorários, total; em alimentos: `regra` (tipo, origem, detalhe, salário mínimo, percentual)
- `avisos`

A memória é a fonte única para o futuro PDF/XLSX (Etapa 7B). Não altera o motor das Etapas 4–5.

## Próximas etapas

- **Etapa 7B:** PDF (ReportLab) + XLSX (openpyxl) a partir da memória.
- **Etapa 8:** frontend React (Vite + TS + Tailwind).

## Regras que não mudam

- `Decimal` + `ROUND_HALF_UP`; juros arredondados por trecho; `principal + correcao == valor_corrigido`.
- Nunca inventar dados, fontes ou doutrina; bases só via scripts oficiais (`backend/scripts/update_*.py`).
- Testar após cada etapa; só declarar "pronto" depois de pytest verde.
- Pasta: `/home/vanessa/Projetos/very-easy-calc`; commit por etapa com
  `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
