import type { PagamentoPayload } from "../../types/api";

export interface EstadoPagamentoVerba {
  id: string;
  data: string;
  valor: string;
  descricao: string;
}

export interface EstadoVerba {
  id: string;
  nome: string;
  descricao: string;
  valor: string;
  dataBase: string;
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
  detalhesAbertos: boolean;
}

let contadorPagamentos = 0;

export function novaVerba(parcial: Partial<EstadoVerba> = {}): EstadoVerba {
  return {
    id: `verba-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    nome: "",
    descricao: "",
    valor: "",
    dataBase: "",
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
    detalhesAbertos: false,
    ...parcial,
  };
}

export function novoPagamentoVerba(): EstadoPagamentoVerba {
  contadorPagamentos += 1;
  return {
    id: `pgv-${Date.now()}-${contadorPagamentos}`,
    data: "",
    valor: "",
    descricao: "",
  };
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
