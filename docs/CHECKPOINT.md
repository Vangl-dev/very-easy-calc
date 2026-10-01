# Ponto de interrupção — Etapa 6 (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 6: API de cálculos POST /api/calculos com VEC-AAAA-NNNNNN*.

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
7. Etapa 6 — API de cálculos (`POST /api/calculos`, `GET /api/calculos/{codigo}`), código `VEC-AAAA-NNNNNN`, persistência SQLite.

Situação conhecida: **142 testes verdes** após a Etapa 6.

## Etapa 6 — o que foi commitado

Módulos novos:

- `app/api/schemas.py` — Pydantic do payload (`CalculoRequest`): tipo `alimentos` | `parcelas`, regras de blocos, pagamentos por competência, configs de correção/juros/multa/honorários.
- `app/api/serializacao.py` — `ResultadoCalculo` → JSON-safe; `RastroParcela` preserva salário mínimo, percentual e origem por parcela.
- `app/api/service.py` — `executar_calculo()`: payload → `gerar_parcelas`/`ParcelaInput` → `calcular()` → serializar → gravar `Calculo` com código `VEC-AAAA-NNNNNN`.
- `tests/test_api_calculos.py` — 15 testes da API.

Alterações:

- `app/main.py`: `POST /api/calculos` (201), `GET /api/calculos/{codigo}` (404 se ausente), handler `ValueError` → 422.

### Comportamentos da API de alimentos

- 1 parcela por competência; salário mínimo daquela competência (sem retroagir o valor atual).
- Blocos de regras diferentes suportados (percentual do SM e/ou valor fixo).
- Pagamentos por `competencia` no payload; saldo por parcela.
- Correção/juros opcionais; bases versionadas em `bases` (inclui `salario_minimo`).
- Decimal monetário serializado em centavos (`"330.00"`).

## Próximas etapas

- **Etapa 7:** memória de cálculo ("Por que este valor?") + PDF (ReportLab) e XLSX (openpyxl).
- **Etapa 8:** frontend React (Vite + TS + Tailwind).

## Regras que não mudam

- `Decimal` + `ROUND_HALF_UP`; juros arredondados por trecho; `principal + correcao == valor_corrigido`.
- Nunca inventar dados, fontes ou doutrina; bases só via scripts oficiais (`backend/scripts/update_*.py`).
- Testar após cada etapa; só declarar "pronto" depois de pytest verde.
- Pasta: `/home/vanessa/Projetos/very-easy-calc`; commit por etapa com
  `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
