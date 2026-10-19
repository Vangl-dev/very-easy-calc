# Very Easy Calc

**Cálculos judiciais, com memória de cálculo auditável.**

O Very Easy Calc é uma aplicação web para elaborar, revisar e exportar cálculos judiciais. O foco do MVP é tornar explícitos os critérios de cada verba, sem que o sistema escolha uma tese jurídica pelo usuário.

> Estado do projeto: MVP em desenvolvimento ativo. Antes de usar um cálculo em processo, revise os parâmetros, a cobertura das bases e o resultado com responsabilidade técnica.

![Ícone do Very Easy Calc](assets/very-easy-calc-icon.png)

## O que já faz

- Cálculos cíveis por **verbas independentes**, com datas de correção e juros próprias.
- Cálculos de **alimentos**, por competência, com percentual do salário mínimo ou valor fixo e pagamentos parciais.
- Correção monetária, juros, multa, honorários e verbas derivadas configuráveis por item.
- Regra explícita de quais verbas entram — ou não — no total da execução.
- Memória de cálculo detalhada, cálculo salvo e revisões rastreáveis.
- Exportação de memória em **PDF** e **XLSX**.
- Bases versionadas e verificação de cobertura: o sistema avisa quando um índice não alcança o período solicitado, em vez de completar o dado silenciosamente.

### Bases incluídas no MVP

| Base | Uso principal |
| --- | --- |
| Tabela Prática TJSP | Correção monetária |
| Salário mínimo | Cálculos de alimentos e verbas vinculadas |
| Taxa Legal | Juros conforme a taxa legal |
| IPCA e SELIC | Regimes de atualização disponíveis no motor |

As séries, respectivas versões e fontes ficam em `backend/app/data/`. Atualizações devem passar pelos scripts em `backend/scripts/` e por revisão dos testes.

## Tecnologia

- Frontend: React, TypeScript, Vite e Tailwind CSS
- Backend: Python e FastAPI
- Dados locais: SQLite (estrutura preparada para PostgreSQL)
- Relatórios: ReportLab (PDF) e openpyxl (XLSX)

## Instalação local

### Pré-requisitos

- Linux (o lançador e o atalho fornecidos foram preparados para Linux)
- Python 3.11 ou superior
- Node.js 20 ou superior, com npm
- `curl`, para a checagem de inicialização do lançador

### 1. Obtenha o código

```bash
git clone https://github.com/Vangl-dev/very-easy-calc.git
cd very-easy-calc
```

### 2. Instale as dependências

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm ci
```

### 3. Configure o ambiente

O projeto já inclui uma configuração de desenvolvimento em `frontend/.env`. Para personalizar o backend, copie o exemplo:

```bash
cd ..
cp .env.example .env
```

Não versione o arquivo `.env` criado localmente.

### 4. Inicie o aplicativo

Na raiz do repositório:

```bash
chmod +x run.sh
./run.sh
```

Abra [http://localhost:5173](http://localhost:5173). O banco SQLite é criado/inicializado na primeira execução.

Para encerrar, use `Ctrl+C` no terminal que executa o lançador.

## Testes e verificação

```bash
# Backend
cd backend
.venv/bin/python -m pytest

# Frontend
cd frontend
npm test
npm run build
```

## Uso self-hosted

O aplicativo foi desenhado para também poder ser hospedado pela própria equipe, mantendo banco e dados de cálculo sob seu controle. A instalação acima serve para uso local e desenvolvimento; a publicação em servidor ainda não é um instalador de produção pronto.

Para uma implantação self-hosted, planeje ao menos:

1. um processo ASGI permanente para o FastAPI (por exemplo, Uvicorn sob systemd);
2. o frontend compilado com `npm run build` e servido por Nginx ou Caddy;
3. proxy reverso de `/api` para o backend;
4. HTTPS, backups do banco e atualização controlada das séries de índices;
5. PostgreSQL em vez de SQLite quando houver acesso simultâneo ou necessidade de operação compartilhada.

Docker/Compose, instalador e guia de produção são a próxima etapa natural para transformar o MVP em uma distribuição self-hosted simples. Eles não fazem parte deste repositório ainda — a documentação evita anunciar uma entrega que não existe.

## Estrutura do projeto

```text
backend/       API FastAPI, motor, dados de índices e exportação
frontend/      interface React
assets/        identidade visual do aplicativo
docs/          notas técnicas e checkpoints de desenvolvimento
run.sh         lançador local para Linux
```

## Limites e responsabilidade

O Very Easy Calc executa os critérios informados; não substitui análise jurídica, conferência contábil ou validação do profissional responsável. Índices e regras precisam ser revisados conforme o caso concreto e a data-base escolhida.

## Licença

O repositório está público para transparência e acompanhamento do desenvolvimento. A definição de uma licença de uso e distribuição ainda está pendente.
