import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Message } from "../../components/ui/Message";
import { TabelaAuditoria } from "./TabelaAuditoria";
import { api, formatarDataHora, mensagemErroAmigavel, rotuloTipoCalculo } from "../../lib/api";
import { formatarDataBR } from "../civel/estadoVerba";
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

function percentualTexto(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return `${(n * 100).toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}%`;
}

type VerbaMemoria = {
  id?: string;
  nome?: string;
  tipo?: string;
  valor?: string;
  base_verba_id?: string | null;
  percentual?: string | null;
  entra_no_total?: boolean | null;
  data_base?: string;
  inicio_correcao?: string | null;
  inicio_juros?: string | null;
};

type ParcelaResumo = {
  verba?: { id?: string; nome?: string };
  principal?: string;
  total?: string;
};

function resumoVisualVerba(
  verba: VerbaMemoria,
  mapaPorId: Map<string, VerbaMemoria>,
): string {
  if (verba.tipo === "percentual") {
    const base = verba.base_verba_id
      ? mapaPorId.get(verba.base_verba_id)?.nome || verba.base_verba_id
      : "verba-base";
    const pct = percentualTexto(verba.percentual) || "?%";
    return `${pct} de ${base}`;
  }
  return "Valor informado";
}

const ROTULO_TAXA_LEGAL = "Taxa Legal (BCB SGS 29543)";

type CriteriosJuros = { aplicado?: boolean; indexador?: string };
type CriteriosCorrecao = {
  aplicado?: boolean;
  indexador?: string;
  segmentos?: Array<{ indexador?: string }>;
};

/** Critérios efetivamente aplicados — SELIC nunca é chamada de Taxa Legal. */
function criteriosAplicados(calculo: CalculoCriado): string[] {
  const parcelas = (calculo.parcelas ?? []) as Array<Record<string, unknown>>;
  const linhas: string[] = [];

  const juros = (indice: string) =>
    parcelas.some((p) => {
      const info = p.juros as CriteriosJuros | undefined;
      return Boolean(info?.aplicado) && info?.indexador === indice;
    });
  const correcaoSelic = parcelas.some((p) => {
    const info = p.correcao as CriteriosCorrecao | undefined;
    if (!info?.aplicado) return false;
    if (info.indexador === "selic") return true;
    return (info.segmentos ?? []).some((s) => s.indexador === "selic");
  });

  if (juros("taxa_legal")) {
    const base = (calculo.bases ?? []).find((b) => b.key === "taxa_legal");
    const nome =
      typeof base?.nome === "string" && base.nome ? base.nome : ROTULO_TAXA_LEGAL;
    linhas.push(`Juros: ${nome}`);
  }
  if (juros("selic")) linhas.push("Juros: SELIC");
  if (correcaoSelic) linhas.push("Correção: SELIC");
  return linhas;
}

function criteriosNaoAplicados(calculo: CalculoCriado): string[] {
  const parcelas = (calculo.parcelas ?? []) as Array<Record<string, unknown>>;
  const avisos = new Set<string>();
  for (const [indice, parcela] of parcelas.entries()) {
    const verba = parcela.verba as { nome?: string } | undefined;
    const nome = verba?.nome || `Verba ${indice + 1}`;
    const juros = parcela.juros as { aplicado?: boolean } | undefined;
    const correcao = parcela.correcao as { aplicado?: boolean } | undefined;
    if (juros?.aplicado === false) avisos.add(`${nome}: juros não aplicados`);
    if (correcao?.aplicado === false) avisos.add(`${nome}: correção monetária não aplicada`);
  }
  return [...avisos];
}

function totalPorVerba(
  calculo: CalculoCriado,
  verbaId?: string,
): { de: string; ate: string } | null {  const parcelas = (calculo.parcelas ?? []) as ParcelaResumo[];
  const alvo = parcelas.filter(
    (p) => !verbaId || p.verba?.id === verbaId || !p.verba?.id,
  );
  if (alvo.length === 0) return null;
  const de = alvo[0]?.principal ?? "0";
  const ate = alvo[0]?.total ?? "0";
  if (alvo.length === 1) return { de, ate };
  const somaDe = alvo.reduce((acc, p) => acc + Number(p.principal ?? 0), 0);
  const somaAte = alvo.reduce((acc, p) => acc + Number(p.total ?? 0), 0);
  return {
    de: somaDe.toFixed(2),
    ate: somaAte.toFixed(2),
  };
}

