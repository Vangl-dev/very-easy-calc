/**
 * Critérios escritos "como na sentença": termo inicial e taxa dos juros,
 * honorários da sentença e encargos do art. 523, §1º, do CPC — e o texto
 * de conferência que descreve, em português, o que será calculado.
 */
import type { EncargoConsolidadoPayload } from "../../types/api";
import {
  fracaoDePercentual,
  formatarDataBR,
  formatarMoedaBR,
  paraNumero,
  percentualValido,
  verbaSomavel,
  type EstadoPagamentoVerba,
  type EstadoVerba,
} from "./estadoVerba";

// --- Juros ---------------------------------------------------------------

export type TermoJuros = "cada_valor" | "data_unica";
export type TaxaJuros = "legal" | "um_por_cento";

export interface EstadoJurosDesde {
  termo: TermoJuros;
  /** Usada quando `termo` é "data_unica" (ex.: citação, trânsito em julgado). */
  data: string;
}

export const JUROS_DESDE_PADRAO: EstadoJurosDesde = { termo: "cada_valor", data: "" };

export const TAXAS_JUROS: Array<{ valor: TaxaJuros; rotulo: string }> = [
  { valor: "legal", rotulo: "Taxa legal de cada época" },
  { valor: "um_por_cento", rotulo: "1% ao mês (fixado na decisão)" },
];

export function taxaDaVerba(verba: EstadoVerba): TaxaJuros {
  return verba.jurosModalidade === "fixa" ? "um_por_cento" : "legal";
}

export function camposDaTaxa(taxa: TaxaJuros): Pick<EstadoVerba, "jurosModalidade" | "jurosTaxa"> {
  return taxa === "um_por_cento"
    ? { jurosModalidade: "fixa", jurosTaxa: "1" }
    : { jurosModalidade: "taxa_legal", jurosTaxa: "" };
}

/** Termo inicial dos juros de uma verba, conforme o controle "Juros desde". */
export function inicioJurosPara(verba: EstadoVerba, desde: EstadoJurosDesde): string {
  return desde.termo === "data_unica" ? desde.data : verba.correcaoInicio;
}

/** Reconhece, num cálculo salvo, se todos os juros partem de uma mesma data. */
export function jurosDesdeDasVerbas(verbas: EstadoVerba[]): EstadoJurosDesde {
  const comJuros = verbas.filter((v) => v.jurosAplicar && v.jurosInicio);
  if (comJuros.length === 0) return JUROS_DESDE_PADRAO;
  const datas = new Set(comJuros.map((v) => v.jurosInicio));
  const diferenteDaLinha = comJuros.some((v) => v.jurosInicio !== v.correcaoInicio);
  if (datas.size === 1 && diferenteDaLinha) {
    return { termo: "data_unica", data: comJuros[0].jurosInicio };
  }
  return JUROS_DESDE_PADRAO;
}

const FIM_CC1916 = "2003-01-11";
const FIM_CC2002 = "2024-08-29";

/** Descreve as taxas que efetivamente incidem entre as datas informadas. */
export function descreverTaxaLegal(inicio: string, fim: string): string {
  const eras: string[] = [];
  if (inicio <= FIM_CC1916) eras.push("6% ao ano até 11/01/2003 (CC/1916)");
  if (inicio <= FIM_CC2002 && fim > FIM_CC1916) {
    eras.push("12% ao ano até 29/08/2024 (CC/2002)");
  }
  if (fim > FIM_CC2002) {
    eras.push("Taxa Legal (Selic menos IPCA, Lei 14.905/24) a partir de 30/08/2024");
  }
  return eras.length > 0 ? eras.join("; ") : "taxa legal";
}

// --- Honorários da sentença e art. 523 ----------------------------------

export type BaseHonorariosSentenca = "corrigido" | "com_juros";

export interface EstadoEncargosSentenca {
  honorarios: { ativo: boolean; percentual: string; base: BaseHonorariosSentenca };
  art523: {
    ativo: boolean;
    multa: string;
    honorarios: string;
    base: BaseHonorariosSentenca;
    /** Soma os honorários da sentença à base da multa e dos honorários do 523. */
    incluirHonorariosSentenca: boolean;
  };
}

