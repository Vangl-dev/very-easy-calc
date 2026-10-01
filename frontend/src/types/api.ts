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

export type CapacidadeUI =
  | "civel"
  | "alimentos"
  | "atualizacao"
  | "memoria"
  | "relatorios";
