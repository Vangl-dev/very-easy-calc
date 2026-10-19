/** Formatação de competência para o formulário — sem cálculo de índices. */

export function fimDoMesISO(competencia: string): string | null {
  const texto = (competencia || "").trim();
  const iso = /^(\d{4})-(\d{1,2})$/.exec(texto);
  const br = /^(\d{1,2})\/(\d{4})$/.exec(texto);
  let ano: number;
  let mes: number;
  if (iso) {
    ano = Number(iso[1]);
    mes = Number(iso[2]);
  } else if (br) {
    mes = Number(br[1]);
    ano = Number(br[2]);
  } else {
    return null;
  }
  if (!ano || !mes || mes < 1 || mes > 12) return null;
  const ultimo = new Date(ano, mes, 0).getDate();
  return `${ano}-${String(mes).padStart(2, "0")}-${String(ultimo).padStart(2, "0")}`;
}

export function rotuloCompetencia(competencia: string): string {
  const texto = (competencia || "").trim();
  const iso = /^(\d{4})-(\d{1,2})$/.exec(texto);
  if (iso) return `${iso[2].padStart(2, "0")}/${iso[1]}`;
  return texto || "—";
}

export function competenciaValida(competencia: string): boolean {
  const texto = (competencia || "").trim();
  if (/^\d{4}-\d{1,2}$/.test(texto)) {
    const [, mes] = texto.split("-").map(Number);
    return mes >= 1 && mes <= 12;
  }
  if (/^\d{1,2}\/\d{4}$/.test(texto)) {
    const [mes] = texto.split("/").map(Number);
    return mes >= 1 && mes <= 12;
  }
  return false;
}

/** Converte data ISO (YYYY-MM-DD) em competência MM/AAAA — só formatação. */
export function competenciaDeData(iso: string): string | null {
  if (!iso || iso.length < 7) return null;
  const [ano, mes] = iso.split("-");
  return `${mes}/${ano}`;
}

const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** "2026-10-05" ou "2026-10" → "outubro/2026" — só formatação. */
export function rotuloCompetenciaExtenso(iso: string): string | null {
  const br = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec((iso || "").trim());
  const data = /^(\d{4})-(\d{2})/.exec((iso || "").trim());
  let ano: number;
  let mes: number;
  if (br) {
    mes = Number(br[2]);
    ano = Number(br[3]);
  } else if (data) {
    ano = Number(data[1]);
    mes = Number(data[2]);
  } else {
    return null;
  }
  if (!mes || mes < 1 || mes > 12 || !ano) return null;
  return `${MESES[mes - 1]}/${ano}`;
}
