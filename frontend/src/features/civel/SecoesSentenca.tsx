import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import {
  TAXAS_JUROS,
  type Conferencia,
  type EstadoEncargosSentenca,
  type EstadoJurosDesde,
  type TaxaJuros,
} from "./criteriosSentenca";

interface CamposJurosProps {
  desde: EstadoJurosDesde;
  taxa: TaxaJuros;
  base: string;
  onDesde: (parcial: Partial<EstadoJurosDesde>) => void;
  onTaxa: (taxa: TaxaJuros) => void;
  onBase: (base: string) => void;
}

/** Juros escritos como na decisão: desde quando, qual taxa e sobre qual base. */
export function CamposJuros({ desde, taxa, base, onDesde, onTaxa, onBase }: CamposJurosProps) {
  return (
    <div className="rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3">
      <div className="grid gap-3 md:grid-cols-3">
        <Select
          id="enc-juros-desde"
          label="Juros desde"
          value={desde.termo}
          onChange={(e) => onDesde({ termo: e.target.value as EstadoJurosDesde["termo"] })}
        >
          <option value="cada_valor">A data de cada valor</option>
          <option value="data_unica">Uma data para todos os valores</option>
        </Select>
        {desde.termo === "data_unica" ? (
          <Input
            id="enc-juros-data"
            label="Data de início dos juros"
            type="date"
            required
            value={desde.data}
            onChange={(e) => onDesde({ data: e.target.value })}
            hint="Ex.: citação ou trânsito em julgado, conforme a decisão."
          />
        ) : null}
        <Select
          id="enc-juros-taxa"
          label="Taxa de juros"
          value={taxa}
          onChange={(e) => onTaxa(e.target.value as TaxaJuros)}
        >
          {TAXAS_JUROS.map((op) => (
            <option key={op.valor} value={op.valor}>
              {op.rotulo}
            </option>
          ))}
        </Select>
        <Select
          id="enc-juros-base"
          label="Juros sobre"
          value={base}
          onChange={(e) => onBase(e.target.value)}
        >
          <option value="corrigido">Valor corrigido</option>
          <option value="principal">Valor original</option>
        </Select>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-500">
        {taxa === "legal"
          ? "Taxa legal de cada época: 6% ao ano até 11/01/2003, 12% ao ano até 29/08/2024 e, a partir de 30/08/2024, a Taxa Legal da Lei 14.905/24 (Selic menos IPCA, publicada pelo Banco Central)."
          : "1% ao mês durante todo o período, proporcional aos dias, como fixado na decisão — inclusive depois de 30/08/2024."}
      </p>
    </div>
  );
}

interface SecaoEncargosSentencaProps {
  valor: EstadoEncargosSentenca;
  onChange: (valor: EstadoEncargosSentenca) => void;
  disabled?: boolean;
}

