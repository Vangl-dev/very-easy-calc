import type {
  PagamentoPayload,
  RegimeAtualizacaoPayload,
  VerbaPayload,
} from "../../types/api";

export type TipoVerba = "valor" | "percentual";

export interface EstadoPagamentoVerba {
  id: string;
  data: string;
  valor: string;
  descricao: string;
}

export const CORRECOES_REGIME = [
  { valor: "", rotulo: "Nenhuma" },
  { valor: "tjsp_tabela_pratica", rotulo: "Tabela Prática TJSP" },
  { valor: "selic", rotulo: "SELIC" },
];

export const JUROS_REGIME = [
  { valor: "", rotulo: "Nenhum" },
  { valor: "fixa", rotulo: "1% ao mês" },
  { valor: "taxa_legal", rotulo: "Taxa Legal (BCB SGS 29543)" },
  { valor: "selic", rotulo: "SELIC" },
];

/** Opções de base de incidência de multa e honorários (rótulos da interface). */
export const BASES_ENCARGO = [
  { valor: "corrigido", rotulo: "Valor corrigido" },
  { valor: "principal", rotulo: "Valor original" },
  { valor: "com_juros", rotulo: "Corrigido + juros" },
];

/** Período com critério próprio de atualização (um regime por linha). */
export interface EstadoRegime {
  id: string;
  dataInicio: string;
  dataFim: string;
  correcao: string;
  juros: string;
}

export interface EstadoVerba {
  id: string;
  tipo: TipoVerba;
  nome: string;
  descricao: string;
  valor: string;
  percentual: string;
  baseVerbaId: string;
  /** Composição no total: ausente/null = padrão (o backend decide), true/false explícito. */
  entraNoTotal?: boolean | null;
  correcaoAplicar: boolean;
  correcaoIndexador: string;
  correcaoInicio: string;
  correcaoFim: string;
  jurosAplicar: boolean;
  jurosModalidade: string;
  jurosTaxa: string;
  jurosBase: string;
  jurosInicio: string;
  jurosFim: string;
  multaAplicar: boolean;
  multaPercentual: string;
  multaValorFixo: string;
  multaBase: string;
  honorariosAplicar: boolean;
  honorariosPercentual: string;
  honorariosValorFixo: string;
  honorariosBase: string;
  pagamentos: EstadoPagamentoVerba[];
  regimes: EstadoRegime[];
}

export function novaVerba(parcial: Partial<EstadoVerba> = {}): EstadoVerba {
  return {
    id: `verba-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    tipo: "valor",
    nome: "",
    descricao: "",
    valor: "",
    percentual: "",
    baseVerbaId: "",
    entraNoTotal: null,
    correcaoAplicar: true,
    correcaoIndexador: "tjsp_tabela_pratica",
    correcaoInicio: "",
    correcaoFim: "",
    jurosAplicar: false,
    jurosModalidade: "taxa_legal",
    jurosTaxa: "",
    jurosBase: "corrigido",
    jurosInicio: "",
    jurosFim: "",
    multaAplicar: false,
    multaPercentual: "",
    multaValorFixo: "",
    multaBase: "corrigido",
    honorariosAplicar: false,
    honorariosPercentual: "",
    honorariosValorFixo: "",
    honorariosBase: "corrigido",
    pagamentos: [],
    regimes: [],
    ...parcial,
  };
}

export function novaRegime(parcial: Partial<EstadoRegime> = {}): EstadoRegime {
  return {
    id: `regime-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    dataInicio: "",
    dataFim: "",
    correcao: "",
    juros: "",
    ...parcial,
  };
}

