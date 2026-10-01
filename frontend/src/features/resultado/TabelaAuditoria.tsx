import { Fragment, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";
import { formatarDataBR } from "../civel/estadoVerba";
import type { CalculoCriado } from "../../types/api";

type LinhaAuditoria = {
  numero: number;
  verba: string;
  competencia: string;
  competenciaRotulo: string;
  vencimento: string;
  valorOriginal: string;
  inicioCorrecao: string;
  correcao: string;
  inicioJuros: string;
  juros: string;
  multa: string;
  honorarios: string;
  pagamento: string;
  saldo: string;
  total: string;
  chaveVerba: string;
};

function monetario(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const texto = String(valor);
  const n = Number(texto);
  if (Number.isNaN(n)) return texto;
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function extrairLinhas(calculo: CalculoCriado): LinhaAuditoria[] {
  const parcelas = (calculo.parcelas ?? []) as Array<Record<string, unknown>>;
  const memoria = (calculo.memoria ?? {}) as {
    verbas?: Array<{ id?: string; nome?: string }>;
  };
  const mapaVerba = new Map<string, string>();
  for (const v of memoria.verbas ?? []) {
    if (v.id && v.nome) mapaVerba.set(v.id, v.nome);
  }

  return parcelas.map((p, indice) => {
    const verba = (p.verba ?? {}) as { id?: string; nome?: string };
    const correcao = (p.correcao ?? {}) as {
      correcao?: string;
      termo_inicial?: string;
    };
    const juros = (p.juros ?? {}) as { juros?: string };
    const multa = (p.multa ?? {}) as { valor?: string };
    const honorarios = (p.honorarios ?? {}) as { valor?: string };
    const chaveVerba = verba.id ?? `sem-verba-${indice}`;
    const nomeVerba =
      verba.nome || mapaVerba.get(verba.id ?? "") || (p.descricao as string) || "—";
    return {
      numero: Number(p.numero ?? indice + 1),
      verba: nomeVerba,
      competencia: String(p.competencia ?? ""),
      competenciaRotulo: String(p.competencia_rotulo ?? p.competencia ?? ""),
      vencimento: String(p.vencimento ?? ""),
      valorOriginal: String(p.principal ?? ""),
      inicioCorrecao: String(p.inicio_correcao ?? correcao.termo_inicial ?? ""),
      correcao: String(correcao.correcao ?? "0.00"),
      inicioJuros: String(p.inicio_juros ?? ""),
      juros: String(juros.juros ?? "0.00"),
      multa: String(multa.valor ?? "0.00"),
      honorarios: String(honorarios.valor ?? "0.00"),
      pagamento: String(p.total_pago ?? "0.00"),
      saldo: String(p.saldo ?? "0.00"),
      total: String(p.total ?? "0.00"),
      chaveVerba,
    };
  });
}

const COLUNAS: Array<{ key: keyof LinhaAuditoria; header: string; monetario?: boolean }> = [
  { key: "verba", header: "Verba" },
  { key: "competenciaRotulo", header: "Competência" },
  { key: "vencimento", header: "Vencimento" },
  { key: "valorOriginal", header: "Valor original", monetario: true },
  { key: "inicioCorrecao", header: "Início correção" },
  { key: "correcao", header: "Correção", monetario: true },
  { key: "inicioJuros", header: "Início juros" },
  { key: "juros", header: "Juros", monetario: true },
  { key: "multa", header: "Multa", monetario: true },
  { key: "honorarios", header: "Honorários", monetario: true },
  { key: "pagamento", header: "Pagamento", monetario: true },
  { key: "saldo", header: "Saldo", monetario: true },
  { key: "total", header: "Total", monetario: true },
];

interface Props {
  calculo: CalculoCriado;
}

export function TabelaAuditoria({ calculo }: Props) {
  const linhas = useMemo(() => extrairLinhas(calculo), [calculo]);
  const [copiado, setCopiado] = useState(false);
  const resumo = calculo.resumo;

  const grupos = useMemo(() => {
    const ordem: string[] = [];
    const mapa = new Map<string, LinhaAuditoria[]>();
    for (const linha of linhas) {
      if (!mapa.has(linha.chaveVerba)) {
        mapa.set(linha.chaveVerba, []);
        ordem.push(linha.chaveVerba);
      }
      mapa.get(linha.chaveVerba)!.push(linha);
    }
    return ordem.map((chave) => ({
      chave,
      nome: mapa.get(chave)![0].verba,
      linhas: mapa.get(chave)!,
    }));
  }, [linhas]);

  async function copiarTabela() {
    const cabecalho = COLUNAS.map((c) => c.header).join("\t");
    const corpo = linhas
      .map((linha) =>
        COLUNAS.map((c) => {
          const valor = linha[c.key];
          return c.monetario ? monetario(valor) : String(valor ?? "");
        }).join("\t"),
      )
      .join("\n");
    const texto = `${cabecalho}\n${corpo}\n\nTotal (backend):\t${monetario(resumo?.total)}\nSaldo (backend):\t${monetario(resumo?.saldo)}`;
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-ink-900">
          Memória de cálculo — detalhamento
        </h2>
        <Tooltip text="Valores vêm do backend (memória de cálculo). O React não recalcula. Rolagem horizontal e cabeçalho fixo para muitas colunas." />
      </div>

      {linhas.length === 0 ? (
        <Message tom="info">Nenhuma parcela na memória deste cálculo.</Message>
      ) : (
        <div className="overflow-auto rounded-xl border border-ink-200 bg-white max-h-[70vh]">
          <table className="min-w-[1400px] border-collapse text-sm">
            <thead className="sticky top-0 z-20 bg-ink-900 text-left text-xs uppercase tracking-wide text-white">
              <tr>
                {COLUNAS.map((coluna, idx) => (
                  <th
                    key={coluna.key}
                    scope="col"
                    className={[
                      "border-b border-ink-700 px-3 py-2.5 font-semibold",
                      coluna.monetario ? "text-right" : "text-left",
                      idx === 0
                        ? "sticky left-0 z-30 bg-ink-900 min-w-[140px]"
                        : "",
                    ].join(" ")}
                  >
                    {coluna.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grupos.map((grupo, grupoIdx) => (
                <Fragment key={`grupo-${grupo.chave}`}>
                  <tr className="bg-brand-50">
                    <td
                      colSpan={COLUNAS.length}
                      className="sticky left-0 border-b border-brand-200 px-3 py-2 text-sm font-semibold text-brand-900"
                    >
                      Verba: {grupo.nome}
                      <span className="ml-2 text-xs font-normal text-brand-700">
                        ({grupo.linhas.length}{" "}
                        {grupo.linhas.length === 1 ? "parcela" : "parcelas"})
                      </span>
                    </td>
                  </tr>
                  {grupo.linhas.map((linha, i) => (
                    <tr
                      key={`${grupo.chave}-${linha.numero}-${i}`}
                      className={[
                        "border-b border-ink-100",
                        grupoIdx % 2 === 0 ? "bg-white" : "bg-ink-50/40",
                        "hover:bg-brand-50/40",
                      ].join(" ")}
                    >
                      {COLUNAS.map((coluna, colIdx) => {
                        const valor = linha[coluna.key];
                        return (
                          <td
                            key={coluna.key}
                            className={[
                              "px-3 py-2 align-middle text-ink-800",
                              coluna.monetario
                                ? "text-right font-mono tabular-nums"
                                : "text-left",
                              colIdx === 0
                                ? "sticky left-0 z-10 bg-inherit font-medium text-ink-900 min-w-[140px] border-r border-ink-200"
                                : "",
                            ].join(" ")}
                          >
                            {coluna.monetario
                              ? monetario(valor)
                              : coluna.key === "vencimento"
                                ? formatarDataBR(String(valor ?? ""))
                                : String(valor ?? "—")}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
            <tfoot className="sticky bottom-0 z-20 bg-ink-100 text-sm font-semibold text-ink-900">
              <tr>
                <td
                  colSpan={COLUNAS.length}
                  className="border-t-2 border-ink-300 px-3 py-2.5"
                >
                  <div className="flex flex-wrap gap-x-6 gap-y-1">
                    <span>
                      Parcelas: <span className="font-mono">{resumo?.qtd_parcelas ?? linhas.length}</span>
                    </span>
                    <span>
                      Principal:{" "}
                      <span className="font-mono">{monetario(resumo?.principal)}</span>
                    </span>
                    <span>
                      Correção:{" "}
                      <span className="font-mono">{monetario(resumo?.correcao)}</span>
                    </span>
                    <span>
                      Juros: <span className="font-mono">{monetario(resumo?.juros)}</span>
                    </span>
                    <span>
                      Multa: <span className="font-mono">{monetario(resumo?.multa)}</span>
                    </span>
                    <span>
                      Honorários:{" "}
                      <span className="font-mono">{monetario(resumo?.honorarios)}</span>
                    </span>
                    <span>
                      Pagamentos:{" "}
                      <span className="font-mono">{monetario(resumo?.pagamentos)}</span>
                    </span>
                    <span>
                      Total: <span className="font-mono text-brand-800">{monetario(resumo?.total)}</span>
                    </span>
                    <span>
                      Saldo: <span className="font-mono text-brand-800">{monetario(resumo?.saldo)}</span>
                    </span>
                  </div>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={copiarTabela}>
          {copiado ? "Tabela copiada!" : "Copiar tabela"}
        </Button>
        <span className="text-xs text-ink-500">
          Totais no rodapé são os valores retornados pelo backend.
        </span>
      </div>
    </div>
  );
}
