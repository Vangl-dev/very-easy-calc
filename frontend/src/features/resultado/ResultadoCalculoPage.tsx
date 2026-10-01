import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";
import { TabelaAuditoria } from "./TabelaAuditoria";
import { api, formatarDataHora, mensagemErroAmigavel, rotuloTipoCalculo } from "../../lib/api";
import type { CalculoCriado } from "../../types/api";

function monetario(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function ResultadoCalculoPage() {
  const { codigo } = useParams<{ codigo: string }>();
  const [calculo, setCalculo] = useState<CalculoCriado | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!codigo) return;
    let ativo = true;
    setCarregando(true);
    setErro(null);
    api
      .obterCalculo(codigo)
      .then((dados) => {
        if (ativo) setCalculo(dados);
      })
      .catch((e) => {
        if (ativo) setErro(mensagemErroAmigavel(e));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [codigo]);

  if (carregando) {
    return <p className="text-sm text-ink-500">Carregando memória de cálculo…</p>;
  }

  if (erro || !calculo) {
    return (
      <div className="space-y-4">
        <Message tom="danger" title="Cálculo não encontrado">
          {erro ?? `Não foi possível carregar o cálculo ${codigo}.`}
        </Message>
        <Link to="/novo-calculo?tipo=parcelas">
          <Button variant="outline">Voltar ao lançamento</Button>
        </Link>
      </div>
    );
  }

  const resumo = calculo.resumo;
  const urlPdf = `${api.baseUrl}/api/calculos/${calculo.codigo}/pdf`;
  const urlXlsx = `${api.baseUrl}/api/calculos/${calculo.codigo}/xlsx`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Resultado · {rotuloTipoCalculo(calculo.tipo)}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">
            {calculo.titulo || calculo.codigo}
          </h1>
          <p className="mt-1 font-mono text-sm text-brand-700">{calculo.codigo}</p>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Processo: {calculo.processo || "—"} · Parte: {calculo.parte || "—"} ·
            Gerado em {formatarDataHora(calculo.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tooltip text="PDF e XLSX são gerados no backend a partir da memória de cálculo — sem recálculo no React." />
          <a href={urlPdf} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="sm">
              Baixar PDF
            </Button>
          </a>
          <a href={urlXlsx} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="sm">
              Salvar XLSX
            </Button>
          </a>
          <Link to={`/novo-calculo?tipo=parcelas&editar=${encodeURIComponent(calculo.codigo)}`}>
            <Button variant="outline" size="sm">
              Voltar / Editar cálculo
            </Button>
          </Link>
        </div>
      </div>

      <Card title="Resumo" description="Valores retornados pelo backend">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
            <dt className="text-xs uppercase text-ink-500">Parcelas</dt>
            <dd className="mt-1 font-mono text-sm font-semibold text-ink-900">
              {resumo?.qtd_parcelas ?? "—"}
            </dd>
          </div>
          <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
            <dt className="text-xs uppercase text-ink-500">Principal</dt>
            <dd className="mt-1 font-mono text-sm font-semibold text-ink-900">
              {monetario(resumo?.principal)}
            </dd>
          </div>
          <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
            <dt className="text-xs uppercase text-ink-500">Total</dt>
            <dd className="mt-1 font-mono text-sm font-semibold text-brand-800">
              {monetario(resumo?.total)}
            </dd>
          </div>
          <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
            <dt className="text-xs uppercase text-ink-500">Saldo</dt>
            <dd className="mt-1 font-mono text-sm font-semibold text-brand-800">
              {monetario(resumo?.saldo)}
            </dd>
          </div>
        </dl>
      </Card>

      <Card padded={false}>
        <div className="p-4">
          <TabelaAuditoria calculo={calculo} />
        </div>
      </Card>
    </div>
  );
}
