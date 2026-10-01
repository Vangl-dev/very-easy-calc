# Ponto de interrupção — Etapa 8 (estrutura visual, commitada)

Salvo em 01/10/2026. Último commit: *Etapa 8: frontend React/Vite/TS/Tailwind — layout, dashboard e componentes base*.

## Como retomar

```bash
# Backend
cd /home/vanessa/Projetos/very-easy-calc/backend
.venv/bin/python -m pytest

# Frontend
cd /home/vanessa/Projetos/very-easy-calc/frontend
npm install
npm run build
npm run dev
```

- Frontend dev: `http://localhost:5173`
- Backend: `http://localhost:8000` (`VITE_API_BASE_URL`)

## O que já está pronto (commits)

1–7. Etapas 0–7C (backend, memória, PDF/XLSX, overrides, atualização).
8. Etapa 8 — frontend: layout, header, navegação, dashboard, componentes base.

Situação conhecida: **175 testes backend verdes** + `npm run build` do frontend OK.

## Etapa 8 — o que foi commitado

Estrutura em `frontend/`:

- Vite + React 19 + TypeScript + Tailwind + React Router
- `src/components/ui/` — Button, Card, Message, Table, Form (Input/Select/Textarea), Tooltip (`ⓘ` via CSS)
- `src/components/layout/` — Header, Navigation, Layout, AppShell
- `src/pages/` — Dashboard, Novo cálculo (placeholder), Meus cálculos, Bases/Indexadores
- `src/lib/api.ts` — cliente HTTP somente leitura (health, cálculos, indexadores)

Dashboard expõe: Cível, Alimentos, Atualização monetária, Memória de cálculo, PDF/XLSX.
Navegação preparada: Novo cálculo, Meus cálculos, Bases/Indexadores.

**Não implementado nesta fase:** formulário completo de cálculo, regras matemáticas no React, mudanças no motor/API.

## Próximas etapas

- **Etapa 8B:** formulário de novo cálculo ligado ao `POST /api/calculos` (sem duplicar regras).
- Detalhe de memória + download integrado de PDF/XLSX na UI.
- Overrides de índices na tela de Bases.

## Regras que não mudam

- Backend é fonte única de cálculo; frontend não recalcula.
- Testar backend + build frontend antes de commit.
- `git -c user.name="Vanessa" -c user.email="vanessa@local" commit`.
