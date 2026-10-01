import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatarDataHora, rotuloTipoCalculo } from "../lib/api";
import type { CalculoResumo, HealthResponse } from "../types/api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Message } from "../components/ui/Message";
import { Table, type Columna } from "../components/ui/Table";
import { Tooltip } from "../components/ui/Tooltip";

const capacidades = [
  {
    id: "civel" as const,
    titulo: "Cálculo Cível",
    descricao:
      "Parcelas com correção monetária, juros, multa, honorários e saldo.",
    detalhe:
      "Configuração por parcela. O motor do backend aplica apenas o que for informado.",
    rota: "/novo-calculo?tipo=parcelas",
    destaque: "Principal",
  },
  {
    id: "alimentos" as const,
    titulo: "Alimentos",
    descricao:
      "Percentual do salário mínimo ou valor fixo, competência a competência.",
    detalhe:
      "Cada competência usa o salário mínimo vigente naquele período — sem retroagir o valor atual.",
    rota: "/novo-calculo?tipo=alimentos",
    destaque: "MVP",
  },
  {
    id: "atualizacao" as const,
    titulo: "Atualização monetária",
    descricao:
      "Valor-base com data-base e data final escolhida para atualização.",
    detalhe:
      "Preserva valor original, índices e versões das bases na memória de cálculo.",
    rota: "/novo-calculo?tipo=atualizacao",
    destaque: "Datas futuras",
  },
  {
    id: "memoria" as const,
    titulo: "Memória de cálculo",
    descricao:
      "Fonte única para auditoria: critérios, parcelas, bases e versões.",
    detalhe:
      "Estrutura memoria-calculo/1.1 — o relatório nunca recalcula valores.",
    rota: "/meus-calculos",
    destaque: "Auditável",
  },
  {
    id: "relatorios" as const,
    titulo: "PDF / XLSX",
    descricao: "Exportação a partir da memória já calculada.",
    detalhe:
      "ReportLab e openpyxl no backend. Valores monetários preservados com precisão.",
    rota: "/meus-calculos",
    destaque: "Exportação",
  },
];

