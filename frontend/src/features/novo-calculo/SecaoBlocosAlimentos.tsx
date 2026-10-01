import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Form";
import { Tooltip } from "../../components/ui/Tooltip";
import { competenciaValida, rotuloCompetencia } from "../../lib/competencia";

export type TipoRegraAlimento = "salario_minimo" | "fixo";

export interface EstadoRegraAlimento {
  id: string;
  inicio: string;
  fim: string;
  tipo: TipoRegraAlimento;
  percentual: string;
  valor: string;
  descricao: string;
}

interface Props {
  regras: EstadoRegraAlimento[];
  onChange: (lista: EstadoRegraAlimento[]) => void;
  ate: string;
  onAteChange: (ate: string) => void;
  diaVencimento: string;
  onDiaVencimentoChange: (dia: string) => void;
}

let contador = 0;

export function novaRegraAlimento(
  parcial: Partial<EstadoRegraAlimento> = {},
): EstadoRegraAlimento {
  contador += 1;
  return {
    id: `regra-${Date.now()}-${contador}`,
    inicio: "",
    fim: "",
    tipo: "salario_minimo",
    percentual: "",
    valor: "",
    descricao: "",
    ...parcial,
  };
}

export function SecaoBlocosAlimentos({
  regras,
  onChange,
  ate,
  onAteChange,
  diaVencimento,
  onDiaVencimentoChange,
}: Props) {
  function atualizar(id: string, parcial: Partial<EstadoRegraAlimento>) {
    onChange(regras.map((r) => (r.id === id ? { ...r, ...parcial } : r)));
  }

  function remover(id: string) {
    onChange(regras.filter((r) => r.id !== id));
  }

  return (
    <section className="space-y-4" aria-labelledby="sec-blocos">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 id="sec-blocos" className="text-base font-semibold text-ink-900">
            2. Período e blocos de regras
          </h2>
          <Tooltip text="Cada competência é gerada no backend com a regra vigente naquele período. O salário mínimo é consultado por competência — sem usar o valor atual retroativamente." />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onChange([...regras, novaRegraAlimento()])}
        >
          + Adicionar bloco
        </Button>
      </div>

      <p className="text-sm text-ink-600">
        Exemplo representável: 01/2021–06/2023 → 30% do salário mínimo ·
        07/2023–12/2024 → 40% do salário mínimo · 01/2025 em diante → valor fixo.
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          id="alimentos-ate"
          label="Período final (até)"
          required
          value={ate}
          onChange={(e) => onAteChange(e.target.value)}
          placeholder="03/2025 ou 2025-03"
          hint="Última competência incluída no cálculo"
          tooltip="Formato MM/AAAA ou YYYY-MM. Cada competência até esta data gera uma parcela no backend."
        />
        <Input
          id="alimentos-dia-vencimento"
          label="Dia do vencimento"
          type="number"
          min={1}
          max={31}
          value={diaVencimento}
          onChange={(e) => onDiaVencimentoChange(e.target.value)}
          hint="Padrão: 10"
          tooltip="Dia de vencimento de cada parcela gerada. Se o dia não existir no mês, o backend usa o último dia do mês."
        />
      </div>

      {regras.length === 0 ? (
        <p className="rounded-lg border border-dashed border-ink-300 bg-white px-3 py-4 text-sm text-ink-500">
          Nenhum bloco. Adicione ao menos uma regra (percentual do salário mínimo
          ou valor fixo).
        </p>
      ) : (
        <ul className="space-y-3">
          {regras.map((regra, indice) => (
            <li
              key={regra.id}
              className="space-y-3 rounded-xl border border-ink-200 bg-white p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-ink-900">
                  Bloco {indice + 1}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => remover(regra.id)}
                  aria-label={`Remover bloco ${indice + 1}`}
                >
                  Remover
                </Button>
              </div>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <Input
                  id={`regra-inicio-${regra.id}`}
                  label="Início da vigência"
                  required
                  value={regra.inicio}
                  onChange={(e) => atualizar(regra.id, { inicio: e.target.value })}
                  placeholder="01/2021"
                  hint={regra.inicio ? rotuloCompetencia(regra.inicio) : "MM/AAAA"}
                  tooltip="Primeira competência em que este bloco vale. Formato MM/AAAA ou YYYY-MM."
                />
                <Input
                  id={`regra-fim-${regra.id}`}
                  label="Fim da vigência"
                  value={regra.fim}
                  onChange={(e) => atualizar(regra.id, { fim: e.target.value })}
                  placeholder="vazio = em diante"
                  hint={
                    regra.fim
                      ? rotuloCompetencia(regra.fim)
                      : "Deixe vazio para vigência aberta"
                  }
                  tooltip="Última competência deste bloco. Vazio = vale até o fim do período do cálculo (01/2025 em diante)."
                />
                <Select
                  id={`regra-tipo-${regra.id}`}
                  label="Tipo de regra"
                  value={regra.tipo}
                  onChange={(e) =>
                    atualizar(regra.id, {
                      tipo: e.target.value as TipoRegraAlimento,
                    })
                  }
                >
                  <option value="salario_minimo">% do salário mínimo</option>
                  <option value="fixo">Valor fixo</option>
                </Select>
                {regra.tipo === "salario_minimo" ? (
                  <Input
                    id={`regra-percentual-${regra.id}`}
                    label="Percentual"
                    required
                    inputMode="decimal"
                    value={regra.percentual}
                    onChange={(e) =>
                      atualizar(regra.id, { percentual: e.target.value })
                    }
                    placeholder="0.30"
                    hint="Ex.: 0.30 = 30% do salário mínimo da competência"
                    tooltip="O backend aplica este percentual sobre o salário mínimo vigente em cada competência do bloco."
                  />
                ) : (
                  <Input
                    id={`regra-valor-${regra.id}`}
                    label="Valor fixo"
                    required
                    inputMode="decimal"
                    value={regra.valor}
                    onChange={(e) => atualizar(regra.id, { valor: e.target.value })}
                    placeholder="800,00"
                    hint="Valor nominal por competência"
                    tooltip="Valor fixo enviado ao backend — sem conversão de salário mínimo."
                  />
                )}
                <Input
                  id={`regra-desc-${regra.id}`}
                  label="Descrição (opcional)"
                  value={regra.descricao}
                  onChange={(e) => atualizar(regra.id, { descricao: e.target.value })}
                  placeholder="Ex.: 30% do salário mínimo"
                  className="md:col-span-2 lg:col-span-4"
                  tooltip="Rótulo livre exibido na memória de cálculo."
                />
              </div>
              {!competenciaValida(regra.inicio) && regra.inicio ? (
                <p className="text-xs text-rose-600">
                  Início inválido — use MM/AAAA (ex.: 01/2021) ou YYYY-MM.
                </p>
              ) : null}
              {regra.fim && !competenciaValida(regra.fim) ? (
                <p className="text-xs text-rose-600">
                  Fim inválido — use MM/AAAA ou YYYY-MM.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
