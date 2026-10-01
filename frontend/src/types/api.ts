export type TipoCalculo = "alimentos" | "parcelas" | "atualizacao" | string;

export interface CalculoResumo {
  codigo: string;
  tipo: TipoCalculo;
  titulo: string;
  processo: string;
  parte: string;
  app_version: string;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

export interface IndexerMeta {
  key: string;
  name: string;
  kind: string;
  source: string;
  source_url: string;
  version: string;
  updated_at: string;
  cobertura: {
    inicio: string;
    fim: string;
    total: number;
  };
  total_records: number;
  note: string;
  registrada?: boolean;
  unidade?: string;
}

export interface IndexersResponse {
  app_version: string;
  indexers: IndexerMeta[];
}

export interface CoberturaEfetiva {
  key: string;
  oficial: {
    inicio: string;
    fim: string;
    inicio_rotulo: string;
    fim_rotulo: string;
    total: number;
    version: string;
    name: string;
    kind: string;
    source: string;
  };
  manual: Array<{
    key: string;
    competencia: string;
    competencia_rotulo: string;
    valor: string;
    fonte: string;
    observacao: string;
  }>;
  cobertura_efetiva: {
    inicio: string;
    fim: string;
    inicio_rotulo: string;
    fim_rotulo: string;
    total: number;
    inclui_manual: boolean;
  };
  nota: string;
}

export interface PagamentoPayload {
  data: string;
  valor: string;
  descricao?: string;
  competencia?: string | null;
}

export interface ConfigCorrecaoPayload {
  aplicar: boolean;
  indexador?: string;
  termo_inicial?: string | null;
  termo_final?: string | null;
}

export interface ConfigJurosPayload {
  aplicar: boolean;
  modalidade?: string;
  taxa?: string | null;
  unidade?: string;
  base?: string;
}

export interface ConfigEncargoPayload {
  aplicar: boolean;
  percentual?: string | null;
  valor_fixo?: string | null;
  base?: string;
}

export interface ParcelaManualPayload {
  numero: number;
  vencimento: string;
  principal: string;
  descricao?: string;
  pagamentos?: PagamentoPayload[];
  correcao?: ConfigCorrecaoPayload | null;
  juros?: ConfigJurosPayload | null;
}

export interface RegraAlimentoPayload {
  inicio: string;
  fim?: string | null;
  tipo: "salario_minimo" | "fixo";
  percentual?: string | null;
  valor?: string | null;
  descricao?: string;
}

export interface AlimentosPayload {
  regras: RegraAlimentoPayload[];
  ate: string;
  dia_vencimento?: number;
}

export interface ValorBasePayload {
  valor: string;
  data_base: string;
  descricao?: string;
}

export interface CalculoCivelPayload {
  tipo: "parcelas";
  titulo: string;
  processo: string;
  parte: string;
  data_base: string;
  parcelas: ParcelaManualPayload[];
  correcao: ConfigCorrecaoPayload;
  juros: ConfigJurosPayload;
  multa: ConfigEncargoPayload;
  honorarios: ConfigEncargoPayload;
  pagamentos?: PagamentoPayload[];
}

export interface CalculoAlimentosPayload {
  tipo: "alimentos";
  titulo: string;
  processo: string;
  parte: string;
  data_base: string;
  alimentos: AlimentosPayload;
  correcao?: ConfigCorrecaoPayload | null;
  juros?: ConfigJurosPayload | null;
  multa?: ConfigEncargoPayload | null;
  honorarios?: ConfigEncargoPayload | null;
  pagamentos?: PagamentoPayload[];
}

export interface CalculoAtualizacaoPayload {
  tipo: "atualizacao";
  titulo: string;
  processo: string;
  parte: string;
  data_base: string;
  data_final?: string | null;
  valor_base: ValorBasePayload;
  correcao?: ConfigCorrecaoPayload | null;
  juros?: ConfigJurosPayload | null;
  multa?: ConfigEncargoPayload | null;
  honorarios?: ConfigEncargoPayload | null;
}

export type CalculoRequestPayload =
  | CalculoCivelPayload
  | CalculoAlimentosPayload
  | CalculoAtualizacaoPayload;

export interface ErroApiBody {
  erro?: string;
  mensagem?: string;
  detail?: {
    erro?: string;
    mensagem?: string;
    [chave: string]: unknown;
  };
  indexador?: string;
  competencia_solicitada?: string;
  cobertura?: {
    inicio?: string;
    fim?: string;
  };
}

export interface CalculoCriado extends CalculoResumo {
  resumo?: {
    qtd_parcelas: number;
    principal: string;
    total: string;
    saldo: string;
    pagamentos: string;
    correcao?: string;
    juros?: string;
    multa?: string;
    honorarios?: string;
  };
  parcelas?: Array<Record<string, unknown>>;
  bases?: Array<Record<string, unknown>>;
  memoria?: Record<string, unknown>;
  created_at: string;
  data_base?: string;
}

export type CapacidadeUI =
  | "civel"
  | "alimentos"
  | "atualizacao"
  | "memoria"
  | "relatorios";
