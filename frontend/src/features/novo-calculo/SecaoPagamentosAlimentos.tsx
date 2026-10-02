import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Form";
import { Tooltip } from "../../components/ui/Tooltip";
import { competenciaValida, rotuloCompetencia } from "../../lib/competencia";

export interface EstadoPagamentoAlimento {
  id: string;
  competencia: string;
  data: string;
  valor: string;
  descricao: string;
}

interface Props {
  pagamentos: EstadoPagamentoAlimento[];
  onChange: (lista: EstadoPagamentoAlimento[]) => void;
}

let contador = 0;

export function novoPagamentoAlimento(): EstadoPagamentoAlimento {
  contador += 1;
  return {
    id: `pga-${Date.now()}-${contador}`,
    competencia: "",
    data: "",
    valor: "",
    descricao: "",
  };
}

export function SecaoPagamentosAlimentos({ pagamentos, onChange }: Props) {
  function atualizar(id: string, parcial: Partial<EstadoPagamentoAlimento>) {
    onChange(
      pagamentos.map((item) => (item.id === id ? { ...item, ...parcial } : item)),
    );
  }

  function remover(id: string) {
    onChange(pagamentos.filter((item) => item.id !== id));
  }

  return (
    <section className="space-y-4" aria-labelledby="sec-pag-alimentos">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2
            id="sec-pag-alimentos"
            className="text-base font-semibold text-ink-900"
          >
            5. Pagamentos por competência
          </h2>
          <Tooltip text="Informe a competência de cada pagamento (ex.: 01/2021). O backend abate o valor na parcela daquela competência. Cada competência mantém seu próprio principal." />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onChange([...pagamentos, novoPagamentoAlimento()])}
        >
          + Adicionar pagamento
        </Button>
      </div>

      {pagamentos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-ink-300 bg-white px-3 py-4 text-sm text-ink-500">
          Nenhum pagamento por competência. O backend gerará as parcelas com saldo
          integral.
        </p>
      ) : (
        <ul className="space-y-3">
          {pagamentos.map((item, indice) => (
            <li
              key={item.id}
              className="grid gap-3 rounded-xl border border-ink-200 bg-white p-4 md:grid-cols-2 lg:grid-cols-5 lg:items-end"
            >
              <Input
                id={`pga-comp-${item.id}`}
                label={`Competência ${indice + 1}`}
                required
                value={item.competencia}
                onChange={(e) =>
                  atualizar(item.id, { competencia: e.target.value })
                }
                placeholder="01/2021"
                hint={
                  item.competencia && competenciaValida(item.competencia)
                    ? rotuloCompetencia(item.competencia)
                    : "MM/AAAA"
                }
                tooltip="Competência da parcela que recebe o abatimento. Ex.: 01/2021 ou 2021-01."
              />
              <Input
                id={`pga-data-${item.id}`}
                label="Data do pagamento"
                type="date"
                required
                value={item.data}
                onChange={(e) => atualizar(item.id, { data: e.target.value })}
              />
              <Input
                id={`pga-valor-${item.id}`}
                label="Valor"
                required
                inputMode="decimal"
                value={item.valor}
                onChange={(e) => atualizar(item.id, { valor: e.target.value })}
                placeholder="100,00"
              />
              <Input
                id={`pga-desc-${item.id}`}
                label="Descrição"
                value={item.descricao}
                onChange={(e) => atualizar(item.id, { descricao: e.target.value })}
                placeholder="Depósito"
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