export function novaPagamento(
  parcial: Partial<EstadoPagamentoVerba> = {},
): EstadoPagamentoVerba {
  return {
    id: `pgto-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    data: "",
    valor: "",
    descricao: "",
    ...parcial,
  };
}

/** Se a verba soma no total da execução (padrão do backend quando null). */
export function verbaSomavel(verba: EstadoVerba, verbas: EstadoVerba[]): boolean {
  if (verba.entraNoTotal === false) return false;
  if (verba.entraNoTotal === true) return true;
  return dependentesDe(verba.id, verbas).length === 0;
}

/** Verba que recebe os pagamentos globais — apenas uma, para não subtrair duas vezes. */
export function verbaAlvoPagamento(verbas: EstadoVerba[]): EstadoVerba | null {
  if (verbas.length === 0) return null;
  const somaveis = verbas.filter((v) => verbaSomavel(v, verbas));
  return somaveis[0] ?? verbas[0];
}

/** Anexa os pagamentos do formulário à única verba somável escolhida. */
export function anexarPagamentosGlobais(
  verbas: EstadoVerba[],
  pagamentos: EstadoPagamentoVerba[],
): EstadoVerba[] {
  if (pagamentos.length === 0) return verbas;
  const alvo = verbaAlvoPagamento(verbas);
  if (!alvo) return verbas;
  return verbas.map((v) =>
    v.id === alvo.id
      ? { ...v, pagamentos: [...v.pagamentos, ...pagamentos] }
      : v,
  );
}

/** Aplica uma configuração em todas as verbas (escrita dos controles globais). */
export function aplicarEmTodas(
  verbas: EstadoVerba[],
  parcial: Partial<EstadoVerba>,
): EstadoVerba[] {
  return verbas.map((v) => ({ ...v, ...parcial }));
}

export interface ConfigEncargoGeral {
  aplicar: boolean;
  percentual: string;
  valorFixo: string;
  base: string;
}

/**
 * Escrita dos controles globais de multa/honorários no modo simples:
 * percentual replica em todas as verbas; valor fixo entra só na primeira
 * somável — senão o total multiplicaria o valor por N verbas.
 */
export function aplicarEncargoGeral(
  verbas: EstadoVerba[],
  tipo: "multa" | "honorarios",
  config: ConfigEncargoGeral,
): EstadoVerba[] {
  if (verbas.length === 0) return verbas;
  const alvo = verbaAlvoPagamento(verbas);
  if (!alvo) return verbas;
  const ehFixo = config.valorFixo.trim() !== "";
  return verbas.map((v) => {
    const noAlvo = v.id === alvo.id;
    if (tipo === "multa") {
      if (!config.aplicar) return { ...v, multaAplicar: false };
      if (ehFixo) {
        return noAlvo
          ? {
              ...v,
              multaAplicar: true,
              multaPercentual: "",
              multaValorFixo: config.valorFixo,
              multaBase: config.base,
            }
          : { ...v, multaAplicar: false };
      }
      return {
        ...v,
        multaAplicar: true,
        multaPercentual: config.percentual,
        multaValorFixo: "",
        multaBase: config.base,
      };
    }
    if (!config.aplicar) return { ...v, honorariosAplicar: false };
    if (ehFixo) {
      return noAlvo
        ? {
            ...v,
            honorariosAplicar: true,
            honorariosPercentual: "",
            honorariosValorFixo: config.valorFixo,
            honorariosBase: config.base,
          }
        : { ...v, honorariosAplicar: false };
    }
    return {
      ...v,
      honorariosAplicar: true,
      honorariosPercentual: config.percentual,
      honorariosValorFixo: "",
      honorariosBase: config.base,
    };
  });
}

export function montarPagamentosVerba(
  pagamentos: EstadoPagamentoVerba[],
): PagamentoPayload[] {
  return pagamentos
    .filter((pg) => pg.data && pg.valor.trim())
    .map((pg) => ({
      data: pg.data,
      valor: pg.valor.trim(),
      descricao: (pg.descricao ?? "").trim(),
    }));
}

export function formatarDataBR(iso: string): string {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.split("-");
  if (!ano || !mes || !dia) return iso;
  return `${dia}/${mes}/${ano}`;
}

/** Aceita "85", "85,5", "0.85" — formatação da entrada, sem cálculo de negócio. */
export function paraNumero(texto: string): number {
  const t = texto.trim().replace("%", "").replace(/\s/g, "");
  const brasileiro = /^(\d+(?:\.\d{3})+),(\d+)$/.exec(t);
  if (brasileiro) {
    return Number(`${brasileiro[1].replace(/\./g, "")}.${brasileiro[2]}`);
  }
  return Number(t.replace(",", "."));
}

/** Percentual digitado em porcentagem (12) vira a fração do backend (0.12). */
export function fracaoDePercentual(texto: string): string {
  return String(Number((paraNumero(texto) / 100).toFixed(6)));
}

export function percentualValido(texto: string): boolean {
  if (!texto.trim()) return false;
  const n = paraNumero(texto);
  return Number.isFinite(n) && n > 0 && n <= 100;
}

/** Resumo visual no card (não vai ao backend como texto de valor). */
export function resumoVerba(
  verba: EstadoVerba,
  nomesPorId: Map<string, string>,
): string {
  if (verba.tipo === "percentual") {
    const base =
      nomesPorId.get(verba.baseVerbaId) || verba.baseVerbaId || "verba-base";
    const pct = verba.percentual.trim() ? `${verba.percentual.trim()}%` : "?%";
    return `${pct} de ${base}`;
  }
  const valor = verba.valor.trim() ? `R$ ${verba.valor.trim()}` : "R$ —";
  const partes = [valor];
  if (verba.correcaoAplicar && verba.correcaoInicio) {
    partes.push(`Correção desde ${formatarDataBR(verba.correcaoInicio)}`);
  }
  if (verba.jurosAplicar && verba.jurosInicio) {
    partes.push(`Juros desde ${formatarDataBR(verba.jurosInicio)}`);
  }
  if (verba.regimes.length > 0) {
    partes.push(
      verba.regimes.length === 1
        ? "1 regra de atualização"
        : `${verba.regimes.length} regras de atualização`,
    );
  }
  return partes.join(" · ");
}

/** Formata em real para leitura na tela (o backend arredonda o valor final). */
export function formatarMoedaBR(valor: number): string {
  const [inteiro, centavos] = Math.abs(valor).toFixed(2).split(".");
  const agrupado = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${valor < 0 ? "-" : ""}R$ ${agrupado},${centavos}`;
}

function projetarPrincipal(
  id: string,
  mapa: Map<string, EstadoVerba>,
  visto: Set<string>,
): number | null {
  const verba = mapa.get(id);
  if (!verba || visto.has(id)) return null;
  visto.add(id);
  if (verba.tipo === "valor") {
    if (!verba.valor.trim()) return null;
    const n = paraNumero(verba.valor);
    return Number.isFinite(n) ? n : null;
  }
  if (!verba.baseVerbaId || !verba.percentual.trim()) return null;
  const base = projetarPrincipal(verba.baseVerbaId, mapa, visto);
  const pct = paraNumero(verba.percentual);
  if (base === null || !Number.isFinite(pct)) return null;
  return (base * pct) / 100;
}

/** Valor que esta verba deve produzir, para mostrar imediatamente na lista. */
export function valorProjetado(
  verba: EstadoVerba,
  verbas: EstadoVerba[],
): number | null {
  return projetarPrincipal(verba.id, new Map(verbas.map((v) => [v.id, v])), new Set());
}

/** Ex.: "R$ 44.000,00 × 12% = R$ 5.280,00". */
export function contaDerivacao(
  verba: EstadoVerba,
  verbas: EstadoVerba[],
): string | null {
  if (verba.tipo !== "percentual") return null;
  const mapa = new Map(verbas.map((v) => [v.id, v]));
  const base = mapa.get(verba.baseVerbaId);
  if (!base || !verba.percentual.trim()) return null;
  const baseValor = projetarPrincipal(base.id, mapa, new Set());
  const total = projetarPrincipal(verba.id, mapa, new Set());
  if (baseValor === null || total === null) return null;
  return `${formatarMoedaBR(baseValor)} × ${verba.percentual.trim()}% = ${formatarMoedaBR(total)}`;
}

/** Ids das verbas que usam `id` como base de percentual. */
export function dependentesDe(id: string, verbas: EstadoVerba[]): EstadoVerba[] {
  return verbas.filter((v) => v.tipo === "percentual" && v.baseVerbaId === id);
}

export function podeRemoverVerba(
  id: string,
  verbas: EstadoVerba[],
): { ok: boolean; motivos: string[] } {
  const dependentes = dependentesDe(id, verbas);
  if (dependentes.length === 0) return { ok: true, motivos: [] };
  return {
    ok: false,
    motivos: dependentes.map(
      (d) => `“${d.nome || "Verba sem nome"}” depende desta verba`,
    ),
  };
}

/** Opções de base: outras verbas (por id interno), não o nome. */
export function opcoesDeBase(
  verbas: EstadoVerba[],
  idAtual: string,
): Array<{ id: string; rotulo: string }> {
  return verbas
    .filter((v) => v.id !== idAtual)
    .map((v, indice) => ({
      id: v.id,
      rotulo:
        v.nome.trim() ||
        `Verba ${verbas.findIndex((x) => x.id === v.id) + 1}` ||
        `#${indice + 1}`,
    }));
}

function jurosDoRegime(regime: EstadoRegime) {
  if (!regime.juros) return null;
  if (regime.juros === "fixa") {
    return {
      aplicar: true,
      modalidade: "fixa",
      taxa: "0.01",
      unidade: "mensal",
      base: "corrigido",
    };
  }
  return { aplicar: true, modalidade: regime.juros, base: "corrigido" };
}

export function montarRegimesPayload(
  regimes: EstadoRegime[],
): RegimeAtualizacaoPayload[] {
  return regimes.map((regime) => {
    const correcao = regime.correcao || null;
    const criterio =
      correcao === "selic" && regime.juros === "selic" ? "selic" : null;
    return {
      data_inicio: regime.dataInicio || null,
      data_fim: regime.dataFim || null,
      correcao,
      juros: jurosDoRegime(regime),
      criterio,
    };
  });
}

export function errosRegimes(regimes: EstadoRegime[]): string[] {
  const erros: string[] = [];
  regimes.forEach((regime, indice) => {
    const rotulo = `Regra de atualização ${indice + 1}`;
    if (indice > 0 && !regime.dataInicio) {
      erros.push(`${rotulo}: informe a data inicial.`);
    }
    if (
      regime.dataInicio &&
      regime.dataFim &&
      regime.dataInicio > regime.dataFim
    ) {
      erros.push(`${rotulo}: a data final é anterior à data inicial.`);
    }
    if (!regime.correcao && !regime.juros) {
      erros.push(`${rotulo}: informe a correção ou os juros do período.`);
    }
  });
  return erros;
}

/** data_base do lançamento vem da data da atualização ativa — sem data própria. */
function dataBaseDaVerba(
  verba: EstadoVerba,
  dataBaseCalculo: string,
): string {
  if (verba.correcaoAplicar && verba.correcaoInicio) return verba.correcaoInicio;
  if (verba.jurosAplicar && verba.jurosInicio) return verba.jurosInicio;
  return dataBaseCalculo;
}

/** Percentual da interface (12) vira fração do backend (0.12); valor fixo tem precedência. */
function percentualEncargo(percentual: string, valorFixo: string): string | null {
  if (valorFixo.trim()) return null;
  if (!percentual.trim()) return null;
  return fracaoDePercentual(percentual);
}

export function montarVerbaPayload(
  verba: EstadoVerba,
  dataBaseCalculo: string,
): VerbaPayload {
  const dataBase = dataBaseDaVerba(verba, dataBaseCalculo);
  const comum = {
    id: verba.id,
    nome: verba.nome.trim(),
    data_base: dataBase,
    // a interface grava a descrição em `nome`; envia como descricao também
    descricao: verba.descricao.trim() || verba.nome.trim(),
    entra_no_total: verba.entraNoTotal ?? null,
    correcao: {
      aplicar: verba.correcaoAplicar,
      indexador: verba.correcaoIndexador,
      termo_inicial: dataBase || null,
      termo_final: verba.correcaoFim || null,
    },
    juros: {
      aplicar: verba.jurosAplicar,
      // juros ativos usam sempre a Taxa Legal oficial já existente no projeto
      modalidade:
        verba.jurosAplicar && !verba.jurosModalidade
          ? "taxa_legal"
          : verba.jurosModalidade,
      taxa: verba.jurosModalidade === "fixa" ? verba.jurosTaxa.trim() || null : null,
      unidade: "mensal",
      base: verba.jurosBase,
      inicio: verba.jurosAplicar ? verba.jurosInicio || dataBase || null : null,
      fim: verba.jurosFim || null,
    },
    multa: {
      aplicar: verba.multaAplicar,
      percentual: percentualEncargo(verba.multaPercentual, verba.multaValorFixo),
      valor_fixo: verba.multaValorFixo.trim() || null,
      base: verba.multaBase,
    },
    honorarios: {
      aplicar: verba.honorariosAplicar,
      percentual: percentualEncargo(
        verba.honorariosPercentual,
        verba.honorariosValorFixo,
      ),
      valor_fixo: verba.honorariosValorFixo.trim() || null,
      base: verba.honorariosBase,
    },
    pagamentos: montarPagamentosVerba(verba.pagamentos),
    parcelas: [] as VerbaPayload["parcelas"],
    regimes: montarRegimesPayload(verba.regimes),
  };

  if (verba.tipo === "percentual") {
    return {
      ...comum,
      tipo: "percentual",
      valor: null,
      base_verba_id: verba.baseVerbaId,
      percentual: fracaoDePercentual(verba.percentual),
    };
  }

  return {
    ...comum,
    tipo: "valor",
    valor: verba.valor.trim(),
    base_verba_id: null,
    percentual: null,
  };
}

/** Multa/honorários aplicados exigem percentual válido OU valor fixo positivo. */
function errosEncargoVerba(verba: EstadoVerba, rotulo: string): string[] {
  const erros: string[] = [];
  if (verba.multaAplicar) {
    if (verba.multaPercentual.trim() && verba.multaValorFixo.trim()) {
      erros.push(
        `${rotulo}: informe o percentual ou o valor fixo da multa, não ambos.`,
      );
    } else if (verba.multaValorFixo.trim()) {
      const n = paraNumero(verba.multaValorFixo);
      if (!Number.isFinite(n) || n <= 0) {
        erros.push(`${rotulo}: valor fixo da multa inválido (ex.: 500,00).`);
      }
    } else if (!percentualValido(verba.multaPercentual)) {
      erros.push(
        `${rotulo}: informe o percentual da multa (ex.: 10) ou o valor fixo.`,
      );
    }
  }
  if (verba.honorariosAplicar) {
    if (verba.honorariosPercentual.trim() && verba.honorariosValorFixo.trim()) {
      erros.push(
        `${rotulo}: informe o percentual ou o valor fixo dos honorários, não ambos.`,
      );
    } else if (verba.honorariosValorFixo.trim()) {
      const n = paraNumero(verba.honorariosValorFixo);
      if (!Number.isFinite(n) || n <= 0) {
        erros.push(`${rotulo}: valor fixo dos honorários inválido (ex.: 500,00).`);
      }
    } else if (!percentualValido(verba.honorariosPercentual)) {
      erros.push(
        `${rotulo}: informe o percentual dos honorários (ex.: 10) ou o valor fixo.`,
      );
    }
  }
  return erros;
}

export function errosPagamentos(pagamentos: EstadoPagamentoVerba[]): string[] {
  const erros: string[] = [];
  pagamentos.forEach((pg, i) => {
    const rotulo = `Pagamento ${i + 1}`;
    if (!pg.data) erros.push(`${rotulo}: informe a data.`);
    if (!pg.valor.trim()) {
      erros.push(`${rotulo}: informe o valor.`);
    } else if (!Number.isFinite(paraNumero(pg.valor)) || paraNumero(pg.valor) <= 0) {
      erros.push(`${rotulo}: valor inválido (ex.: 500,00).`);
    }
  });
  return erros;
}

export function errosVerbas(
  verbas: EstadoVerba[],
  dataBaseCalculo: string,
): string[] {
  const erros: string[] = [];
  if (verbas.length === 0) erros.push("Inclua ao menos um valor.");
  verbas.forEach((verba, i) => {
    const rotulo = `Lançamento ${i + 1}`;
    if (!verba.nome.trim()) erros.push(`${rotulo}: informe a descrição.`);
    if (verba.correcaoAplicar && !verba.correcaoInicio) {
      erros.push(`${rotulo}: informe a data da correção.`);
    }
    if (verba.jurosAplicar && !verba.jurosInicio) {
      erros.push(`${rotulo}: informe a data de início dos juros.`);
    }
    if (verba.tipo === "valor") {
      if (!verba.valor.trim()) {
        erros.push(`${rotulo}: informe o valor.`);
      } else if (!Number.isFinite(paraNumero(verba.valor))) {
        erros.push(`${rotulo}: valor inválido (ex.: 44000,00).`);
      }
    } else {
      if (!verba.baseVerbaId) {
        erros.push(`${rotulo}: escolha sobre qual valor incidir.`);
      }
      if (!verba.percentual.trim()) {
        erros.push(`${rotulo}: informe o percentual (ex.: 12).`);
      } else if (!percentualValido(verba.percentual)) {
        erros.push(`${rotulo}: percentual inválido (use de 0,01 a 100).`);
      }
    }
    erros.push(...errosEncargoVerba(verba, rotulo));
    if (
      dataBaseCalculo &&
      verba.correcaoAplicar &&
      verba.correcaoInicio &&
      verba.correcaoInicio > dataBaseCalculo
    ) {
      erros.push(`${rotulo}: a data da correção é posterior à data final.`);
    }
    if (
      dataBaseCalculo &&
      verba.jurosAplicar &&
      verba.jurosInicio &&
      verba.jurosInicio > dataBaseCalculo
    ) {
      erros.push(`${rotulo}: a data dos juros é posterior à data final.`);
    }
    for (const erro of errosRegimes(verba.regimes)) {
      erros.push(`${rotulo}: ${erro}`);
    }
  });
  return erros;
}
