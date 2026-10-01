import type { ReactNode } from "react";

export interface Columna<T> {
  key: string;
  header: string;
  render: (linha: T) => ReactNode;
  className?: string;
}

interface TableProps<T> {
  colunas: Columna<T>[];
  linhas: T[];
  chaveLinha: (linha: T) => string;
  vazio?: ReactNode;
  caption?: string;
}

export function Table<T>({
  colunas,
  linhas,
  chaveLinha,
  vazio,
  caption,
}: TableProps<T>) {
  return (
    <div className="overflow-x-auto rounded-xl border border-ink-200">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-600">
          <tr>
            {colunas.map((coluna) => (
              <th
                key={coluna.key}
                scope="col"
                className={`border-b border-ink-200 px-4 py-3 font-semibold ${coluna.className ?? ""}`}
              >
                {coluna.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100 bg-white">
          {linhas.length === 0 ? (
            <tr>
              <td
                colSpan={colunas.length}
                className="px-4 py-8 text-center text-sm text-ink-500"
              >
                {vazio ?? "Nenhum registro."}
              </td>
            </tr>
          ) : (
            linhas.map((linha) => (
              <tr key={chaveLinha(linha)} className="hover:bg-ink-50/70">
                {colunas.map((coluna) => (
                  <td
                    key={coluna.key}
                    className={`px-4 py-3 align-middle text-ink-800 ${coluna.className ?? ""}`}
                  >
                    {coluna.render(linha)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
