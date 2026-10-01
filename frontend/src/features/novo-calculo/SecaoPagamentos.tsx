import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Form";
import { Tooltip } from "../../components/ui/Tooltip";
import type { PagamentoPayload } from "../../types/api";

export type EstadoPagamento = Omit<PagamentoPayload, "competencia"> & {
  id: string;
};

interface Props {
  pagamentos: EstadoPagamento[];
  onChange: (lista: EstadoPagamento[]) => void;
}

let contador = 0;

export function novoPagamento(): EstadoPagamento {
  contador += 1;
  return {
    id: `pg-${Date.now()}-${contador}`,
    data: "",
    valor: "",
    descricao: "",
  };
}

export function SecaoPagamentos({ pagamentos, onChange }: Props) {
  function atualizar(id: string, parcial: Partial<EstadoPagamento>) {
    onChange(
      pagamentos.map((item) => (item.id === id ? { ...item, ...parcial } : item)),
    );
  }

  function remover(id: string) {
    onChange(pagamentos.filter((item) => item.id !== id));
  }

  return (
    <section className="space-y-4" aria-labelledby="sec-pagamentos">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 id="sec-pagamentos" className="text-base font-semibold text-ink-900">
            4. Pagamentos / abatimentos
          </h2>
          <Tooltip text="Valores já recebidos que abatem o saldo. O backend soma os pagamentos e devolve o saldo por parcela — sem cálculo no React." />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onChange([...pagamentos, novoPagamento()])}
        >
          + Adicionar pagamento
        </Button>
      </div>

      {pagamentos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-ink-300 bg-white px-3 py-4 text-sm text-ink-500">
          Nenhum pagamento informado. O saldo permanecerá igual ao total calculado
          pelo backend.
        </p>
      ) : (
        <ul className="space-y-3">
          {pagamentos.map((item, indice) => (
            <li
              key={item.id}
              className="grid gap-3 rounded-xl border border-ink-200 bg-white p-4 md:grid-cols-[1fr_1fr_1.4fr_auto] md:items-end"
            >
              <Input
                id={`pg-data-${item.id}`}
                label={`Data do pagamento ${indice + 1}`}
                type="date"
                required
                value={item.data}
                onChange={(e) => atualizar(item.id, { data: e.target.value })}
              />
              <Input
                id={`pg-valor-${item.id}`}
                label="Valor pago"
                required
                inputMode="decimal"
                value={item.valor}
                onChange={(e) => atualizar(item.id, { valor: e.target.value })}
                placeholder="330,00"
              />
              <Input
                id={`pg-desc-${item.id}`}
                label="Descrição"
                value={item.descricao}
                onChange={(e) => atualizar(item.id, { descricao: e.target.value })}
                placeholder="Depósito / transferência"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => remover(item.id)}
                aria-label={`Remover pagamento ${indice + 1}`}
              >
                Remover
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
