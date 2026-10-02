# Ponto de interrupção — Testes funcionais Cível + Alimentos (até 30/09/2026)

Salvo em 02/10/2026.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build
```

Dev: backend `:8001` (`nohup .venv/bin/python -m uvicorn app.main:app --port 8001 &`) · frontend `http://localhost:5173` (`VITE_API_BASE_URL=http://localhost:8001`)

## Estado

- Backend: **186 testes verdes** (inclui `tests/test_funcional_civel_alimentos.py`)
- Frontend: `npm run build` OK
- Memória: `memoria-calculo/1.3` (campo `diferenca` por parcela)

## Etapa 10 — Testes funcionais

### Base oficial TJSP

- `backend/scripts/update_tjsp.py` baixa a Tabela Prática na AASP, valida continuidade
  e **recusa divergência com o histórico já gravado** (não reescreve passado).
- Base atual: **2026.09 — Setembro/2026 = 8,566509** (valor publicado, histórico intacto).
- Proveniência: `backend/app/data/tjsp_aasp_raw.json`.
- Reexecutar: `cd backend && .venv/bin/python scripts/update_tjsp.py [--dry-run]`.

### TESTE 1 — Cível (`tipo: parcelas`, data-base 30/09/2026)

- 8 verbas independentes: Valor da causa 44.000,00 (correção desde 08/2022, juros desde 24/04/2026),
  Honorários sucumbenciais 12% = 5.280,00 (mesma correção, mesmos juros) e 6 custas
  **só com correção** (`juros.aplicar=false` → motivo explícito na memória).
- Verba "honorários da fase de cumprimento (10%)" ignorada por decisão do usuário.

### TESTE 2 — Alimentos (`tipo: alimentos`, até 09/2026)

- 42 parcelas (abr/2023 → set/2026), uma por competência, salário mínimo da própria
  competência (1302 → 1320 → 1412 → 1518 → 1621 conforme Ipeadata).
- Correção Tabela Prática mês a mês + juros **1% a.m. (modalidade fixa)** desde o
  vencimento de cada débito; tudo até 30/09/2026.
- R$ 200,00/mês em jan/2026..set/2026 = pagamento parcial: `diferenca = devido − pago`
  e `saldo = total atualizado − pago` (o pagamento não bloqueia a atualização).

### Frontend

- `SecaoAtualizacaoAlimentos.tsx`: interruptores de correção (TJSP) e juros
  (taxa fixa 0,01 = 1% a.m. ou Taxa Legal) — antes estavam fixos em `aplicar: false`.
- `TabelaAuditoria.tsx`: colunas próprias de alimentos (Salário mínimo, % devido,
  Devido, Índice, Pago, Diferença) e agrupamento único (antes: 1 grupo por parcela).

### Exportação

- XLSX/PDF ganharam **Início correção, Início juros, Diferença, Índice (fator)**.
- PDF em paisagem; seção "Verbas do cálculo"; critérios mostram
  "configurada por verba" quando o cálculo é por verbas.
- `pct_memoria` corrigido: 0,85 → **85%** (mostrava "0,85%").

## Próximas etapas

- Prefill de edição a partir de cálculo salvo
- Overrides de índices na UI de Bases
- Atualizar `update_salario_minimo.py`/`update_taxa_legal.py` já existem; TJSP agora também
