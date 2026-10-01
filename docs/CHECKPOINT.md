# Ponto de interrupção — Etapa 8C (concluída, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 8C: formulários de Alimentos e Atualização monetária*.

## Como retomar

```bash
cd /home/vanessa/Projetos/very-easy-calc/backend && .venv/bin/python -m pytest
cd /home/vanessa/Projetos/very-easy-calc/frontend && npm run build && npm run dev
```

## Estado

- Backend: **175 testes verdes**
- Frontend: `npm run build` OK
- Três fluxos de Novo cálculo conectados ao `POST /api/calculos`

## Etapa 8C — o que foi commitado

### Alimentos (`/novo-calculo?tipo=alimentos`)

- Identificação + período + blocos de regras (add/remove)
- Regra: `% do salário mínimo` ou `valor fixo`
- Vigência por bloco (início/fim; fim vazio = em diante)
- Pagamentos **por competência**
- Exemplo representável: 01/2021–06/2023 30% SM · 07/2023–12/2024 40% SM · 01/2025+ R$ 800
- Payload: `tipo=alimentos` + `alimentos.regras` + `alimentos.ate` + `pagamentos[].competencia`
- Backend gera parcela/competência com SM daquele período (sem retroagir)

### Atualização monetária (`/novo-calculo?tipo=atualizacao`)

- Valor-base + data-base + data-final
- Visual: **“Valor em [data-base] → atualizar até [data-final]”**
- Indexador + opção de não aplicar correção
- Consulta de cobertura antes do envio
- Payload: `tipo=atualizacao` + `valor_base` + `correcao`

### Compartilhado

- `ResultadoSucesso` (VEC, PDF, XLSX, memória, Meus cálculos)
- `FluxoFormulario` (cabeçalho, revisão)
- `SecaoIdentificacao` reutilizada
- Correção no `ErroApi`: 422 ≠ cobertura_insuficiente

**Não implementado:** editor avançado de parcelas individuais. React não calcula SM/juros/fatores.

## Próximas etapas

- Detalhe de memória na UI
- Overrides de índices na tela de Bases
- Editor avançado de parcelas (Etapa 9)
