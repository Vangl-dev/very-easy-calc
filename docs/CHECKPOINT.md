# Ponto de interrupção — Frontend Cível por VERBAS (commitada)

Salvo em 01/10/2026. Último commit: *Frontend Cível: formulário por VERBAS com datas independentes*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build
```

Dev:

```bash
cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
cd frontend && npm run dev   # http://localhost:5173
```

## Estado

- Backend: **184 testes verdes**
- Frontend: `npm run build` OK
- Formulário Cível envia `verbas[]`

## Frontend Cível por verbas

`/novo-calculo?tipo=parcelas`:

- Identificação + **data-base do cálculo** (referência)
- Botão **+ Adicionar verba**
- Cada verba em Card independente:
  - nome, valor, data-base/vencimento
  - correção: aplicar/não, **desde**, até, indexador
  - juros: aplicar/não, **desde**, até, modalidade/taxa/base
  - multa/honorários opcionais
  - pagamentos da verba
- Revisão lista cada verba com seus marcos
- Total geral **após envio**, vindo do backend

Payload: `tipo=parcelas` + `verbas[]` (configs globais neutras). Payload antigo com `parcelas[]` continua suportado pela API.

React não calcula correção, juros ou totais.

## Próximas etapas

- Editor avançado de parcelas por verba
- Detalhe de verbas no PDF/XLSX (campos já na memória 1.2)
- Overrides de índices na UI de Bases
