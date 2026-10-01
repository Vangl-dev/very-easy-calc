import type {
  CalculoCriado,
  CalculoRequestPayload,
  CalculoResumo,
  CoberturaEfetiva,
  ErroApiBody,
  HealthResponse,
  IndexersResponse,
} from "../types/api";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ErroApi extends Error {
  readonly status: number;
  readonly corpo: ErroApiBody;
  readonly coberturaInsuficiente: boolean;

  constructor(status: number, corpo: ErroApiBody) {
    const mensagem =
      corpo.mensagem ||
      corpo.detail?.mensagem ||
      corpo.detail?.erro ||
      `Falha na API (${status})`;
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.corpo = corpo;
    this.coberturaInsuficiente =
      corpo.erro === "cobertura_insuficiente" ||
      corpo.detail?.erro === "cobertura_insuficiente";
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let corpo: ErroApiBody = {};
    try {
      corpo = (await response.json()) as ErroApiBody;
    } catch {
      corpo = { mensagem: `Falha na API (${response.status}) em ${path}` };
    }
    throw new ErroApi(response.status, corpo);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let corpo: ErroApiBody = {};
    try {
      corpo = (await response.json()) as ErroApiBody;
    } catch {
      corpo = { mensagem: `Falha na API (${response.status}) em ${path}` };
    }
    throw new ErroApi(response.status, corpo);
  }
  return (await response.json()) as T;
}

export const api = {
  baseUrl: BASE,

  health: () => getJson<HealthResponse>("/api/health"),

  listarCalculos: () => getJson<CalculoResumo[]>("/api/calculos"),

  listarIndexadores: () => getJson<IndexersResponse>("/api/indexers"),

  coberturaIndexador: (key: string) =>
    getJson<CoberturaEfetiva>(`/api/indexers/${encodeURIComponent(key)}/cobertura`),

  criarCalculo: (payload: CalculoRequestPayload) =>
    postJson<CalculoCriado>("/api/calculos", payload),

  obterCalculo: (codigo: string) =>
    getJson<CalculoCriado>(`/api/calculos/${encodeURIComponent(codigo)}`),
};

export function formatarDataHora(iso: string): string {
  if (!iso) return "—";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return iso;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(data);
}

export function rotuloTipoCalculo(tipo: string): string {
  switch (tipo) {
    case "alimentos":
      return "Alimentos";
    case "parcelas":
      return "Parcelas / Cível";
    case "atualizacao":
      return "Atualização monetária";
    default:
      return tipo || "Cálculo";
  }
}

/** Converte data ISO (YYYY-MM-DD) em rotulo MM/YYYY — só formatação, sem cálculo. */
export function competenciaDeData(iso: string): string | null {
  if (!iso || iso.length < 7) return null;
  const [ano, mes] = iso.split("-");
  if (!ano || !mes) return null;
  return `${mes}/${ano}`;
}

export function mensagemErroAmigavel(erro: unknown): string {
  if (erro instanceof ErroApi) {
    if (erro.corpo.erro === "cobertura_insuficiente" || erro.coberturaInsuficiente) {
      const base = erro.corpo.indexador ?? "a base indexadora";
      const cob = erro.corpo.cobertura;
      const periodo = cob?.inicio && cob?.fim ? ` (cobertura ${cob.inicio} a ${cob.fim})` : "";
      return (
        `A base ${base} ainda não cobre o período informado${periodo}. ` +
        "Ajuste a data final, cadastre um valor manual em Bases/Indexadores ou desative a correção monetária."
      );
    }
    return erro.message;
  }
  if (erro instanceof Error) return erro.message;
  return "Ocorreu um erro inesperado.";
}
