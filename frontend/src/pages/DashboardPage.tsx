import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatarDataHora, rotuloTipoCalculo } from "../lib/api";
import { excluirRascunho, listarRascunhos, type RascunhoCivel } from "../lib/rascunhos";
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
  const [selecionados, setSelecionados] = useState<string[]>([]);
  const [erroAcao, setErroAcao] = useState<string | null>(null);
  const [rascunhos, setRascunhos] = useState<RascunhoCivel[]>([]);

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      const [health, lista] = await Promise.all([
        api.health(),
        api.listarCalculos(),
      ]);
      setSaude(health);
      setCalculos(lista);
    } catch (e) {
      setErro(
        e instanceof Error
          ? e.message
          : "Não foi possível consultar a API do Very Easy Calc.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
    setRascunhos(listarRascunhos());
  }, []);

  function alternarSelecao(codigo: string) {
    setSelecionados((atual) =>
      atual.includes(codigo)
        ? atual.filter((item) => item !== codigo)
        : [...atual, codigo],
    );
  }

  function alternarTodos() {
    setSelecionados((atual) =>
      atual.length === recentes.length ? [] : recentes.map((c) => c.codigo),
    );
  }

  async function excluirSelecionados() {
    if (selecionados.length === 0) return;
    setErroAcao(null);
    try {
      for (const codigo of selecionados) {
        await api.excluirCalculo(codigo);
      }
      setSelecionados([]);
      await carregar();
    } catch (e) {
      setErroAcao(
        e instanceof Error ? e.message : "Não foi possível excluir os cálculos.",
      );
    }
  }

  async function limparTudo() {
    const confirmado = window.confirm(
      "Excluir todos os cálculos salvos? Esta ação não remove os rascunhos.",
    );
    if (!confirmado) return;
    setErroAcao(null);
    try {
      await api.limparCalculos();
      setSelecionados([]);
      await carregar();
    } catch (e) {
      setErroAcao(
        e instanceof Error ? e.message : "Não foi possível limpar os cálculos.",
      );
    }
  }

  function removerRascunho(id: string) {
    excluirRascunho(id);
    setRascunhos(listarRascunhos());
  }

  const recentes = calculos.slice(0, 8);

  const colunas: Columna<CalculoResumo>[] = [
    {
      key: "selecionar",
      header: "Selecionar",
      render: (linha) => (
        <input
          type="checkbox"
          checked={selecionados.includes(linha.codigo)}
          onChange={() => alternarSelecao(linha.codigo)}
          aria-label={`Selecionar cálculo ${linha.codigo}`}
          className="h-4 w-4 accent-brand-700"
        />
      ),
    },
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
            Suba o backend em <code className="font-mono">localhost:8001</code> e
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

      {erroAcao ? (
        <Message tom="danger" title="Falha na ação">
          {erroAcao}
        </Message>
      ) : null}

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
          <div className="space-y-4 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={recentes.length > 0 && selecionados.length === recentes.length}
                  onChange={alternarTodos}
                  aria-label="Selecionar todos os cálculos"
                  className="h-4 w-4 accent-brand-700"
                />
                Selecionar todos
              </label>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void excluirSelecionados()}
                disabled={selecionados.length === 0}
              >
                Excluir selecionados
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void limparTudo()}
                disabled={calculos.length === 0}
              >
                Limpar tudo
              </Button>
            </div>
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

      <section aria-label="Rascunhos">
        <Card
          title="Rascunhos"
          description="Cálculos incompletos guardados neste navegador — não são cálculos concluídos."
        >
          {rascunhos.length === 0 ? (
            <p className="text-sm text-ink-500">
              Nenhum rascunho salvo. Use “Salvar rascunho” no formulário para
              continuar depois.
            </p>
          ) : (
            <ul className="divide-y divide-ink-100">
              {rascunhos.map((rascunho) => (
                <li
                  key={rascunho.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-ink-900">
                      {rascunho.titulo}
                    </p>
                    <p className="text-xs text-ink-500">
                      Atualizado em {formatarDataHora(rascunho.atualizadoEm)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/novo-calculo?tipo=parcelas&rascunho=${encodeURIComponent(rascunho.id)}`}
                    >
                      <Button variant="secondary" size="sm">
                        Continuar
                      </Button>
                    </Link>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removerRascunho(rascunho.id)}
                      aria-label={`Excluir rascunho ${rascunho.titulo}`}
                    >
                      Excluir
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  );
}
