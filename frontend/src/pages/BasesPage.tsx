import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { IndexerMeta } from "../types/api";
import { Card } from "../components/ui/Card";
import { Message } from "../components/ui/Message";
import { Table, type Columna } from "../components/ui/Table";
import { Tooltip } from "../components/ui/Tooltip";

export function BasesPage() {
  const [indexers, setIndexers] = useState<IndexerMeta[]>([]);
  const [appVersion, setAppVersion] = useState<string>("");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    async function carregar() {
      setCarregando(true);
      setErro(null);
      try {
        const dados = await api.listarIndexadores();
        if (!ativo) return;
        setIndexers(dados.indexers);
        setAppVersion(dados.app_version);
      } catch (e) {
        if (ativo) {
          setErro(e instanceof Error ? e.message : "Falha ao carregar indexadores.");
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

  const colunas: Columna<IndexerMeta>[] = [
    {
      key: "key",
      header: "Key",
      render: (linha) => (
        <span className="font-mono text-xs font-semibold text-ink-800">{linha.key}</span>
      ),
    },
    {
      key: "name",
      header: "Nome",
      render: (linha) => linha.name,
    },
    {
      key: "kind",
      header: "Tipo",
      render: (linha) => (
        <span className="rounded-full bg-ink-100 px-2 py-0.5 text-xs text-ink-700">
          {linha.kind}
        </span>
      ),
    },
    {
      key: "version",
      header: "Versão",
      render: (linha) => linha.version,
    },
    {
      key: "cobertura",
      header: "Cobertura",
      render: (linha) =>
        `${linha.cobertura.inicio} → ${linha.cobertura.fim} (${linha.cobertura.total})`,
    },
    {
      key: "fonte",
      header: "Fonte",
      render: (linha) => linha.source || "—",
    },
    {
      key: "registrada",
      header: "Seed",
      render: (linha) =>
        linha.registrada ? (
          <span className="text-xs font-medium text-emerald-700">registrada</span>
        ) : (
          <span className="text-xs text-ink-500">—</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Rastreabilidade
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">
            Bases / Indexadores
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Versões oficiais e cobertura. Cadastros manuais (overrides) e detalhe de
            cobertura efetiva serão ligados nesta tela na próxima etapa.
            {appVersion ? ` App ${appVersion}.` : ""}
          </p>
        </div>
        <Tooltip text="GET /api/indexers lista as bases versionadas. GET /api/indexers/{key}/cobertura mostra oficial + manual." />
      </div>

      {erro ? <Message tom="danger">{erro}</Message> : null}

      <Card title="Indexadores" description="Fonte única: backend FastAPI." padded={false}>
        <div className="p-5">
          <Table
            colunas={colunas}
            linhas={indexers}
            chaveLinha={(linha) => linha.key}
            caption="Indexadores"
            vazio={carregando ? "Carregando…" : "Nenhum indexador."}
          />
        </div>
      </Card>
    </div>
  );
}
