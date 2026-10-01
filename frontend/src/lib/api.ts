import type { CalculoResumo, HealthResponse, IndexersResponse } from "../types/api";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Falha na API (${response.status}) em ${path}`);
  }
  return (await response.json()) as T;
}

export const api = {
  baseUrl: BASE,

  health: () => getJson<HealthResponse>("/api/health"),

  listarCalculos: () => getJson<CalculoResumo[]>("/api/calculos"),

  listarIndexadores: () => getJson<IndexersResponse>("/api/indexers"),
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
