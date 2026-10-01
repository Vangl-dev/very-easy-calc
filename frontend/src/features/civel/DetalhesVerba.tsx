import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import { Tooltip } from "../../components/ui/Tooltip";
import { novoPagamentoVerba, type EstadoVerba } from "./estadoVerba";
import { Button } from "../../components/ui/Button";

interface Props {
  verba: EstadoVerba;
  onChange: (parcial: Partial<EstadoVerba>) => void;
  coberturaFim?: string | null;
}

/** Painel avançado — só aparece após "Configurar detalhes". */
export function DetalhesVerba({ verba, onChange, coberturaFim }: Props) {
  function atualizarPagamento(id: string, parcial: Partial<EstadoVerba["pagamentos"][number]>) {
    onChange({
      pagamentos: verba.pagamentos.map((p) =>
        p.id === id ? { ...p, ...parcial } : p,
      ),
    });
  }

  return (
    <div className="space-y-4 border-t border-dashed border-ink-200 bg-ink-50/40 px-3 py-4">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold text-ink-900">Detalhes da verba</h4>
        <Tooltip text="Configurações avançadas desta rubrica. As datas principais já estão na tabela de lançamento." />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Input
          id={`det-desc-${verba.id}`}
          label="Descrição"
          value={verba.descricao}
          onChange={(e) => onChange({ descricao: e.target.value })}
          placeholder="Observação livre"
        />
        <Input
          id={`det-data-base-${verba.id}`}
          label="Data-base / vencimento"
          type="date"
          value={verba.dataBase}
          onChange={(e) => onChange({ dataBase: e.target.value })}
          tooltip="Data em que o valor da verba foi fixado. Pode ser no passado."
        />
      </div>

      <div className="space-y-2 rounded-xl border border-ink-200 bg-white p-3">
        <Switch
          id={`det-correcao-${verba.id}`}
          checked={verba.correcaoAplicar}
          onChange={(correcaoAplicar) => onChange({ correcaoAplicar })}
          label="Correção monetária"
          description="Fim da correção e indexador desta verba."
        />
        {verba.correcaoAplicar ? (
          <div className="grid gap-3 md:grid-cols-3">
            <Input
              id={`det-correcao-fim-${verba.id}`}
              label="Correção até"
              type="date"
              value={verba.correcaoFim}
              onChange={(e) => onChange({ correcaoFim: e.target.value })}
              hint={verba.correcaoFim ? verba.correcaoFim : "padrão: data-base do cálculo"}
            />
            <Select
              id={`det-correcao-indexador-${verba.id}`}
              label="Indexador"
              value={verba.correcaoIndexador}
              onChange={(e) => onChange({ correcaoIndexador: e.target.value })}
            >
              <option value="tjsp_tabela_pratica">Tabela Prática TJSP</option>
            </Select>
          </div>
        ) : null}
        {coberturaFim && verba.correcaoAplicar ? (
          <p className="text-xs text-amber-800">
            Cobertura oficial até {coberturaFim}. Períodos além disso podem ser
            recusados pelo backend.
          </p>
        ) : null}
      </div>

      <div className="space-y-2 rounded-xl border border-ink-200 bg-white p-3">
        <Switch
          id={`det-juros-${verba.id}`}
          checked={verba.jurosAplicar}
          onChange={(jurosAplicar) => onChange({ jurosAplicar })}
          label="Juros"
          description="Fim dos juros e modalidade desta verba."
        />
        {verba.jurosAplicar ? (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <Input
              id={`det-juros-fim-${verba.id}`}
              label="Juros até"
              type="date"
              value={verba.jurosFim}
              onChange={(e) => onChange({ jurosFim: e.target.value })}
              hint={verba.jurosFim ? verba.jurosFim : "padrão: data-base do cálculo"}
            />
            <Select
              id={`det-juros-modalidade-${verba.id}`}
              label="Modalidade"
              value={verba.jurosModalidade}
              onChange={(e) => onChange({ jurosModalidade: e.target.value })}
            >
              <option value="taxa_legal">Taxa Legal (BCB SGS 29543)</option>
              <option value="fixa">Taxa fixa</option>
              <option value="nao_aplicar">Não aplicar</option>
            </Select>
            {verba.jurosModalidade === "fixa" ? (
              <Input
                id={`det-juros-taxa-${verba.id}`}
                label="Taxa"
                inputMode="decimal"
                value={verba.jurosTaxa}
                onChange={(e) => onChange({ jurosTaxa: e.target.value })}
                placeholder="0.01"
                hint="Ex.: 0.01 = 1%"
              />
            ) : (
              <Select
                id={`det-juros-base-${verba.id}`}
                label="Base de incidência"
                value={verba.jurosBase}
                onChange={(e) => onChange({ jurosBase: e.target.value })}
              >
                <option value="corrigido">Valor corrigido</option>
                <option value="principal">Principal histórico</option>
                <option value="com_juros">Principal + correção + juros</option>
              </Select>
            )}
          </div>
        ) : null}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="space-y-2 rounded-xl border border-ink-200 bg-white p-3">
          <Switch
            id={`det-multa-${verba.id}`}
            checked={verba.multaAplicar}
            onChange={(multaAplicar) => onChange({ multaAplicar })}
            label="Multa"
          />
          {verba.multaAplicar ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Input
                id={`det-multa-pct-${verba.id}`}
                label="% multa"
                inputMode="decimal"
                value={verba.multaPercentual}
                onChange={(e) => onChange({ multaPercentual: e.target.value })}
                placeholder="0.02"
              />
              <Input
                id={`det-multa-valor-${verba.id}`}
                label="Valor fixo"
                inputMode="decimal"
                value={verba.multaValorFixo}
                onChange={(e) => onChange({ multaValorFixo: e.target.value })}
              />
              <Select
                id={`det-multa-base-${verba.id}`}
                label="Base"
                value={verba.multaBase}
                onChange={(e) => onChange({ multaBase: e.target.value })}
              >
                <option value="corrigido">Corrigido</option>
                <option value="principal">Principal</option>
                <option value="com_juros">Com juros</option>
              </Select>
            </div>
          ) : null}
        </div>
        <div className="space-y-2 rounded-xl border border-ink-200 bg-white p-3">
          <Switch
            id={`det-hon-${verba.id}`}
            checked={verba.honorariosAplicar}
            onChange={(honorariosAplicar) => onChange({ honorariosAplicar })}
            label="Honorários"
          />
          {verba.honorariosAplicar ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Input
                id={`det-hon-pct-${verba.id}`}
                label="% honorários"
                inputMode="decimal"
                value={verba.honorariosPercentual}
                onChange={(e) => onChange({ honorariosPercentual: e.target.value })}
                placeholder="0.10"
              />
              <Input
                id={`det-hon-valor-${verba.id}`}
                label="Valor fixo"
                inputMode="decimal"
                value={verba.honorariosValorFixo}
                onChange={(e) => onChange({ honorariosValorFixo: e.target.value })}
              />
              <Select
                id={`det-hon-base-${verba.id}`}
                label="Base"
                value={verba.honorariosBase}
                onChange={(e) => onChange({ honorariosBase: e.target.value })}
              >
                <option value="corrigido">Corrigido</option>
                <option value="principal">Principal</option>
                <option value="com_juros">Com juros</option>
              </Select>
            </div>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-ink-800">
            Pagamentos desta verba
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({ pagamentos: [...verba.pagamentos, novoPagamentoVerba()] })
            }
          >
            + Pagamento
          </Button>
        </div>
        {verba.pagamentos.length === 0 ? (
          <p className="text-xs text-ink-500">Nenhum pagamento vinculado.</p>
        ) : (
          <ul className="space-y-2">
            {verba.pagamentos.map((pg) => (
              <li
                key={pg.id}
                className="grid gap-2 rounded-lg border border-ink-200 bg-white p-2 md:grid-cols-4"
              >
                <Input
                  id={`pgv-data-${pg.id}`}
                  label="Data"
                  type="date"
                  required
                  value={pg.data}
                  onChange={(e) => atualizarPagamento(pg.id, { data: e.target.value })}
                />
                <Input
                  id={`pgv-valor-${pg.id}`}
                  label="Valor"
                  required
                  inputMode="decimal"
                  value={pg.valor}
                  onChange={(e) => atualizarPagamento(pg.id, { valor: e.target.value })}
                />
                <Input
                  id={`pgv-desc-${pg.id}`}
                  label="Descrição"
                  value={pg.descricao}
                  onChange={(e) =>
                    atualizarPagamento(pg.id, { descricao: e.target.value })
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="self-end"
                  onClick={() =>
                    onChange({
                      pagamentos: verba.pagamentos.filter((p) => p.id !== pg.id),
                    })
                  }
                >
                  Remover
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