export const ENCARGOS_SENTENCA_PADRAO: EstadoEncargosSentenca = {
  honorarios: { ativo: false, percentual: "10", base: "com_juros" },
  art523: {
    ativo: false,
    multa: "10",
    honorarios: "10",
    base: "com_juros",
    incluirHonorariosSentenca: true,
  },
};

const ID_HONORARIOS_SENTENCA = "honorarios_sentenca";
const ID_MULTA_523 = "multa_523";
const ID_HONORARIOS_523 = "honorarios_523";
const IDS_SENTENCA = new Set([ID_HONORARIOS_SENTENCA, ID_MULTA_523, ID_HONORARIOS_523]);

const DEBITO_ATUALIZADO: NonNullable<EncargoConsolidadoPayload["componentes"]> = [
  "principal_corrigido",
  "juros_individuais",
];

function componentesDa(base: BaseHonorariosSentenca): EncargoConsolidadoPayload["componentes"] {
  return base === "com_juros" ? [...DEBITO_ATUALIZADO] : ["principal_corrigido"];
}

function baseDe(encargo: EncargoConsolidadoPayload): BaseHonorariosSentenca {
  return (encargo.componentes ?? []).includes("juros_individuais") ? "com_juros" : "corrigido";
}

export function montarEncargosSentenca(
  estado: EstadoEncargosSentenca,
): EncargoConsolidadoPayload[] {
  const itens: EncargoConsolidadoPayload[] = [];
  const { honorarios, art523 } = estado;
  if (honorarios.ativo) {
    itens.push({
      id: ID_HONORARIOS_SENTENCA,
      tipo: "honorarios",
      ordem: 1,
      componentes: componentesDa(honorarios.base),
      percentual: fracaoDePercentual(honorarios.percentual),
      entra_no_total: true,
    });
  }
  if (art523.ativo) {
    const predecessores =
      honorarios.ativo && art523.incluirHonorariosSentenca ? [ID_HONORARIOS_SENTENCA] : [];
    if (art523.multa.trim()) {
      itens.push({
        id: ID_MULTA_523,
        tipo: "multa",
        ordem: 2,
        componentes: componentesDa(art523.base),
        predecessores,
        percentual: fracaoDePercentual(art523.multa),
        entra_no_total: true,
      });
    }
    if (art523.honorarios.trim()) {
      itens.push({
        id: ID_HONORARIOS_523,
        tipo: "honorarios",
        ordem: 3,
        componentes: componentesDa(art523.base),
        predecessores,
        percentual: fracaoDePercentual(art523.honorarios),
        entra_no_total: true,
      });
    }
  }
  return itens;
}

function percentualParaTela(valor: string | null | undefined): string {
  if (!valor) return "";
  const n = Number(valor);
  return Number.isFinite(n) ? String(Number((n * 100).toFixed(6))).replace(".", ",") : "";
}

/**
 * Lê de volta os encargos de um cálculo salvo. Devolve `null` quando há
 * encargos consolidados que este formulário não representa fielmente.
 */
export function hidratarEncargosSentenca(
  consolidados: EncargoConsolidadoPayload[],
): EstadoEncargosSentenca | null {
  if (consolidados.length === 0) return ENCARGOS_SENTENCA_PADRAO;
  const porId = new Map(consolidados.map((e) => [e.id, e]));
  const conhecidos = consolidados.every((e) => IDS_SENTENCA.has(e.id));
  if (conhecidos) {
    const hs = porId.get(ID_HONORARIOS_SENTENCA);
    const m = porId.get(ID_MULTA_523);
    const h = porId.get(ID_HONORARIOS_523);
    const ref523 = m ?? h;
    return {
      honorarios: {
        ativo: Boolean(hs),
        percentual: hs ? percentualParaTela(hs.percentual) : "10",
        base: hs ? baseDe(hs) : "com_juros",
      },
      art523: {
        ativo: Boolean(ref523),
        multa: m ? percentualParaTela(m.percentual) : "",
        honorarios: h ? percentualParaTela(h.percentual) : "",
        base: ref523 ? baseDe(ref523) : "com_juros",
        incluirHonorariosSentenca: ref523
          ? (ref523.predecessores ?? []).includes(ID_HONORARIOS_SENTENCA)
          : true,
      },
    };
  }
  // Cálculos salvos com o antigo "encargo único sobre o total".
  if (consolidados.length === 1) {
    const [legado] = consolidados;
    const componentes = legado.componentes ?? [];
    const comJuros =
      componentes.includes("principal_corrigido") && componentes.includes("juros_individuais");
    const soCorrigido = componentes.length === 1 && componentes[0] === "principal_corrigido";
    const simples =
      !legado.valor_fixo && !(legado.predecessores?.length) && !(legado.verba_ids?.length);
    if (simples && legado.tipo === "honorarios" && (comJuros || soCorrigido)) {
      return {
        ...ENCARGOS_SENTENCA_PADRAO,
        honorarios: {
          ativo: true,
          percentual: percentualParaTela(legado.percentual),
          base: comJuros ? "com_juros" : "corrigido",
        },
      };
    }
    if (simples && legado.tipo === "multa" && (comJuros || soCorrigido)) {
      return {
        ...ENCARGOS_SENTENCA_PADRAO,
        art523: {
          ativo: true,
          multa: percentualParaTela(legado.percentual),
          honorarios: "",
          base: comJuros ? "com_juros" : "corrigido",
          incluirHonorariosSentenca: true,
        },
      };
    }
  }
  return null;
}

