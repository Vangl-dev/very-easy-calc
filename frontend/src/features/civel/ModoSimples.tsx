import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/Button";
import {
  formatarDataBR,
  formatarMoedaBR,
  paraNumero,
  resumoVerba,
  valorProjetado,
  type EstadoVerba,
} from "./estadoVerba";

const COLUNAS_SIMPLES =
  "gap-x-4 gap-y-3 lg:grid-cols-[minmax(0,1fr)_9rem_10rem_7.5rem] lg:gap-x-3 lg:gap-y-0 lg:items-end";

interface ModoSimplesProps {
  verbas: EstadoVerba[];
  onAtualizar: (id: string, parcial: Partial<EstadoVerba>) => void;
  onAdicionar: () => void;
  onRemover: (id: string) => boolean;
  onEditarDetalhado: () => void;
}

/**
 * Modo simples: uma linha por valor (descrição, data, valor), como a
 * planilha Easy Calc. A data da linha alimenta correção e juros.
 */
export function ModoSimples({
  verbas,
  onAtualizar,
  onAdicionar,
  onRemover,
  onEditarDetalhado,
}: ModoSimplesProps) {
  const [editando, setEditando] = useState<Set<string>>(() => new Set());
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const conhecidos = useRef<Set<string>>(new Set());

  useEffect(() => {
    const novos = verbas.filter((v) => !conhecidos.current.has(v.id));
    if (novos.length === 0) return;
    setEditando((prev) => {
      const atualizado = new Set(prev);
      novos.forEach((v) => atualizado.add(v.id));
      return atualizado;
    });
    novos.forEach((v) => conhecidos.current.add(v.id));
  }, [verbas]);

  function abrirEdicao(id: string) {
    setConfirmando(null);
    setEditando((prev) => new Set(prev).add(id));
  }

  function fecharEdicao(id: string) {
    setEditando((prev) => {
      const atualizado = new Set(prev);
      atualizado.delete(id);
      return atualizado;
    });
  }

  function tentarRemover(verba: EstadoVerba) {
    if (confirmando !== verba.id) {
      setConfirmando(verba.id);
      return;
    }
    setConfirmando(null);
    setEditando((prev) => {
      const atualizado = new Set(prev);
      atualizado.delete(verba.id);
      return atualizado;
    });
    onRemover(verba.id);
  }

  function dataDaLinha(verba: EstadoVerba): string {
    return verba.correcaoInicio || verba.jurosInicio || "";
  }

  return (
    <>
      <div className="mt-5 border border-line bg-panel">
        <div
          className={`hidden border-b border-line bg-ink-50 px-4 pb-2 pt-2.5 text-[11px] font-semibold uppercase tracking-legal text-ink-500 lg:grid ${COLUNAS_SIMPLES}`}
        >
          <span>Descrição</span>
          <span>Data</span>
          <span>Valor</span>
          <span className="text-right">Ações</span>
        </div>
        <ul>
          {verbas.map((verba, indice) => {
            const derivada = verba.tipo === "percentual";
            const emEdicao = editando.has(verba.id);
            const projetado = valorProjetado(verba, verbas);
            const nomes = new Map(
              verbas.map((v, i) => [v.id, v.nome.trim() || `Lançamento ${i + 1}`]),
            );

            if (derivada) {
              return (
                <li
                  key={verba.id}
                  className="border-b border-line px-4 py-3 last:border-b-0"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <p className="text-[14px] font-medium text-ink-900">
                          {verba.nome || `Lançamento ${indice + 1}`}
                        </p>
                        <span className="rounded border border-line bg-ink-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-legal text-ink-600">
                          Configuração avançada
                        </span>
                      </div>
                      <p className="mt-0.5 text-[13px] text-ink-600">
                        {resumoVerba(verba, nomes)}
                        {projetado !== null
                          ? ` · ${formatarMoedaBR(projetado)}`
                          : ""}
                      </p>
                      <p className="mt-0.5 text-[11px] text-ink-500">
                        Edite no modo detalhado.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => onEditarDetalhado()}
                        aria-label={`Editar no modo detalhado o lançamento ${indice + 1}`}
                      >
                        Editar
                      </Button>
                      {confirmando === verba.id ? (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Confirmar remoção do lançamento ${indice + 1}`}
                        >
                          Confirmar
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Remover lançamento ${indice + 1}`}
                        >
                          Remover
                        </Button>
                      )}
                    </div>
                  </div>
                </li>
              );
            }

            return (
              <li
                key={verba.id}
                className="border-b border-line px-4 py-3 transition-colors last:border-b-0 hover:bg-ink-50/40"
              >
                {emEdicao ? (
                  <div className={`grid grid-cols-2 ${COLUNAS_SIMPLES}`}>
                    <div className="col-span-2 space-y-1 lg:col-span-1 lg:space-y-0">
                      <label
                        htmlFor={`simples-descricao-${verba.id}`}
                        className="label-legal lg:sr-only"
                      >
                        Descrição
                      </label>
                      <input
                        id={`simples-descricao-${verba.id}`}
                        type="text"
                        required
                        className="field-line"
                        placeholder="Ex.: Valor da causa"
                        value={verba.nome}
                        onChange={(e) =>
                          onAtualizar(verba.id, {
                            nome: e.target.value,
                            descricao: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-1 lg:space-y-0">
                      <label
                        htmlFor={`simples-data-${verba.id}`}
                        className="label-legal lg:sr-only"
                      >
                        Data
                      </label>
                      <input
                        id={`simples-data-${verba.id}`}
                        type="date"
                        required
                        className="field-line"
                        aria-label={`Data do lançamento ${indice + 1}`}
                        value={dataDaLinha(verba)}
                        onChange={(e) =>
                          onAtualizar(verba.id, {
                            correcaoInicio: e.target.value,
                            jurosInicio: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-1 lg:space-y-0">
                      <label
                        htmlFor={`simples-valor-${verba.id}`}
                        className="label-legal lg:sr-only"
                      >
                        Valor
                      </label>
                      <input
                        id={`simples-valor-${verba.id}`}
                        type="text"
                        required
                        inputMode="decimal"
                        className="field-line"
                        placeholder="44000,00"
                        value={verba.valor}
                        onChange={(e) =>
                          onAtualizar(verba.id, { valor: e.target.value })
                        }
                      />
                    </div>
                    <div className="col-span-2 flex items-center justify-end gap-2 lg:col-span-1">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => fecharEdicao(verba.id)}
                        aria-label={`Concluir edição do lançamento ${indice + 1}`}
                      >
                        Concluir
                      </Button>
                      {confirmando === verba.id ? (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Confirmar remoção do lançamento ${indice + 1}`}
                        >
                          Confirmar
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Remover lançamento ${indice + 1}`}
                        >
                          Remover
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className={`grid ${COLUNAS_SIMPLES}`}>
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-medium text-ink-900">
                        {verba.nome || `Lançamento ${indice + 1}`}
                      </p>
                    </div>
                    <div>
                      <p className="font-mono text-[13px] text-ink-700">
                        {formatarDataBR(dataDaLinha(verba))}
                      </p>
                    </div>
                    <div>
                      <p className="font-mono text-[14px] tabular-nums text-ink-900">
                        {verba.valor.trim() && Number.isFinite(paraNumero(verba.valor))
                          ? formatarMoedaBR(paraNumero(verba.valor))
                          : "R$ —"}
                      </p>
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => abrirEdicao(verba.id)}
                        aria-label={`Editar lançamento ${indice + 1}`}
                      >
                        Editar
                      </Button>
                      {confirmando === verba.id ? (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Confirmar remoção do lançamento ${indice + 1}`}
                        >
                          Confirmar
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => tentarRemover(verba)}
                          aria-label={`Remover lançamento ${indice + 1}`}
                        >
                          Remover
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="mt-4">
        <Button type="button" variant="secondary" size="sm" onClick={onAdicionar}>
          + Adicionar valor
        </Button>
      </div>
    </>
  );
}
