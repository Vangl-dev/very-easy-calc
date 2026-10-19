import { Fragment, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Message } from "../../components/ui/Message";
import { formatarDataBR } from "../civel/estadoVerba";
import type { CalculoCriado } from "../../types/api";

type LinhaAuditoria = {
  numero: number;
  verba: string;
  competencia: string;
  competenciaRotulo: string;
  vencimento: string;
  dataPagamento: string;
  mes: string;
  ano: string;
  valorOriginal: string;
  inicioCorrecao: string;
  correcao: string;
  indice: string;
  indiceInicial: string;
  inicioJuros: string;
  diasJuros: string;
  juros: string;
  multa: string;
  honorarios: string;
  pagamento: string;
  diferenca: string;
  saldo: string;
  total: string;
  salarioMinimo: string;
  percentual: string;
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

function percentual(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return `${(n * 100).toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}%`;
}

function simples(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return String(valor);
}

function numeroBr(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  });
}

function extrairLinhas(
  calculo: CalculoCriado,
  ehAlimentos: boolean,
): LinhaAuditoria[] {
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
      fator_inicial?: string;
      fator_exibicao?: string | null;
      razao?: string | null;
    };
    const juros = (p.juros ?? {}) as {
      juros?: string;
      trechos?: Array<{ dias?: number }>;
    };
    const multa = (p.multa ?? {}) as { valor?: string };
    const honorarios = (p.honorarios ?? {}) as { valor?: string };
    const pagamentos = (p.pagamentos ?? []) as Array<{ data?: string }>;
    const competencia = String(p.competencia ?? "");
    const [anoComp, mesComp] = competencia.split("-");
    const chaveVerba =
      verba.id ?? (ehAlimentos ? "alimentos" : `sem-verba-${indice}`);
    const nomeVerba =
      verba.nome ||
      mapaVerba.get(verba.id ?? "") ||
      (ehAlimentos ? "Alimentos" : (p.descricao as string)) ||
      "—";
    return {
      numero: Number(p.numero ?? indice + 1),
      verba: nomeVerba,
      competencia,
      competenciaRotulo: String(p.competencia_rotulo ?? p.competencia ?? ""),
      vencimento: String(p.vencimento ?? ""),
      dataPagamento: String(pagamentos[0]?.data ?? ""),
      mes: mesComp ?? "",
      ano: anoComp ?? "",
      valorOriginal: String(p.principal ?? ""),
      inicioCorrecao: String(p.inicio_correcao ?? correcao.termo_inicial ?? ""),
      correcao: String(correcao.correcao ?? "0.00"),
      indice: String(correcao.fator_exibicao ?? correcao.razao ?? ""),
      indiceInicial: String(correcao.fator_inicial ?? ""),
      inicioJuros: String(p.inicio_juros ?? ""),
      diasJuros: String(juros.trechos?.[0]?.dias ?? ""),
      juros: String(juros.juros ?? "0.00"),
      multa: String(multa.valor ?? "0.00"),
      honorarios: String(honorarios.valor ?? "0.00"),
      pagamento: String(p.total_pago ?? "0.00"),
      diferenca: String(p.diferenca ?? ""),
      saldo: String(p.saldo ?? "0.00"),
      total: String(p.total ?? "0.00"),
      salarioMinimo: String(p.salario_minimo ?? ""),
      percentual: String(p.percentual ?? ""),
      chaveVerba,
    };
  });
}

type Coluna = {
  key: keyof LinhaAuditoria;
  header: string;
  monetario?: boolean;
  percentual?: boolean;
  numero?: boolean;
};

const COLUNAS_CIVEL_COMPACTO: Coluna[] = [
  { key: "verba", header: "Verba" },
  { key: "competenciaRotulo", header: "Competência" },
  { key: "valorOriginal", header: "Principal", monetario: true },
  { key: "correcao", header: "Correção", monetario: true },
  { key: "juros", header: "Juros", monetario: true },
  { key: "total", header: "Total", monetario: true },
];

const COLUNAS_CIVEL_DETALHE: Coluna[] = [
  ...COLUNAS_CIVEL_COMPACTO,
  { key: "vencimento", header: "Vencimento" },
  { key: "inicioCorrecao", header: "Início correção" },
  { key: "inicioJuros", header: "Início juros" },
  { key: "diasJuros", header: "Dias de juros", numero: true },
  { key: "multa", header: "Multa", monetario: true },
  { key: "honorarios", header: "Honorários", monetario: true },
  { key: "pagamento", header: "Pagamento", monetario: true },
  { key: "diferenca", header: "Diferença", monetario: true },
  { key: "saldo", header: "Saldo", monetario: true },
  { key: "indiceInicial", header: "Índice inicial", numero: true },
  { key: "indice", header: "Índice atual", numero: true },
];

const COLUNAS_ALIMENTOS: Coluna[] = [
  { key: "competenciaRotulo", header: "Competência" },
  { key: "vencimento", header: "Vencimento" },
  { key: "salarioMinimo", header: "Salário mínimo", monetario: true },
  { key: "percentual", header: "Percentual", percentual: true },
  { key: "valorOriginal", header: "Valor devido", monetario: true },
  { key: "pagamento", header: "Valor pago", monetario: true },
  { key: "diferenca", header: "Diferença", monetario: true },
  { key: "indiceInicial", header: "Índice inicial", numero: true },
  { key: "indice", header: "Índice atual", numero: true },
  { key: "correcao", header: "Correção", monetario: true },
  { key: "juros", header: "Juros", monetario: true },
  { key: "total", header: "Total", monetario: true },
  { key: "saldo", header: "Saldo", monetario: true },
];

