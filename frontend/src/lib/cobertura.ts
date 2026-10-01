import type { CoberturaEfetiva, ErroApiBody } from "../types/api";

export function extrairCobertura(erro: ErroApiBody): {
  indexador?: string;
  inicio?: string;
  fim?: string;
} {
  return {
    indexador: erro.indexador,
    inicio: erro.cobertura?.inicio,
    fim: erro.cobertura?.fim,
  };
}

export function coberturaInsuficientePara(
  cobertura: CoberturaEfetiva | null,
  competenciaISO: string,
): boolean {
  if (!cobertura?.cobertura_efetiva?.fim) return false;
  const [anoFim, mesFim] = cobertura.cobertura_efetiva.fim.split("-").map(Number);
  const [anoSol, mesSol] = competenciaISO.split("-").map(Number);
  if (!anoFim || !mesFim || !anoSol || !mesSol) return false;
  if (anoSol > anoFim) return true;
  if (anoSol === anoFim && mesSol > mesFim) return true;
  return false;
}
