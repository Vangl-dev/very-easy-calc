# Ponto de interrupção — Testes funcionais Cível + Alimentos (até 30/09/2026)

Salvo em 02/10/2026.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm test && npm run build
```

Dev: backend `:8001` (`nohup .venv/bin/python -m uvicorn app.main:app --port 8001 &`) · frontend `http://localhost:5173` (`VITE_API_BASE_URL=http://localhost:8001`)

## Estado

- Backend: **294 testes verdes** (inclui `tests/test_funcional_civel_alimentos.py`)
- Frontend: `npm test` **68 verdes** (vitest + jsdom) · `npm run build` OK
- Memória: `memoria-calculo/1.5` (campo `diferenca` por parcela + regra auditável do total)
- Último commit: **`6d3b735` UX Alimentos** (02/10/2026)

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

- **UX de Alimentos refeita (`6d3b735`)**: `FormAlimentos.tsx` virou tela de
  lançamento em 5 blocos — Identificação · Regra (percentual do SM `[%]` ou valor
  fixo, período inicial–final, `+ Nova regra`) · Pagamentos (tabela
  Competência | Data | Valor, `+ Adicionar pagamento`) · Atualizar até ·
  **`Gerar cálculo`** → `/calculos/{codigo}`.
- Sem interruptores de correção/juros na tela: o padrão do MVP sai fixo no envio
  (Tabela Prática TJSP + juros 1% a.m. desde o vencimento de cada competência).
  Lógica pura (validação + payload + conversão do percentual) em
  `features/novo-calculo/alimentos.ts`; secções antigas
  (`SecaoBlocos/Pagamentos/AtualizacaoAlimentos`) removidas.
- **Bug do botão corrigido**: os erros de validação eram calculados no passo
  `formulario` mas só renderizados no cartão de revisão (alcançado só quando a
  validação passa) → dado fora do formato deixava o clique mudo. Agora aparecem
  no topo, sempre; teste de regressão em `FormAlimentos.test.tsx`.
- Percentual digitado em `%` (85) é convertido para a fração do backend (0.85);
  sem isso o total saía 100× (6.795.374,35 em vez de 67.953,75).
- `TabelaAuditoria.tsx`: colunas próprias de alimentos na ordem da planilha
  (Data do pagamento, Mês, Ano, Vencimento, Índice inicial, Salário mínimo,
  Percentual, Valor devido, Valor pago, Diferença, Índice/fator atual, Correção,
  Dias de juros, Juros, Multa, Saldo, Subtotal/Total) + agrupamento único;
  "Meses devidos" da planilha não existe no backend → coluna "Dias de juros".
- Testes de frontend: `cd frontend && npm test` (`vitest.config.ts`, jsdom,
  `globals: true` — sem globals o auto-cleanup do testing-library não roda).

### Exportação

- XLSX/PDF ganharam **Início correção, Início juros, Diferença, Índice (fator)**.
- PDF em paisagem; seção "Verbas do cálculo"; critérios mostram
  "configurada por verba" quando o cálculo é por verbas.
- `pct_memoria` corrigido: 0,85 → **85%** (mostrava "0,85%").

## Estabilização MVP (out/2026)

### Composição no total — `entra_no_total`

- Campo `entra_no_total` (bool | null) em `VerbaSchema`: fonte única da decisão
  de soma. `null` = padrão histórico (a verba usada como base por outra fica
  fora do total), para não alterar cálculos já salvos; valor explícito sempre
  prevalece — inclusive quando a verba é base de outra.
- Motor: `ParcelaInput.entra_no_total` filtra a soma em `calculo.py`; a verba
  base continua existindo e alimentando as derivadas.
- Memória `1.5`: `verbas[].entra_no_total` + `criterios.total_da_execucao`
  (`regra` + `verbas_fora_do_total`).
- Export: PDF/XLSX marcam a verba fora do total e explicam a regra sem expor
  nomes de campo técnicos no documento (os testes seguem barrando `base_verba_id`
  no texto do PDF).
- Frontend: select **Padrão / Sim — soma no total / Não — fica fora do total**
  no rodapé do card do lançamento; etiqueta **Fora do total** na página de
  resultado. Rascunhos antigos sem o campo enviam `null` (compatível).

### Fronteira temporal do regime

- `regime_temporal.py`: quando os juros começam antes da correção, o trecho
  "somente juros" terminava em `limite` (inclusive) enquanto a regra de juros
  aplicada terminava em `limite − 1 dia` — sobreposição de um dia entre os
  trechos do regime. Agora são contíguos (`fim = limite − 1`); regressão em
  `tests/test_regime_temporal.py::test_regime_temporal_trechos_contiguos_sem_lacuna`.

### Séries indexadoras — limitações registradas (nada atualizado)

- Cobertura conferida, contínua e sem duplicatas: Tabela Prática TJSP
  1992-01→2026-09 (417), IPCA 1979-12→2026-09 (562), SELIC 2023-01→2026-09 (45),
  Taxa Legal 2024-08→2026-09 (26), Salário mínimo 1994-07→2026-12 (390);
  metadados coerentes.
- **Limite conhecido**: BCB/Ipea já publicam dados de **2026-10** (Taxa Legal e
  SELIC), mas nenhuma série foi atualizada — a cobertura trava em `2026.09`
  nos testes e atualizar só para ganhar cobertura está fora do MVP.
  Atualização consciente = rodar `backend/scripts/update_*.py`, conferir a
  proveniência (`*_raw.json`) e ajustar os testes de metadados na mesma mudança.
- `scripts/update_*.py --dry-run` já foi executado (rede ok); só os caches
  brutos são regravados — as séries processadas não mudaram.

## Próximas etapas

- Prefill de edição a partir de cálculo salvo
- Overrides de índices na UI de Bases
- Atualizar `update_salario_minimo.py`/`update_taxa_legal.py` já existem; TJSP agora também
- `FormAtualizacao.tsx` tem o **mesmo** bug de erros invisíveis no passo `formulario`
  (ainda não corrigido — mesmo tratamento aplicado no Alimentos)
- Se "Meses devidos" for exigido na tabela de Alimentos, gerar no backend
  (não derivar datas no React)