export function errosEncargosSentenca(estado: EstadoEncargosSentenca): string[] {
  const erros: string[] = [];
  if (estado.honorarios.ativo && !percentualValido(estado.honorarios.percentual)) {
    erros.push("Honorários da sentença: informe o percentual (ex.: 10).");
  }
  if (estado.art523.ativo) {
    const { multa, honorarios } = estado.art523;
    if (!multa.trim() && !honorarios.trim()) {
      erros.push("Art. 523: informe o percentual da multa e/ou dos honorários.");
    }
    if (multa.trim() && !percentualValido(multa)) {
      erros.push("Art. 523: percentual da multa inválido (ex.: 10).");
    }
    if (honorarios.trim() && !percentualValido(honorarios)) {
      erros.push("Art. 523: percentual dos honorários inválido (ex.: 10).");
    }
  }
  return erros;
}

// --- Conferência em português -------------------------------------------

export interface Conferencia {
  linhas: string[];
  encargos: string[];
  pagamentos: string[];
  alertas: string[];
}

function competencia(iso: string): string {
  const [ano, mes] = iso.split("-");
  return mes && ano ? `${mes}/${ano}` : iso;
}

function pct(texto: string): string {
  return `${texto.trim().replace(".", ",")}%`;
}

function valorDaLinha(verba: EstadoVerba): string {
  const n = paraNumero(verba.valor);
  return Number.isFinite(n) ? formatarMoedaBR(n) : verba.valor;
}

function descreverJuros(verba: EstadoVerba, dataFinal: string): string {
  if (!verba.jurosAplicar) return "sem juros";
  const inicio = verba.jurosInicio;
  const fim = verba.jurosFim || dataFinal;
  const base = verba.jurosBase === "principal" ? "sobre o valor original" : "sobre o valor corrigido";
  const periodo = `de ${formatarDataBR(inicio)} até ${formatarDataBR(fim)}`;
  if (verba.regimes.length > 0) {
    return `juros conforme as regras de atualização por período (${periodo})`;
  }
  if (verba.jurosModalidade === "fixa") {
    return `juros de 1% ao mês ${periodo}, ${base}`;
  }
  return `juros pela taxa legal de cada época — ${descreverTaxaLegal(inicio, fim)} — ${periodo}, ${base}`;
}

function descreverCorrecao(verba: EstadoVerba, dataFinal: string, indexador: string): string {
  if (!verba.correcaoAplicar) return "sem correção monetária";
  if (verba.regimes.length > 0) {
    return "correção conforme as regras de atualização por período";
  }
  return `correção pela ${indexador} de ${competencia(verba.correcaoInicio)} até ${competencia(verba.correcaoFim || dataFinal)}`;
}

function descreverEncargoDaLinha(
  nome: string,
  aplicar: boolean,
  percentual: string,
  valorFixo: string,
  base: string,
): string | null {
  if (!aplicar) return null;
  if (valorFixo.trim()) return `${nome} fixa de R$ ${valorFixo.trim()}`;
  const rotuloBase =
    base === "principal" ? "o valor original" : base === "com_juros" ? "o valor corrigido + juros" : "o valor corrigido";
  return `${nome} de ${pct(percentual)} sobre ${rotuloBase}`;
}