/** Honorários fixados na sentença e encargos do cumprimento (art. 523, §1º). */
export function SecaoEncargosSentenca({ valor, onChange, disabled }: SecaoEncargosSentencaProps) {
  const { honorarios, art523 } = valor;
  const honorariosParcial = (parcial: Partial<EstadoEncargosSentenca["honorarios"]>) =>
    onChange({ ...valor, honorarios: { ...honorarios, ...parcial } });
  const art523Parcial = (parcial: Partial<EstadoEncargosSentenca["art523"]>) =>
    onChange({ ...valor, art523: { ...art523, ...parcial } });

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="space-y-3">
        <Switch
          id="enc-honorarios-sentenca"
          label="Honorários da sentença"
          description="Os honorários de sucumbência fixados na decisão, calculados uma vez sobre o total."
          checked={honorarios.ativo}
          onChange={(ativo) => honorariosParcial({ ativo })}
          disabled={disabled}
        />
        {honorarios.ativo ? (
          <div className="grid gap-3 rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3 sm:grid-cols-2">
            <Input
              id="enc-honorarios-sentenca-pct"
              label="Percentual (%)"
              inputMode="decimal"
              required
              value={honorarios.percentual}
              onChange={(e) => honorariosParcial({ percentual: e.target.value })}
            />
            <Select
              id="enc-honorarios-sentenca-base"
              label="Calcular sobre"
              value={honorarios.base}
              onChange={(e) =>
                honorariosParcial({ base: e.target.value as EstadoEncargosSentenca["honorarios"]["base"] })
              }
            >
              <option value="com_juros">Débito atualizado (corrigido + juros)</option>
              <option value="corrigido">Valor corrigido, sem juros</option>
            </Select>
          </div>
        ) : null}
      </div>
      <div className="space-y-3">
        <Switch
          id="enc-art523"
          label="Cumprimento de sentença (art. 523, §1º)"
          description="Multa e honorários de 10% quando a parte, intimada, não paga em 15 dias."
          checked={art523.ativo}
          onChange={(ativo) => art523Parcial({ ativo })}
          disabled={disabled}
        />
        {art523.ativo ? (
          <div className="space-y-3 rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                id="enc-art523-multa"
                label="Multa do art. 523 (%)"
                inputMode="decimal"
                value={art523.multa}
                onChange={(e) => art523Parcial({ multa: e.target.value })}
              />
              <Input
                id="enc-art523-honorarios"
                label="Honorários do art. 523 (%)"
                inputMode="decimal"
                value={art523.honorarios}
                onChange={(e) => art523Parcial({ honorarios: e.target.value })}
              />
            </div>
            <Select
              id="enc-art523-base"
              label="Calcular sobre"
              value={art523.base}
              onChange={(e) =>
                art523Parcial({ base: e.target.value as EstadoEncargosSentenca["art523"]["base"] })
              }
            >
              <option value="com_juros">Débito atualizado (corrigido + juros)</option>
              <option value="corrigido">Valor corrigido, sem juros</option>
            </Select>
            {honorarios.ativo ? (
              <label className="flex cursor-pointer items-start gap-2 text-[13px] text-ink-700">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-brand-700"
                  checked={art523.incluirHonorariosSentenca}
                  onChange={(e) => art523Parcial({ incluirHonorariosSentenca: e.target.checked })}
                />
                Incluir os honorários da sentença na base da multa e dos honorários do art. 523
              </label>
            ) : null}
            <p className="text-[12px] leading-relaxed text-ink-500">
              O usual é o débito atualizado (valor corrigido + juros). Os
              honorários do art. 523 não incidem sobre a multa. Deixe um campo em
              branco para não aplicar.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

interface PainelConferenciaProps {
  conferencia: Conferencia;
  dataFinal: string;
  enviando: boolean;
  onConfirmar: () => void;
  onVoltar: () => void;
}

/** Descrição em português do que será calculado, para conferir com a decisão. */
export function PainelConferencia({
  conferencia,
  dataFinal,
  enviando,
  onConfirmar,
  onVoltar,
}: PainelConferenciaProps) {
  return (
    <div
      className="border-t border-line bg-ink-50 px-6 py-5 lg:px-8"
      role="alertdialog"
      aria-labelledby="conferencia-titulo"
    >
      <p id="conferencia-titulo" className="font-semibold text-ink-950">
        Confira com a decisão antes de gerar
      </p>
      <p className="mt-1 text-sm text-ink-600">
        É isto que será calculado, atualizado até {dataFinal}. Leia frase por frase.
      </p>

      <h3 className="mt-4 text-[11px] font-semibold uppercase tracking-legal text-ink-500">Valores</h3>
      <ul className="mt-1 space-y-1.5 text-sm text-ink-900">
        {conferencia.linhas.map((linha) => (
          <li key={linha}>{linha}</li>
        ))}
      </ul>

      <h3 className="mt-4 text-[11px] font-semibold uppercase tracking-legal text-ink-500">
        Honorários e multa
      </h3>
      <ul className="mt-1 space-y-1.5 text-sm text-ink-900">
        {conferencia.encargos.map((linha) => (
          <li key={linha}>{linha}</li>
        ))}
      </ul>

      {conferencia.pagamentos.length > 0 ? (
        <>
          <h3 className="mt-4 text-[11px] font-semibold uppercase tracking-legal text-ink-500">
            Pagamentos
          </h3>
          <ul className="mt-1 space-y-1.5 text-sm text-ink-900">
            {conferencia.pagamentos.map((linha) => (
              <li key={linha}>{linha}</li>
            ))}
          </ul>
        </>
      ) : null}

      {conferencia.alertas.length > 0 ? (
        <div className="mt-4 rounded border border-amber-300 bg-amber-50 px-3 py-2">
          <p className="text-sm font-semibold text-amber-950">Pontos de atenção</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-amber-950">
            {conferencia.alertas.map((linha) => (
              <li key={linha}>{linha}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-3">
        <Button type="button" onClick={onConfirmar} disabled={enviando}>
          Está correto, gerar cálculo
        </Button>
        <Button type="button" variant="outline" onClick={onVoltar} disabled={enviando}>
          Voltar e corrigir
        </Button>
      </div>
    </div>
  );
}
