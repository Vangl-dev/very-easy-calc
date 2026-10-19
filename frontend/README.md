# Very Easy Calc — frontend (Vite)

React + Vite + TypeScript + Tailwind CSS.

## Desenvolvimento

```bash
# Backend (porta 8001 — a 8000 pode estar ocupada por outro serviço)
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

- Frontend: `http://localhost:5173` (ou `http://<IP-da-lan>:5173` com `npm run dev -- --host 0.0.0.0`)
- API: mesma origem — o Vite repassa `/api/*` ao backend via proxy
  (`VITE_API_PROXY_TARGET` em `frontend/.env`, padrão `http://127.0.0.1:8001`).
  `VITE_API_BASE_URL` vazio = same-origin; defina uma URL absoluta só se a API
  estiver em outra origem (aí o CORS do backend precisa permitir essa origem).

## Build

```bash
npm run build
npm run preview
```