export function ResultadoCalculoPage() {
  const { codigo } = useParams<{ codigo: string }>();
  const [calculo, setCalculo] = useState<CalculoCriado | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [memoriaAberta, setMemoriaAberta] = useState(false);

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
    return (
      <p className="mx-auto max-w-page py-10 text-sm text-ink-500">
        Carregando memória de cálculo…
      </p>
    );
  }

  if (erro || !calculo) {
    return (
      <div className="mx-auto max-w-page space-y-4 py-8">
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
  const ehAlimentos = calculo.tipo === "alimentos";
  const memoria = (calculo.memoria ?? {}) as {
    verbas?: VerbaMemoria[];
  };
  const verbasMemoria = memoria.verbas ?? [];
  const mapaVerbas = new Map<string, VerbaMemoria>();
  for (const v of verbasMemoria) {
    if (v.id) mapaVerbas.set(v.id, v);
  }

  const urlPdf = `${api.baseUrl}/api/calculos/${calculo.codigo}/pdf`;
  const urlXlsx = `${api.baseUrl}/api/calculos/${calculo.codigo}/xlsx`;
  const editarUrl = `/novo-calculo?tipo=parcelas&revisar=${encodeURIComponent(calculo.codigo)}`;
  const urlLancamento = ehAlimentos
    ? "/novo-calculo?tipo=alimentos"
    : editarUrl;

  const tituloTipo = rotuloTipoCalculo(calculo.tipo);
  const criterios = criteriosAplicados(calculo);
  const criteriosAusentes = criteriosNaoAplicados(calculo);

  const itensResumo = [
    { rotulo: "Principal", valor: resumo?.principal, destaque: false, sempre: true },
    { rotulo: "Correção monetária", valor: resumo?.correcao, destaque: false, sempre: false },
    { rotulo: "Juros", valor: resumo?.juros, destaque: false, sempre: false },
    { rotulo: "Multa", valor: resumo?.multa, destaque: false, sempre: false },
    { rotulo: "Honorários", valor: resumo?.honorarios, destaque: false, sempre: false },
    { rotulo: "Total atualizado", valor: resumo?.total, destaque: true, sempre: true },
    {
      rotulo: "Pagamentos e abatimentos",
      valor: resumo?.pagamentos,
      destaque: false,
      sempre: false,
    },
    { rotulo: "Saldo final", valor: resumo?.saldo, destaque: true, sempre: true },
  ].filter((item) => item.sempre || Number(item.valor) > 0);

  return (
    <div className="mx-auto max-w-page space-y-8">
      <header className="border-b border-line pb-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="section-kicker">{tituloTipo}</p>
            <h1 className="mt-2 text-[26px] leading-tight text-ink-950">
              {calculo.titulo || calculo.codigo}
            </h1>
            <p className="mt-1 font-mono text-[13px] text-brand-700">
              {calculo.codigo}
            </p>
            <p className="mt-3 max-w-[60ch] text-[13px] leading-relaxed text-ink-500">
              Processo: {calculo.processo || "—"} · Parte: {calculo.parte || "—"}
              <br />
              Gerado em {formatarDataHora(calculo.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
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
            {calculo.tipo === "parcelas" ? (
              <Link to={editarUrl}>
                <Button variant="outline" size="sm">Criar revisão</Button>
              </Link>
            ) : null}
            <Link to={urlLancamento}>
              <Button variant="outline" size="sm">
                Voltar ao cálculo
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section aria-labelledby="sec-resumo">
        <p className="section-kicker">Memória de cálculo</p>
        <h2 id="sec-resumo" className="section-title mt-1">
          Resumo
        </h2>
        <dl className="mt-4 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {itensResumo.map((item) => (
            <div
              key={item.rotulo}
              className={`px-4 py-3.5 ${
                item.destaque ? "bg-brand-50" : "bg-panel"
              }`}
            >
              <dt className="label-legal">{item.rotulo}</dt>
              <dd
                className={`mt-1.5 font-mono text-[18px] font-semibold tabular-nums ${
                  item.destaque ? "text-brand-700" : "text-ink-900"
                }`}
              >
                {monetario(item.valor)}
              </dd>
            </div>
          ))}
        </dl>
        {criterios.map((texto) => (
          <p key={texto} className="mt-3 text-[13px] text-ink-600">
            {texto}
          </p>
        ))}
        <p className="mt-3 text-[13px] text-ink-500">
          Competências/parcelas:{" "}
          <span className="font-mono text-ink-800">
            {resumo?.qtd_parcelas ?? "—"}
          </span>
        </p>
        {criteriosAusentes.length > 0 ? (
          <div className="mt-4">
            <Message tom="warning" title="Confira antes de exportar">
              {criteriosAusentes.join("; ")}. Estes critérios não entraram no cálculo.
            </Message>
          </div>
        ) : null}
      </section>

      {verbasMemoria.length > 0 ? (
        <section aria-labelledby="sec-verbas-resumo">
          <h2 id="sec-verbas-resumo" className="section-title">
            Verbas
          </h2>
          <ul className="mt-4 space-y-3">
            {verbasMemoria.map((verba, indice) => {
              const totais = totalPorVerba(calculo, verba.id);
              const formula = resumoVisualVerba(verba, mapaVerbas);
              return (
                <li key={verba.id ?? indice} className="sheet-panel px-5 py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <p className="text-[15px] font-semibold text-ink-900">
                          {verba.nome || `Verba ${indice + 1}`}
                        </p>
                        {verba.entra_no_total === false ? (
                          <span className="rounded border border-line bg-ink-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-legal text-ink-600">
                            Fora do total
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-[13px] text-ink-600">{formula}</p>
                    </div>
                    <p className="font-mono text-[15px] tabular-nums text-ink-900">
                      {totais ? (
                        <>
                          {monetario(totais.de)}
                          <span className="mx-2 text-ink-400">→</span>
                          <span className="font-semibold text-brand-700">
                            {monetario(totais.ate)}
                          </span>
                        </>
                      ) : (
                        "—"
                      )}
                    </p>
                  </div>
                  <p className="mt-2 text-[12px] text-ink-500">
                    Base: {verba.data_base ? formatarDataBR(verba.data_base) : "—"}
                    {" · "}Correção desde {verba.inicio_correcao || "—"}
                    {" · "}Juros desde{" "}
                    {verba.inicio_juros ? formatarDataBR(verba.inicio_juros) : "—"}
                  </p>
                  {verba.tipo === "percentual" && verba.base_verba_id ? (
                    <p className="mt-2 border-t border-line pt-2 text-[13px] text-ink-700">
                      Cálculo:{" "}
                      <span className="font-mono">
                        {monetario(
                          mapaVerbas.get(verba.base_verba_id)?.valor ??
                            totais?.de ??
                            "0",
                        )}
                        {" × "}
                        {percentualTexto(verba.percentual)}
                        {" = "}
                        <span className="font-semibold text-brand-700">
                          {monetario(totais?.ate ?? verba.valor)}
                        </span>
                      </span>
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="sec-tabela">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="section-kicker">Detalhamento</p>
            <h2 id="sec-tabela" className="section-title mt-1">
              {ehAlimentos ? "Planilha por competência" : "Parcelas"}
            </h2>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setMemoriaAberta((v) => !v)}
            aria-expanded={memoriaAberta}
          >
            {memoriaAberta ? "Ocultar memória técnica" : "Memória técnica"}
          </Button>
        </div>

        <div className="mt-4">
          <TabelaAuditoria calculo={calculo} compacto={!memoriaAberta} />
        </div>
      </section>
    </div>
  );
}