interface Props {
  calculo: CalculoCriado;
  compacto?: boolean;
}

export function TabelaAuditoria({ calculo, compacto = false }: Props) {
  const ehAlimentos = calculo.tipo === "alimentos";
  const colunas = ehAlimentos
    ? COLUNAS_ALIMENTOS
    : compacto
      ? COLUNAS_CIVEL_COMPACTO
      : COLUNAS_CIVEL_DETALHE;
  const linhas = useMemo(
    () => extrairLinhas(calculo, ehAlimentos),
    [calculo, ehAlimentos],
  );
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

  function formatarCelula(coluna: Coluna, valor: unknown): string {
    if (coluna.monetario) return monetario(valor);
    if (coluna.percentual) return percentual(valor);
    if (coluna.numero) return numeroBr(valor);
    if (coluna.key === "vencimento" || coluna.key === "dataPagamento") {
      return formatarDataBR(String(valor ?? ""));
    }
    return simples(valor);
  }

  async function copiarTabela() {
    const cabecalho = colunas.map((c) => c.header).join("\t");
    const corpo = linhas
      .map((linha) =>
        colunas.map((c) => formatarCelula(c, linha[c.key])).join("\t"),
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
      {linhas.length === 0 ? (
        <Message tom="info">Nenhuma parcela na memória deste cálculo.</Message>
      ) : (
        <div className="overflow-x-auto border border-line bg-panel">
          <table
            className={`w-full border-collapse text-[13.5px] ${
              ehAlimentos ? "min-w-[1100px]" : "min-w-[720px]"
            }`}
          >
            <thead>
              <tr className="border-b border-line bg-paper">
                {colunas.map((coluna) => (
                  <th
                    key={coluna.key}
                    scope="col"
                    className={[
                      "px-3 py-2.5 text-[11px] font-semibold uppercase tracking-legal text-ink-500",
                      coluna.monetario || coluna.percentual || coluna.numero
                        ? "text-right"
                        : "text-left",
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
                  <tr className="border-b border-line bg-brand-50/60">
                    <td
                      colSpan={colunas.length}
                      className="px-3 py-2 text-[13px] font-semibold text-brand-800"
                    >
                      {ehAlimentos ? "Alimentos" : grupo.nome}
                      <span className="ml-2 text-[12px] font-normal text-ink-600">
                        ({grupo.linhas.length}{" "}
                        {grupo.linhas.length === 1
                          ? ehAlimentos
                            ? "competência"
                            : "parcela"
                          : ehAlimentos
                            ? "competências"
                            : "parcelas"}
                        )
                      </span>
                    </td>
                  </tr>
                  {grupo.linhas.map((linha, i) => (
                    <tr
                      key={`${grupo.chave}-${linha.numero}-${i}`}
                      className={[
                        "border-b border-line/80",
                        grupoIdx % 2 === 0 ? "bg-panel" : "bg-paper/60",
                      ].join(" ")}
                    >
                      {colunas.map((coluna, colIdx) => {
                        const valor = linha[coluna.key];
                        const numerico =
                          coluna.monetario || coluna.percentual || coluna.numero;
                        return (
                          <td
                            key={coluna.key}
                            className={[
                              "px-3 py-2.5 align-middle text-ink-800",
                              numerico
                                ? "text-right font-mono tabular-nums"
                                : "text-left",
                              colIdx === 0
                                ? "font-medium text-ink-900"
                                : "",
                            ].join(" ")}
                          >
                            {formatarCelula(coluna, valor)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-edge bg-paper">
                <td colSpan={colunas.length} className="px-3 py-3">
                  <div className="flex flex-wrap gap-x-8 gap-y-1 text-[13px] text-ink-700">
                    <span>
                      Principal{" "}
                      <span className="font-mono font-semibold text-ink-900">
                        {monetario(resumo?.principal)}
                      </span>
                    </span>
                    <span>
                      Correção{" "}
                      <span className="font-mono font-semibold text-ink-900">
                        {monetario(resumo?.correcao)}
                      </span>
                    </span>
                    <span>
                      Juros{" "}
                      <span className="font-mono font-semibold text-ink-900">
                        {monetario(resumo?.juros)}
                      </span>
                    </span>
                    <span>
                      Pago{" "}
                      <span className="font-mono font-semibold text-ink-900">
                        {monetario(resumo?.pagamentos)}
                      </span>
                    </span>
                    <span>
                      Total{" "}
                      <span className="font-mono font-semibold text-brand-700">
                        {monetario(resumo?.total)}
                      </span>
                    </span>
                    <span>
                      Saldo{" "}
                      <span className="font-mono font-semibold text-brand-700">
                        {monetario(resumo?.saldo)}
                      </span>
                    </span>
                  </div>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" size="sm" onClick={copiarTabela}>
          {copiado ? "Tabela copiada!" : "Copiar tabela"}
        </Button>
        <span className="text-[12px] text-ink-500">
          Valores retornados pelo backend. O React não recalcula.
        </span>
      </div>
    </div>
  );
}