export function DashboardPage() {
  const [saude, setSaude] = useState<HealthResponse | null>(null);
  const [calculos, setCalculos] = useState<CalculoResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    async function carregar() {
      setCarregando(true);
      setErro(null);
      try {
        const [health, lista] = await Promise.all([
          api.health(),
          api.listarCalculos(),
        ]);
        if (!ativo) return;
        setSaude(health);
        setCalculos(lista);
      } catch (e) {
        if (!ativo) return;
        setErro(
          e instanceof Error
            ? e.message
            : "Não foi possível consultar a API do Very Easy Calc.",
        );
      } finally {
        if (ativo) setCarregando(false);
      }
    }
    void carregar();
    return () => {
      ativo = false;
    };
  }, []);

  const recentes = calculos.slice(0, 8);

  const colunas: Columna<CalculoResumo>[] = [
    {
      key: "codigo",
      header: "Código",
      render: (linha) => (
        <span className="font-mono text-xs font-semibold text-brand-700">
          {linha.codigo}
        </span>
      ),
    },
    {
      key: "tipo",
      header: "Tipo",
      render: (linha) => (
        <span className="inline-flex rounded-full bg-ink-100 px-2.5 py-0.5 text-xs font-medium text-ink-700">
          {rotuloTipoCalculo(linha.tipo)}
        </span>
      ),
    },
    {
      key: "titulo",
      header: "Título",
      render: (linha) => linha.titulo || "—",
    },
    {
      key: "processo",
      header: "Processo",
      render: (linha) => linha.processo || "—",
    },
    {
      key: "created_at",
      header: "Criado em",
      render: (linha) => (
        <span className="text-ink-600">{formatarDataHora(linha.created_at)}</span>
      ),
    },
    {
      key: "acoes",
      header: "Ações",
      render: (linha) => (
        <Link
          to={`/meus-calculos?codigo=${encodeURIComponent(linha.codigo)}`}
          className="text-sm font-medium text-brand-700 hover:text-brand-800 hover:underline"
        >
          Ver detalhes
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Painel
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950 sm:text-3xl">
            Dashboard do Very Easy Calc
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-600">
            Estrutura visual para iniciar cálculos cíveis, alimentos e atualização
            monetária. Os valores vêm sempre do backend — sem regras matemáticas
            no React.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/novo-calculo">
            <Button size="lg">Novo cálculo</Button>
          </Link>
          <Link to="/meus-calculos">
            <Button variant="outline" size="lg">
              Meus cálculos
            </Button>
          </Link>
          <Tooltip text="Nesta fase o formulário completo ainda será implementado. A área 'Novo cálculo' já está preparada na navegação." />
        </div>
      </section>

      {erro ? (
        <Message tom="danger" title="API indisponível">
          {erro}
          <p className="mt-1 text-xs">
            Suba o backend em <code className="font-mono">localhost:8000</code> e
            confira <code className="font-mono">VITE_API_BASE_URL</code>.
          </p>
        </Message>
      ) : null}

      <section aria-labelledby="capacidades-heading">
        <div className="mb-4 flex items-center gap-2">
          <h2 id="capacidades-heading" className="text-lg font-semibold text-ink-900">
            O que o sistema oferece
          </h2>
          <Tooltip text="Cada capacidade é resolvida no backend. O frontend organiza a experiência e exibe a memória de cálculo." />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {capacidades.map((item) => (
            <Card
              key={item.id}
              title={item.titulo}
              description={item.descricao}
              action={
                <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
                  {item.destaque}
                </span>
              }
            >
              <p className="text-sm leading-relaxed text-ink-600">{item.detalhe}</p>
              <div className="mt-4">
                <Link to={item.rota}>
                  <Button variant="secondary" size="sm">
                    Abrir
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Atalhos"
          description="Navegação preparada para as próximas etapas do formulário."
        >
          <ul className="space-y-3 text-sm text-ink-700">
            <li className="flex items-start justify-between gap-3 rounded-xl border border-ink-100 bg-ink-50/60 px-3 py-2.5">
              <span>
                <strong className="font-semibold text-ink-900">Novo cálculo</strong>
                <span className="block text-xs text-ink-500">
                  Formulário completo será implementado em etapa seguinte
                </span>
              </span>
              <Link to="/novo-calculo" className="shrink-0 text-brand-700 hover:underline">
                Ir
              </Link>
            </li>
            <li className="flex items-start justify-between gap-3 rounded-xl border border-ink-100 bg-ink-50/60 px-3 py-2.5">
              <span>
                <strong className="font-semibold text-ink-900">Meus cálculos</strong>
                <span className="block text-xs text-ink-500">
                  Histórico, memória e links de PDF/XLSX
                </span>
              </span>
              <Link to="/meus-calculos" className="shrink-0 text-brand-700 hover:underline">
                Ir
              </Link>
            </li>
            <li className="flex items-start justify-between gap-3 rounded-xl border border-ink-100 bg-ink-50/60 px-3 py-2.5">
              <span>
                <strong className="font-semibold text-ink-900">Bases / Indexadores</strong>
                <span className="block text-xs text-ink-500">
                  Versões oficiais e cobertura efetiva
                </span>
              </span>
              <Link to="/bases" className="shrink-0 text-brand-700 hover:underline">
                Ir
              </Link>
            </li>
          </ul>
        </Card>

        <Card
          title="Status da aplicação"
          description="Leitura direta da API — sem cache matemático no cliente."
        >
          {carregando ? (
            <p className="text-sm text-ink-500">Carregando status…</p>
          ) : saude ? (
            <dl className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
                <dt className="text-xs uppercase tracking-wide text-ink-500">
                  Status
                </dt>
                <dd className="mt-1 font-medium text-emerald-700">{saude.status}</dd>
              </div>
              <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
                <dt className="text-xs uppercase tracking-wide text-ink-500">
                  Aplicativo
                </dt>
                <dd className="mt-1 font-medium text-ink-900">{saude.app}</dd>
              </div>
              <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
                <dt className="text-xs uppercase tracking-wide text-ink-500">
                  Versão
                </dt>
                <dd className="mt-1 font-medium text-ink-900">{saude.version}</dd>
              </div>
              <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
                <dt className="text-xs uppercase tracking-wide text-ink-500">
                  Cálculos listados
                </dt>
                <dd className="mt-1 font-medium text-ink-900">{calculos.length}</dd>
              </div>
            </dl>
          ) : (
            <Message tom="warning">Sem resposta do backend.</Message>
          )}
        </Card>
      </section>

      <section aria-labelledby="recentes-heading">
        <Card
          title="Cálculos recentes"
          description="Últimos registros persistidos no SQLite via API."
          action={
            <Link to="/meus-calculos">
              <Button variant="ghost" size="sm">
                Ver todos
              </Button>
            </Link>
          }
          padded={false}
        >
          <div className="p-5">
            <Table
              colunas={colunas}
              linhas={recentes}
              chaveLinha={(linha) => linha.codigo}
              caption="Cálculos recentes"
              vazio={
                carregando
                  ? "Carregando cálculos…"
                  : "Nenhum cálculo ainda. Use 'Novo cálculo' para começar."
              }
            />
          </div>
        </Card>
      </section>
    </div>
  );
}
