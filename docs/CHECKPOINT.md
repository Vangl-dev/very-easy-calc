# Ponto de interrupção — Etapa 8B (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 8B: formulário de Novo cálculo (Cível) ligado ao POST /api/calculos*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build && npm run dev
```

## Estado

- Backend: **175 testes verdes**
- Frontend: `npm run build` OK
- Último commit backend/frontend: Etapa 8B

## Etapa 8B — o que foi commitado

Formulário de **Cálculo Cível** em `/novo-calculo?tipo=parcelas`:

- Seções: identificação, valor-base + datas, correção/juros/multa/honorários, pagamentos
- Interruptores explícitos de **não aplicar**
- Datas passadas/futuras; data-final **não** preenchida com hoje
- Aviso amigável quando a cobertura efetiva do indexador não alcança a data-final
- Passo de **revisão** antes do envio
- Após sucesso: código VEC + links PDF/XLSX/memória/Meus cálculos
- Erros 422/CoverageError traduzidos para mensagens compreensíveis

**Payload enviado** (`tipo=parcelas`): 1 parcela com `vencimento=data-base`, `principal=valor-base`, `data_base=data_final`, configs explícitas de correção/juros/encargos e pagamentos na parcela.

**Não implementado:** editor multi-parcela, formulário completo de alimentos/atualização. React não calcula índices/juros/salário mínimo.

## Próximas etapas

- **Etapa 8C:** formulários de Alimentos e Atualização monetária
- Editor avançado de parcelas
- Detalhe de memória na UI com download integrado
