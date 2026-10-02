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
  if (!ano || !mes) return null;
  return `${mes}/${ano}`;
}
