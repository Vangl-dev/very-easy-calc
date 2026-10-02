import {
  competenciaDeData,
  competenciaValida,
} from "../../lib/competencia";
import type {
  CalculoAlimentosPayload,
  PagamentoPayload,
  RegraAlimentoPayload,
} from "../../types/api";

export type TipoRegraAlimento = "percentual" | "fixo";

export interface RegraAlimento {
  id: string;
  tipo: TipoRegraAlimento;
  percentual: string;
  valor: string;
  inicio: string;
  fim: string;
}

export interface PagamentoAlimento {
  id: string;
  competencia: string;
  data: string;
  valor: string;
}

export interface EstadoAlimentos {
  identificacao: {
    titulo: string;
    processo: string;
    parte: string;
  };
  regras: RegraAlimento[];
  pagamentos: PagamentoAlimento[];
  atualizarAte: string;
}

export const CORRECAO_PADRAO = "tjsp_tabela_pratica";
export const JUROS_PADRAO = "0.01";
export const DIA_VENCIMENTO = 10;

let contador = 0;

function proximoId(prefixo: string): string {
  contador += 1;
  return `${prefixo}-${Date.now()}-${contador}`;
}

export function novaRegra(parcial: Partial<RegraAlimento> = {}): RegraAlimento {
  return {
    id: proximoId("regra"),
    tipo: "percentual",
    percentual: "",
    valor: "",
    inicio: "",
    fim: "",
    ...parcial,
  };
}

export function novoPagamento(parcial: Partial<PagamentoAlimento> = {}): PagamentoAlimento {
  return {
    id: proximoId("pag"),
    competencia: "",
    data: "",
    valor: "",
    ...parcial,
  };
}

export function estadoInicialAlimentos(): EstadoAlimentos {
  return {
    identificacao: { titulo: "", processo: "", parte: "" },
    regras: [novaRegra()],
    pagamentos: [],
    atualizarAte: "",
  };
}

/** Aceita "85", "85,5", "0.85", "1.000,00" — formatação da entrada, sem cálculo. */
function paraNumero(texto: string): number {
  const t = texto.trim().replace("%", "").replace(/\s/g, "");
  const brasileiro = /^(\d+(?:\.\d{3})+),(\d+)$/.exec(t);
  if (brasileiro) {
    return Number(`${brasileiro[1].replace(/\./g, "")}.${brasileiro[2]}`);
  }
  return Number(t.replace(",", "."));
}

function positivo(texto: string): boolean {
  const n = paraNumero(texto);
  return Number.isFinite(n) && n > 0;
}

/** Percentual digitado em porcentagem (85) vira a fração que o backend usa (0.85). */
export function fracaoDePercentual(texto: string): string {
  return String(Number((paraNumero(texto) / 100).toFixed(6)));
}

/** Linhas totalmente vazias não contam como lançamento. */
function lancados(pagamentos: PagamentoAlimento[]): PagamentoAlimento[] {
  return pagamentos.filter(
    (p) => p.competencia.trim() !== "" || p.data !== "" || p.valor.trim() !== "",
  );
}

export function validarAlimentos(estado: EstadoAlimentos): string[] {
  const erros: string[] = [];

  if (!estado.identificacao.titulo.trim()) {
    erros.push("Informe o nome/descrição do cálculo.");
  }
  if (!estado.atualizarAte) {
    erros.push("Informe a data da atualização (até quando atualizar).");
  }
  if (estado.regras.length === 0) {
    erros.push("Inclua ao menos uma regra de alimentos.");
  }

  estado.regras.forEach((regra, indice) => {
    const rotulo = `Regra ${indice + 1}`;
    if (!regra.inicio.trim()) {
      erros.push(`${rotulo}: informe o mês/ano inicial.`);
    } else if (!competenciaValida(regra.inicio)) {
      erros.push(`${rotulo}: início inválido — use MM/AAAA (ex.: 04/2023).`);
    }
    if (regra.fim.trim() && !competenciaValida(regra.fim)) {
      erros.push(`${rotulo}: fim inválido — use MM/AAAA (ex.: 12/2025).`);
    }
    if (indice < estado.regras.length - 1 && !regra.fim.trim()) {
      erros.push(
        `${rotulo}: informe o mês/ano final — existe uma regra depois dela.`,
      );
    }
    if (regra.tipo === "percentual") {
      if (!regra.percentual.trim()) {
        erros.push(`${rotulo}: informe o percentual do salário mínimo.`);
      } else if (!positivo(regra.percentual)) {
        erros.push(`${rotulo}: percentual inválido (ex.: 85).`);
      }
    } else if (!regra.valor.trim()) {
      erros.push(`${rotulo}: informe o valor fixo.`);
    } else if (!positivo(regra.valor)) {
      erros.push(`${rotulo}: valor inválido (ex.: 1000,00).`);
    }
  });

  lancados(estado.pagamentos).forEach((pg, indice) => {
    const rotulo = `Pagamento ${indice + 1}`;
    if (!pg.competencia.trim()) {
      erros.push(`${rotulo}: informe a competência (ex.: 01/2026).`);
    } else if (!competenciaValida(pg.competencia)) {
      erros.push(`${rotulo}: competência inválida — use MM/AAAA (ex.: 01/2026).`);
    }
    if (!pg.data) {
      erros.push(`${rotulo}: informe a data do pagamento.`);
    }
    if (!pg.valor.trim()) {
      erros.push(`${rotulo}: informe o valor pago.`);
    } else if (!positivo(pg.valor)) {
      erros.push(`${rotulo}: valor inválido (ex.: 200,00).`);
    }
  });

  return erros;
}

export function montarPayloadAlimentos(
  estado: EstadoAlimentos,
): CalculoAlimentosPayload {
  const regras: RegraAlimentoPayload[] = estado.regras.map((regra) => ({
    inicio: regra.inicio.trim(),
    fim: regra.fim.trim() || null,
    tipo: regra.tipo === "percentual" ? "salario_minimo" : "fixo",
    percentual:
      regra.tipo === "percentual" ? fracaoDePercentual(regra.percentual) : null,
    valor: regra.tipo === "fixo" ? regra.valor.trim() : null,
    descricao: "",
  }));

  const pagamentos: PagamentoPayload[] = lancados(estado.pagamentos).map((pg) => ({
    competencia: pg.competencia.trim(),
    data: pg.data,
    valor: pg.valor.trim(),
    descricao: "",
  }));

  const ate = competenciaDeData(estado.atualizarAte);

  return {
    tipo: "alimentos",
    titulo: estado.identificacao.titulo.trim(),
    processo: estado.identificacao.processo.trim(),
    parte: estado.identificacao.parte.trim(),
    data_base: estado.atualizarAte,
    alimentos: {
      regras,
      ate: ate ?? "",
      dia_vencimento: DIA_VENCIMENTO,
    },
    correcao: {
      aplicar: true,
      indexador: CORRECAO_PADRAO,
      termo_inicial: null,
      termo_final: null,
    },
    juros: {
      aplicar: true,
      modalidade: "fixa",
      taxa: JUROS_PADRAO,
      unidade: "mensal",
      base: "corrigido",
      inicio: null,
      fim: null,
    },
    multa: { aplicar: false },
    honorarios: { aplicar: false },
    pagamentos,
  };
}
