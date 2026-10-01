# Ponto de interrupção — Etapa 7C (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 7C: datas futuras, overrides manuais de índices e atualização de valor-base*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend
.venv/bin/python -m pytest        # use sempre workdir explícito (cwd padrão do tool é o caminho antigo)
```

## O que já está pronto (commits)

1. `e1d29be` Etapa 0 — estrutura.
2. `45d1668` Etapa 1 — FastAPI, SQLite, indexadores, Tabela Prática TJSP.
3. `2b1a2f1` Etapa 2 — correção monetária (Decimal).
4. `6df8372` Etapa 3 — Taxa Legal + juros.
5. `d41547c` Etapa 4 — salário mínimo + alimentos.
6. `9e57740` Etapa 5 — parcelas, encargos, agregação.
7. `adc6afb` Etapa 6 — API `POST/GET /api/calculos`, código VEC.
8. `f7af1db` Etapa 7A — memória `memoria-calculo/1.0`.
9. `1d0f475` Etapa 7B — PDF/XLSX a partir da memória.
10. Etapa 7C — datas futuras + cadastro manual de índices + `tipo=atualizacao`.

Situação conhecida: **175 testes verdes** após a Etapa 7C.

## Etapa 7C — o que foi commitado

### Cadastro manual de índices (sem UI administrativa)

- `IndexerOverride` (SQLite): key, competencia, valor, fonte, observacao; unique (key, competencia).
- `app/indexers/overrides.py`: cadastro, listagem, cobertura efetiva, store em memória para o cálculo.
- `MonthlyIndexer.valor()`: override → oficial → `CoverageError` (**nunca** usa o último índice).
- **Regra:** se a competência já existe na série oficial, o cadastro manual é **rejeitado** (não substitui histórico).

### API

- `GET /api/indexers/{key}/cobertura` — oficial + manual + cobertura efetiva.
- `GET/POST /api/indexers/{key}/overrides` — listagem e cadastro manual.

### Atualização de valor-base (`tipo="atualizacao"`)

- Payload: `valor_base {valor, data_base, descricao}` + `data_base`/`data_final` (data escolhida).
- Motor de correção já existente; juros/multa/honorários só se pedidos.
- Sem cobertura → `CoverageError` (422). Com override manual no período → cálculo usa o override e registra em `overrides_utilizados`.

### Memória `memoria-calculo/1.1` (aditiva)

- `atualizacao`: valor original, data_base, data_final, fatores, versão do indexador, valor atualizado.
- `overrides_utilizados`: entradas manuais efetivamente usadas.
- Export 7B continua válido (chaves extras ignoradas).

## Próximas etapas

- **Etapa 7D (opcional):** enriquecer PDF/XLSX com bloco `atualizacao` e overrides.
- **Etapa 8:** frontend React (Vite + TS + Tailwind).

## Regras que não mudam

- `Decimal` + `ROUND_HALF_UP`; nunca inventar dados; bases oficiais só via scripts.
- Cobertura insuficiente → `CoverageError`; nunca auto-estender com o último índice.
- Testar após cada etapa; commit por etapa com
  `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
