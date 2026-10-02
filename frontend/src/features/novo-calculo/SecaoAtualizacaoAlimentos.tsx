import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import { Tooltip } from "../../components/ui/Tooltip";

export interface EstadoAtualizacaoAlimentos {
  correcaoAplicar: boolean;
  correcaoIndexador: string;
  jurosAplicar: boolean;
  jurosModalidade: string;
  jurosTaxa: string;
  jurosBase: string;
}

export function estadoAtualizacaoInicial(): EstadoAtualizacaoAlimentos {
  return {
    correcaoAplicar: false,
    correcaoIndexador: "tjsp_tabela_pratica",
    jurosAplicar: false,
    jurosModalidade: "fixa",
    jurosTaxa: "0.01",
    jurosBase: "corrigido",
  };
}

interface Props {
  valor: EstadoAtualizacaoAlimentos;
  onChange: (parcial: Partial<EstadoAtualizacaoAlimentos>) => void;
}

/** Correção monetária e juros por parcela de alimentos — o backend aplica. */
export function SecaoAtualizacaoAlimentos({ valor, onChange }: Props) {
  return (
    <section className="space-y-4" aria-labelledby="sec-atualizacao-alimentos">
      <div className="flex items-center gap-2">
        <h2
          id="sec-atualizacao-alimentos"
          className="text-base font-semibold text-ink-900"
        >
          4. Correção monetária e juros
        </h2>
        <Tooltip text="Aplicados pelo backend em cada competência: correção entre o vencimento da parcela e a data-base; juros desde o vencimento de cada débito. Pagamentos parciais não bloqueiam a atualização do saldo." />
      </div>

      <div className="space-y-3">
        <Switch
          id="alimentos-correcao-aplicar"
          checked={valor.correcaoAplicar}
          onChange={(correcaoAplicar) => onChange({ correcaoAplicar })}
          label="Aplicar correção monetária"
          description="Mês a mês pela Tabela Prática TJSP, do vencimento de cada competência até a data-base."
        />
        {valor.correcaoAplicar ? (
          <div className="rounded-xl border border-ink-200 bg-white p-4">
            <Select
              id="alimentos-correcao-indexador"
              label="Indexador de correção"
              value={valor.correcaoIndexador}
              onChange={(e) => onChange({ correcaoIndexador: e.target.value })}
              tooltip="Série oficial versionada no backend. O frontend não aplica fatores."
            >
              <option value="tjsp_tabela_pratica">
                Tabela Prática TJSP (correção monetária)
              </option>
            </Select>
          </div>
        ) : (
          <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
            Correção monetária <strong>não aplicada</strong> — os valores ficam no
            nominal de cada competência.
          </p>
        )}
      </div>

      <div className="space-y-3">
        <Switch
          id="alimentos-juros-aplicar"
          checked={valor.jurosAplicar}
          onChange={(jurosAplicar) => onChange({ jurosAplicar })}
          label="Aplicar juros"
          description="Desde a data de vencimento de cada débito até a data-base do cálculo."
        />
        {valor.jurosAplicar ? (
          <div className="grid gap-4 rounded-xl border border-ink-200 bg-white p-4 md:grid-cols-2">
            <Select
              id="alimentos-juros-modalidade"
              label="Modalidade de juros"
              value={valor.jurosModalidade}
              onChange={(e) => onChange({ jurosModalidade: e.target.value })}
              tooltip="Taxa fixa é o padrão de alimentos (ex.: 0,01 = 1% ao mês)."
            >
              <option value="fixa">Taxa fixa ao mês</option>
              <option value="taxa_legal">Taxa Legal (BCB SGS 29543)</option>
            </Select>
            {valor.jurosModalidade === "fixa" ? (
              <Input
                id="alimentos-juros-taxa"
                label="Taxa ao mês"
                inputMode="decimal"
                value={valor.jurosTaxa}
                onChange={(e) => onChange({ jurosTaxa: e.target.value })}
                placeholder="0.01"
                hint="0.01 = 1% ao mês (proporcional aos dias)"
              />
            ) : null}
            <Select
              id="alimentos-juros-base"
              label="Base de incidência"
              value={valor.jurosBase}
              onChange={(e) => onChange({ jurosBase: e.target.value })}
              className="md:col-span-2"
              tooltip="Sobre qual montante os juros incidem. Definido no backend."
            >
              <option value="corrigido">Valor corrigido</option>
              <option value="principal">Principal da competência</option>
              <option value="com_juros">Principal + correção + juros</option>
            </Select>
          </div>
        ) : (
          <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
            Juros <strong>não aplicados</strong> (parâmetro explícito do usuário).
          </p>
        )}
      </div>
    </section>
  );
}
