import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, formatarDataHora, rotuloTipoCalculo } from "../lib/api";
import type { CalculoResumo } from "../types/api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Message } from "../components/ui/Message";
import { Table, type Columna } from "../components/ui/Table";
import { Tooltip } from "../components/ui/Tooltip";

export function MeusCalculosPage() {
  const [params, setParams] = useSearchParams();
  const codigoSelecionado = params.get("codigo");
  const [calculos, setCalculos] = useState<CalculoResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    async function carregar() {
      setCarregando(true);
      setErro(null);
      try {
        const lista = await api.listarCalculos();
        if (ativo) setCalculos(lista);
      } catch (e) {
        if (ativo) {
          setErro(e instanceof Error ? e.message : "Falha ao listar cálculos.");
        }
      } finally {
        if (ativo) setCarregando(false);
      }
    }
    void carregar();
    return () => {
      ativo = false;
    };
  }, []);

  const selecionado = useMemo(
    () => calculos.find((c) => c.codigo === codigoSelecionado) ?? null,
    [calculos, codigoSelecionado],
  );

  const colunas: Columna<CalculoResumo>[] = [
    {
      key: "codigo",
      header: "Código",
      render: (linha) => (
        <button
          type="button"
          onClick={() => setParams({ codigo: linha.codigo })}
          className="font-mono text-xs font-semibold text-brand-700 hover:underline"
        >
          {linha.codigo}
        </button>
      ),
    },
    {
      key: "tipo",
      header: "Tipo",
      render: (linha) => rotuloTipoCalculo(linha.tipo),
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
      render: (linha) => formatarDataHora(linha.created_at),
    },
    {
      key: "export",
      header: "Exportar",
      render: (linha) => (
        <span className="flex flex-wrap gap-2">
          <a
            href={`${api.baseUrl}/api/calculos/${linha.codigo}/pdf`}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-brand-700 hover:underline"
          >
            PDF
          </a>
          <a
            href={`${api.baseUrl}/api/calculos/${linha.codigo}/xlsx`}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-brand-700 hover:underline"
          >
            XLSX
          </a>
          <a
            href={`${api.baseUrl}/api/calculos/${linha.codigo}/memoria`}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-brand-700 hover:underline"
          >
            Memória
          </a>
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Histórico
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">Meus cálculos</h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Lista vinda de <code className="font-mono">GET /api/calculos</code>.
            Exportações apontam para os endpoints validados de PDF, XLSX e memória.
          </p>
        </div>
        <Tooltip text="Os arquivos são gerados no backend a partir de memoria_json — o React apenas baixa o resultado." />
      </div>

      {erro ? <Message tom="danger">{erro}</Message> : null}

      <Card
        title="Cálculos"
        description="Selecione um código para destacar o registro."
        padded={false}
      >
        <div className="p-5">
          <Table
            colunas={colunas}
            linhas={calculos}
            chaveLinha={(linha) => linha.codigo}
            caption="Meus cálculos"
            vazio={carregando ? "Carregando…" : "Nenhum cálculo registrado."}
          />
        </div>
      </Card>

      {selecionado ? (
        <Card title="Detalhe rápido" description={selecionado.codigo}>
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-ink-500">Tipo</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {rotuloTipoCalculo(selecionado.tipo)}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Título</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {selecionado.titulo || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Processo</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {selecionado.processo || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Versão do app</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {selecionado.app_version}
              </dd>
            </div>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={`${api.baseUrl}/api/calculos/${selecionado.codigo}/pdf`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="secondary" size="sm">
                Baixar PDF
              </Button>
            </a>
            <a
              href={`${api.baseUrl}/api/calculos/${selecionado.codigo}/xlsx`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="secondary" size="sm">
                Baixar XLSX
              </Button>
            </a>
            <a
              href={`${api.baseUrl}/api/calculos/${selecionado.codigo}/memoria`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline" size="sm">
                Abrir memória
              </Button>
            </a>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