export function montarConferencia(args: {
  dataFinal: string;
  indexador: string;
  verbas: EstadoVerba[];
  pagamentos: EstadoPagamentoVerba[];
  encargos: EstadoEncargosSentenca;
}): Conferencia {
  const { dataFinal, indexador, verbas, pagamentos, encargos } = args;
  const alertas: string[] = [];
  const linhas = verbas.map((verba, i) => {
    const nome = verba.nome.trim() || `Lançamento ${i + 1}`;
    const data = verba.correcaoInicio ? ` em ${formatarDataBR(verba.correcaoInicio)}` : "";
    const partes = [
      descreverCorrecao(verba, dataFinal, indexador),
      descreverJuros(verba, dataFinal),
    ];
    const multa = descreverEncargoDaLinha(
      "multa", verba.multaAplicar, verba.multaPercentual, verba.multaValorFixo, verba.multaBase,
    );
    const hon = descreverEncargoDaLinha(
      "honorários", verba.honorariosAplicar, verba.honorariosPercentual,
      verba.honorariosValorFixo, verba.honorariosBase,
    );
    if (multa) partes.push(multa);
    if (hon) partes.push(hon);
    const fora = verbaSomavel(verba, verbas) ? "" : " Não entra no total.";
    if (verba.jurosAplicar && verba.correcaoInicio && verba.jurosInicio < verba.correcaoInicio) {
      alertas.push(`${nome}: os juros começam antes da data do valor (${formatarDataBR(verba.jurosInicio)}).`);
    }
    if (!verba.correcaoAplicar) alertas.push(`${nome}: sem correção monetária.`);
    if (!verba.jurosAplicar) alertas.push(`${nome}: sem juros.`);
    if (verba.multaAplicar || verba.honorariosAplicar) {
      alertas.push(`${nome}: tem multa ou honorários próprios da linha — confira se não repetem os encargos da sentença.`);
    }
    const valor = verba.tipo === "percentual" ? `${pct(verba.percentual)} de outro valor` : valorDaLinha(verba);
    return `${i + 1}. ${nome} — ${valor}${data}: ${partes.join("; ")}.${fora}`;
  });

  const linhasEncargos: string[] = [];
  const { honorarios, art523 } = encargos;
  if (honorarios.ativo) {
    const base = honorarios.base === "com_juros"
      ? "o débito atualizado (valor corrigido + juros)"
      : "o valor corrigido, sem juros";
    linhasEncargos.push(`Honorários da sentença: ${pct(honorarios.percentual)} sobre ${base}.`);
  }
  if (art523.ativo) {
    const itens = [
      art523.multa.trim() ? `multa de ${pct(art523.multa)}` : null,
      art523.honorarios.trim() ? `honorários de ${pct(art523.honorarios)}` : null,
    ].filter(Boolean).join(" e ");
    const somaHonorarios = honorarios.ativo && art523.incluirHonorariosSentenca
      ? " somado aos honorários da sentença"
      : "";
    const base523 = art523.base === "com_juros"
      ? "o débito atualizado (valor corrigido + juros)"
      : "o valor corrigido, sem juros";
    linhasEncargos.push(
      `Art. 523, §1º, do CPC: ${itens} sobre ${base523}${somaHonorarios}. ` +
        "Só cabe se a parte foi intimada para pagar e não pagou em 15 dias.",
    );
  }
  if (!honorarios.ativo && !art523.ativo) {
    linhasEncargos.push("Sem honorários da sentença e sem multa/honorários do art. 523.");
  }

  const linhasPagamentos = pagamentos
    .filter((pg) => pg.data && pg.valor.trim())
    .map((pg) => {
      const n = paraNumero(pg.valor);
      const valor = Number.isFinite(n) ? formatarMoedaBR(n) : pg.valor;
      const descricao = pg.descricao.trim() ? ` (${pg.descricao.trim()})` : "";
      return `${valor} em ${formatarDataBR(pg.data)}${descricao}: abatido nessa data — quita primeiro os juros vencidos até ali e depois o principal; o valor é corrigido até a data final para comparar com o débito.`;
    });

  return {
    linhas,
    encargos: linhasEncargos,
    pagamentos: linhasPagamentos,
    alertas,
  };
}
