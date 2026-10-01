import { Input } from "../../components/ui/Form";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";

export interface EstadoValorDatas {
  valorBase: string;
  dataBase: string;
  dataFinal: string;
}

interface Props {
  valor: EstadoValorDatas;
  onChange: (parcial: Partial<EstadoValorDatas>) => void;
  avisos: string[];
}

export function SecaoValorDatas({ valor, onChange, avisos }: Props) {
  return (
    <section className="space-y-4" aria-labelledby="sec-valor-datas">
      <div className="flex items-center gap-2">
        <h2 id="sec-valor-datas" className="text-base font-semibold text-ink-900">
          2. Valor-base e datas
        </h2>
        <Tooltip text="Informe o valor original e as datas escolhidas por você. O backend aplica correção/juros até a data final — o React não calcula nada." />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Input
          id="valor-base"
          label="Valor-base / principal"
          required
          inputMode="decimal"
          value={valor.valorBase}
          onChange={(e) => onChange({ valorBase: e.target.value })}
          placeholder="10000,00"
          hint="Aceita formato monetário (ex.: 10.000,00 ou 10000.00)"
          tooltip="Valor original da obrigação (causa, contrato, dano ou principal). Enviado como texto para o backend converter com precisão Decimal."
        />
        <Input
          id="data-base"
          label="Data-base do valor"
          required
          type="date"
          value={valor.dataBase}
          onChange={(e) => onChange({ dataBase: e.target.value })}
          hint="Data em que o valor-base foi fixado"
          tooltip="Data de vigência / vencimento do valor original. Pode ser no passado. Usada como termo inicial da correção (quando aplicável)."
        />
        <Input
          id="data-final"
          label="Data-final (atualização até)"
          required
          type="date"
          value={valor.dataFinal}
          onChange={(e) => onChange({ dataFinal: e.target.value })}
          hint="Você escolhe — não é sempre a data de hoje"
          tooltip="Data até a qual deseja atualizar o cálculo. Pode ser futura. Se a base oficial ainda não cobrir esse período, o backend retornará aviso de cobertura."
        />
      </div>

      <div className="grid gap-2 rounded-xl border border-ink-200 bg-white px-4 py-3 text-sm sm:grid-cols-2">
        <div>
          <span className="text-ink-500">Data-base selecionada:</span>{" "}
          <strong className="font-mono text-ink-900">
            {valor.dataBase || "—"}
          </strong>
        </div>
        <div>
          <span className="text-ink-500">Data-final selecionada:</span>{" "}
          <strong className="font-mono text-ink-900">
            {valor.dataFinal || "—"}
          </strong>
        </div>
      </div>

      {avisos.map((aviso) => (
        <Message key={aviso} tom="warning" title="Atenção às datas">
          {aviso}
        </Message>
      ))}
    </section>
  );
}
