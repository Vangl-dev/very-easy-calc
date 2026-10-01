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

- Frontend: `http://localhost:5173`
- API: `http://localhost:8001` (`VITE_API_BASE_URL` em `frontend/.env`)

## Build

```bash
npm run build
npm run preview
```
