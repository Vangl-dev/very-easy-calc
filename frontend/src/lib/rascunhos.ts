import type { EstadoIdentificacao } from "../features/novo-calculo/SecaoIdentificacao";
import type {
  EstadoPagamentoVerba,
  EstadoVerba,
} from "../features/civel/estadoVerba";

/** Estado do formulário Cível salvo para continuar depois (localStorage). */
export interface RascunhoCivel {
  id: string;
  titulo: string;
  atualizadoEm: string;
  estado: {
    identificacao: EstadoIdentificacao;
    dataBaseCalculo: string;
    indexador: string;
    verbas: EstadoVerba[];
    /** Opcionais — rascunhos antigos continuam válidos. */
    pagamentos?: EstadoPagamentoVerba[];
    modo?: "simples" | "detalhado";
    encargoConsolidado?: {
      ativo: boolean;
      tipo: "multa" | "honorarios";
      percentual: string;
      base: "principal" | "corrigido" | "com_juros";
    };
  };
}

const CHAVE = "very-easy-calc.rascunhos.civel";

function ler(): RascunhoCivel[] {
  try {
    const bruto = localStorage.getItem(CHAVE);
    if (!bruto) return [];
    const dados = JSON.parse(bruto);
    if (!Array.isArray(dados)) return [];
    return dados.filter(
      (item): item is RascunhoCivel =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as RascunhoCivel).id === "string",
    );
  } catch {
    return [];
  }
}

function gravar(lista: RascunhoCivel[]): void {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(lista));
  } catch {
    // armazenamento indisponível: rascunho apenas não persiste
  }
}

export function listarRascunhos(): RascunhoCivel[] {
  return ler().sort((a, b) => (a.atualizadoEm < b.atualizadoEm ? 1 : -1));
}

export function obterRascunho(id: string): RascunhoCivel | null {
  return ler().find((item) => item.id === id) ?? null;
}

export function salvarRascunho(
  estado: RascunhoCivel["estado"],
  id?: string | null,
): RascunhoCivel {
  const lista = ler();
  const existente = id ? lista.find((item) => item.id === id) : undefined;
  const rascunho: RascunhoCivel = {
    id: existente?.id ?? `rascunho-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    titulo:
      estado.identificacao.titulo.trim() ||
      estado.verbas.find((v) => v.nome.trim())?.nome.trim() ||
      "Cálculo sem título",
    atualizadoEm: new Date().toISOString(),
    estado,
  };
  const restantes = lista.filter((item) => item.id !== rascunho.id);
  gravar([...restantes, rascunho]);
  return rascunho;
}

export function excluirRascunho(id: string): void {
  gravar(ler().filter((item) => item.id !== id));
}
