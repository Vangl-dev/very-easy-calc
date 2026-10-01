# Ponto de interrupção — Verbas independentes (commitada)

Salvo em 01/10/2026. Último commit: *Verbas independentes no cálculo Cível (datas de correção/juros por verba)*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build
```

Dev (porta 8001 — 8000 ocupada por outro serviço):

```bash
cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
cd frontend && npm run dev   # http://localhost:5173
```

## Estado

- Backend: **184 testes verdes**
- Frontend: `npm run build` OK
- Memória: `memoria-calculo/1.2`

## Verbas (Cível)

O motor Etapa 5 já aceitava configs por parcela. A mudança foi na **camada de entrada** + um aditivo no motor de juros.

### Payload (`tipo=parcelas` + `verbas`)

```json
{
  "tipo": "parcelas",
  "data_base": "2026-08-31",
  "verbas": [
    {
      "nome": "Dano moral",
      "valor": "20000.00",
      "data_base": "2020-05-10",
      "correcao": {"aplicar": true, "indexador": "tjsp_tabela_pratica",
                   "termo_inicial": "2020-05", "termo_final": "2026-08"},
      "juros": {"aplicar": true, "modalidade": "fixa", "taxa": "0.01",
                "inicio": "2024-03-15", "fim": "2026-08-31"},
      "multa": {"aplicar": false},
      "honorarios": {"aplicar": false},
      "pagamentos": [],
      "parcelas": []
    },
    {
      "nome": "Honorários",
      "valor": "5000.00",
      "data_base": "2023-08-01",
      "correcao": {"aplicar": true, "termo_inicial": "2023-08"},
      "juros": {"aplicar": true, "modalidade": "fixa", "taxa": "0.01",
                "inicio": "2023-08-01"}
    }
  ]
}
```

- Cada verba → 1 parcela (ou N se `parcelas[]` preenchido).
- Datas de correção/juros **não** são globais.
- Compatível: payload antigo com `parcelas[]` e configs globais continua funcionando.

### Motor (aditivo)

- `ConfigJuros.inicio` / `ConfigJuros.fim` (opcional).
- Sem `inicio` → mantém vencimento da parcela (compatível).
- `calcular_parcela` usa `cfg_juros.inicio or vencimento` e `cfg_juros.fim or data_base`.

### Memória 1.2

- `verbas[]`: id, nome, valor, data_base, inicio_correcao, inicio_juros, parcelas.
- Cada parcela: `verba {id, nome, ...}`, `inicio_correcao`, `inicio_juros`.
- Export PDF/XLSX (7B) lê a memória — campos extras são aditivos.

### Testes

- `tests/test_engine_verbas.py` — independência no motor.
- `tests/test_api_verbas.py` — duas verbas com datas diferentes; memória; compat.

## Frontend

Formulário Cível ainda usa 1 parcela + configs globais. Próximo passo UX: cartões “Adicionar verba” enviando `verbas[]` (sem cálculos no React).

## Próximas etapas

- UX de verbas no formulário Cível.
- Editor avançado de parcelas por verba.
- Detalhe de verbas no PDF/XLSX (campos já na memória).
