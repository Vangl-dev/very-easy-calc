# Very Easy Calc

> **Very Easy Calc — cálculos judiciais sem complicação.**

Aplicação web moderna para elaboração de cálculos judiciais extensos: dezenas ou
centenas de parcelas, correção monetária individualizada, juros, multa,
honorários, pagamentos e memória de cálculo auditável.

## Princípio fundamental

O sistema **não presume** que toda parcela sofre todas as incidências.
Cada componente é configurado independentemente, e **"não aplicar" é uma regra
válida e explícita**. O aplicativo executa os parâmetros definidos pelo usuário —
ele não decide qual interpretação jurídica é correta.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Backend | Python + FastAPI |
| Banco | SQLite (arquitetura preparada para PostgreSQL) |
| Relatórios | ReportLab (PDF) |
| Planilhas | openpyxl (XLSX) |
| Infra | Docker + Docker Compose |

## Estrutura

```
very-easy-calc/
├── frontend/      React + Vite + TS + Tailwind
├── backend/       FastAPI, motor de cálculo, indexadores, exportação
├── database/      SQLite e migrações
├── docs/          Documentação
├── tests/         Testes transversais
├── docker/        Configurações de container
├── docker-compose.yml
├── README.md
└── .env.example
```

## Indexadores do MVP

1. **Tabela Prática do TJSP** (correção monetária, série IPCA-E acumulada)
2. **Salário mínimo** (série histórica por competência)
3. **Taxa Legal** (juros, série BCB SGS 29543)

A arquitetura permite adicionar novos indexadores (IPCA, IPCA-E, INPC, IGP-M,
TR, SELIC, UFESP, índices de outros tribunais) sem reescrever o motor.

## Versionamento e rastreabilidade

Cada base de índice é **imutável e versionada** (fonte, versão, data de
atualização, período coberto). Cada cálculo registra:

- identificador (`VEC-AAAA-NNNNNN`);
- versão do aplicativo;
- data/hora;
- versão exata de cada base utilizada;
- parâmetros e resultado.

Um cálculo antigo é sempre reproduzível com as mesmas bases — nunca é
recalculado silenciativamente com índices novos.

Se o período solicitado não estiver coberto pela base disponível, o sistema
**emite alerta e não completa o cálculo silenciosamente**.

## Desenvolvimento

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest

# Frontend
cd frontend
npm install
npm run dev

# Tudo via Docker
docker compose up --build
```

## Licença

Uso interno. Não distribuir sem autorização.
