# Ponto de interrupção — UX Cível: lançamento simples + resultado (commitada)

Salvo em 01/10/2026. Último commit: *UX Cível: lançamento simples + tela de resultado auditável*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build
```

Dev: backend `:8001` · frontend `http://localhost:5173`

## Estado

- Backend: **184 testes verdes**
- Frontend: `npm run build` OK
- Fluxo Cível: lançamento → `POST` → `/calculos/:codigo`

## UX Etapa 9B

### Tela 1 — Lançamento simples (`/novo-calculo?tipo=parcelas`)

- Identificação + **data da atualização**
- Tabela: **Verba | Valor | Início correção | Início juros**
- `+ Incluir verba`
- `Configurar detalhes` expande painel avançado (fim correção/juros, indexador, modalidade, multa, honorários, pagamentos)
- `Gerar cálculo` → navega para o resultado

### Tela 2 — Resultado (`/calculos/:codigo`)

- Resumo do backend (total, saldo, principal…)
- `TabelaAuditoria`: Verba, Competência, Vencimento, Valor original, Início correção, Correção, Início juros, Juros, Multa, Honorários, Pagamento, Saldo, Total
- Header fixo, 1ª coluna sticky, scroll horizontal, agrupamento por verba, totais no rodapé (valores do backend)
- Ações: **Baixar PDF**, **Salvar XLSX**, **Copiar tabela**, **Voltar/Editar cálculo**

Motor/API intactos. Payload `verbas[]` inalterado.

## Próximas etapas

- Prefill de edição a partir de cálculo salvo
- Overrides de índices na UI de Bases
- Exportar tabela com o PDF/XLSX (já gerados no backend)
