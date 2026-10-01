import type { ReactNode } from "react";
import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import { Tooltip } from "../../components/ui/Tooltip";
import type { PagamentoPayload } from "../../types/api";

export interface EstadoPagamentoVerba {
  id: string;
  data: string;
  valor: string;
  descricao: string;
}

export interface EstadoVerba {
  id: string;
  nome: string;
  descricao: string;
  valor: string;
  dataBase: string;
  correcaoAplicar: boolean;
  correcaoIndexador: string;
  correcaoInicio: string;
  correcaoFim: string;
  jurosAplicar: boolean;
  jurosModalidade: string;
  jurosTaxa: string;
  jurosBase: string;
  jurosInicio: string;
  jurosFim: string;
  multaAplicar: boolean;
  multaPercentual: string;
  multaValorFixo: string;
  multaBase: string;
  honorariosAplicar: boolean;
  honorariosPercentual: string;
  honorariosValorFixo: string;
  honorariosBase: string;
  pagamentos: EstadoPagamentoVerba[];
}

interface Props {
  verba: EstadoVerba;
  indice: number;
  onChange: (parcial: Partial<EstadoVerba>) => void;
  onRemover: () => void;
  coberturaFim?: string | null;
}

let contadorPagamentos = 0;

export function novaVerba(parcial: Partial<EstadoVerba> = {}): EstadoVerba {
  return {
    id: `verba-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    nome: "",
    descricao: "",
    valor: "",
    dataBase: "",
    correcaoAplicar: true,
    correcaoIndexador: "tjsp_tabela_pratica",
    correcaoInicio: "",
    correcaoFim: "",
    jurosAplicar: false,
    jurosModalidade: "taxa_legal",
    jurosTaxa: "",
    jurosBase: "corrigido",
    jurosInicio: "",
    jurosFim: "",
    multaAplicar: false,
    multaPercentual: "",
    multaValorFixo: "",
    multaBase: "corrigido",
    honorariosAplicar: false,
    honorariosPercentual: "",
    honorariosValorFixo: "",
    honorariosBase: "corrigido",
    pagamentos: [],
    ...parcial,
  };
}

function novoPagamento(): EstadoPagamentoVerba {
  contadorPagamentos += 1;
  return {
    id: `pgv-${Date.now()}-${contadorPagamentos}`,
    data: "",
    valor: "",
    descricao: "",
  };
}

export function CardVerba({ verba, indice, onChange, onRemover, coberturaFim }: Props) {
  function atualizarPagamento(id: string, parcial: Partial<EstadoPagamentoVerba>) {
    onChange({
      pagamentos: verba.pagamentos.map((p) =>
        p.id === id ? { ...p, ...parcial } : p,
      ),
    });
  }

  return (
    <CardVerbaShell
      indice={indice}
      verba={verba}
      onRemover={onRemover}
      coberturaFim={coberturaFim}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          id={`verba-nome-${verba.id}`}
          label="Nome da verba"
          required
          value={verba.nome}
          onChange={(e) => onChange({ nome: e.target.value })}
          placeholder="Ex.: Dano moral"
          tooltip="Identifica a rubrica (dano moral, honorários, restituição…)."
        />
        <Input
          id={`verba-valor-${verba.id}`}
          label="Valor"
          required
          inputMode="decimal"
          value={verba.valor}
          onChange={(e) => onChange({ valor: e.target.value })}
          placeholder="20000,00"
          tooltip="Valor nominal da verba. Enviado como texto — o backend aplica Decimal."
        />
        <Input
          id={`verba-data-base-${verba.id}`}
          label="Data-base / vencimento"
          required
          type="date"
          value={verba.dataBase}
          onChange={(e) => onChange({ dataBase: e.target.value })}
          tooltip="Data em que o valor da verba foi fixado. Pode ser no passado."
        />
        <Input
          id={`verba-descricao-${verba.id}`}
          label="Descrição"
          value={verba.descricao}
          onChange={(e) => onChange({ descricao: e.target.value })}
          placeholder="Observação livre"
        />
      </div>

      <div className="mt-4 space-y-3 rounded-xl border border-ink-200 bg-ink-50/40 p-3">
        <Switch
          id={`verba-correcao-${verba.id}`}
          checked={verba.correcaoAplicar}
          onChange={(correcaoAplicar) => onChange({ correcaoAplicar })}
          label="Correção monetária desta verba"
          description="Datas e indexador são próprios desta verba — não são globais."
        />
        {verba.correcaoAplicar ? (
          <div className="grid gap-3 md:grid-cols-3">
            <Input
              id={`verba-correcao-inicio-${verba.id}`}
              label="Correção desde"
              type="date"
              value={verba.correcaoInicio}
              onChange={(e) => onChange({ correcaoInicio: e.target.value })}
              hint={
                verba.correcaoInicio
                  ? verba.correcaoInicio
                  : `padrão: data-base (${verba.dataBase || "—"})`
              }
              tooltip="Início da correção monetária desta verba. Ex.: 10/05/2020."
            />
            <Input
              id={`verba-correcao-fim-${verba.id}`}
              label="Correção até"
              type="date"
              value={verba.correcaoFim}
              onChange={(e) => onChange({ correcaoFim: e.target.value })}
              hint={
                verba.correcaoFim
                  ? verba.correcaoFim
                  : "padrão: data-base do cálculo"
              }
              tooltip="Fim da correção. Vazio = data-base do cálculo."
            />
            <Select
              id={`verba-correcao-indexador-${verba.id}`}
              label="Indexador"
              value={verba.correcaoIndexador}
              onChange={(e) => onChange({ correcaoIndexador: e.target.value })}
              tooltip="Série oficial no backend. O React não aplica fatores."
            >
              <option value="tjsp_tabela_pratica">
                Tabela Prática TJSP
              </option>
            </Select>
          </div>
        ) : (
          <p className="text-xs text-ink-600">
            Correção <strong>não aplicada</strong> nesta verba.
          </p>
        )}
        {coberturaFim && verba.correcaoAplicar && verba.correcaoFim && (
          <p className="text-xs text-amber-800">
            Cobertura oficial da correção termina em {coberturaFim}. Se a data
            final da verba estiver além disso, o backend pode recusar o cálculo.
          </p>
        )}
      </div>

      <div className="mt-3 space-y-3 rounded-xl border border-ink-200 bg-ink-50/40 p-3">
        <Switch
          id={`verba-juros-${verba.id}`}
          checked={verba.jurosAplicar}
          onChange={(jurosAplicar) => onChange({ jurosAplicar })}
          label="Juros desta verba"
          description="Início dos juros é próprio desta verba."
        />
        {verba.jurosAplicar ? (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <Input
              id={`verba-juros-inicio-${verba.id}`}
              label="Juros desde"
              type="date"
              value={verba.jurosInicio}
              onChange={(e) => onChange({ jurosInicio: e.target.value })}
              hint={
                verba.jurosInicio
                  ? verba.jurosInicio
                  : `padrão: data-base (${verba.dataBase || "—"})`
              }
              tooltip="Ex.: dano moral com juros desde 15/03/2024, mesmo com vencimento em 2020."
            />
            <Input
              id={`verba-juros-fim-${verba.id}`}
              label="Juros até"
              type="date"
              value={verba.jurosFim}
              onChange={(e) => onChange({ jurosFim: e.target.value })}
              hint={
                verba.jurosFim
                  ? verba.jurosFim
                  : "padrão: data-base do cálculo"
              }
            />
            <Select
              id={`verba-juros-modalidade-${verba.id}`}
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
                id={`verba-juros-taxa-${verba.id}`}
                label="Taxa"
                inputMode="decimal"
                value={verba.jurosTaxa}
                onChange={(e) => onChange({ jurosTaxa: e.target.value })}
                placeholder="0.01"
                hint="Ex.: 0.01 = 1%"
              />
            ) : (
              <Select
                id={`verba-juros-base-${verba.id}`}
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
        ) : (
          <p className="text-xs text-ink-600">Juros <strong>não aplicados</strong> nesta verba.</p>
        )}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="space-y-2 rounded-xl border border-ink-200 bg-white p-3">
          <Switch
            id={`verba-multa-${verba.id}`}
            checked={verba.multaAplicar}
            onChange={(multaAplicar) => onChange({ multaAplicar })}
            label="Multa (opcional)"
          />
          {verba.multaAplicar ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Input
                id={`verba-multa-pct-${verba.id}`}
                label="% multa"
                inputMode="decimal"
                value={verba.multaPercentual}
                onChange={(e) => onChange({ multaPercentual: e.target.value })}
                placeholder="0.02"
              />
              <Input
                id={`verba-multa-valor-${verba.id}`}
                label="Valor fixo"
                inputMode="decimal"
                value={verba.multaValorFixo}
                onChange={(e) => onChange({ multaValorFixo: e.target.value })}
              />
              <Select
                id={`verba-multa-base-${verba.id}`}
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
            id={`verba-hon-${verba.id}`}
            checked={verba.honorariosAplicar}
            onChange={(honorariosAplicar) => onChange({ honorariosAplicar })}
            label="Honorários (opcional)"
          />
          {verba.honorariosAplicar ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <Input
                id={`verba-hon-pct-${verba.id}`}
                label="% honorários"
                inputMode="decimal"
                value={verba.honorariosPercentual}
                onChange={(e) => onChange({ honorariosPercentual: e.target.value })}
                placeholder="0.10"
              />
              <Input
                id={`verba-hon-valor-${verba.id}`}
                label="Valor fixo"
                inputMode="decimal"
                value={verba.honorariosValorFixo}
                onChange={(e) => onChange({ honorariosValorFixo: e.target.value })}
              />
              <Select
                id={`verba-hon-base-${verba.id}`}
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

      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-ink-800">
            Pagamentos desta verba
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({ pagamentos: [...verba.pagamentos, novoPagamento()] })
            }
          >
            + Pagamento
          </Button>
        </div>
        {verba.pagamentos.length === 0 ? (
          <p className="text-xs text-ink-500">
            Nenhum pagamento vinculado a esta verba.
          </p>
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
    </CardVerbaShell>
  );
}

function CardVerbaShell({
  indice,
  verba,
  onRemover,
  coberturaFim: _coberturaFim,
  children,
}: {
  indice: number;
  verba: EstadoVerba;
  onRemover: () => void;
  coberturaFim?: string | null;
  children: ReactNode;
}) {
  const marcos = [
    verba.valor ? `R$ ${verba.valor}` : null,
    verba.dataBase ? `venc. ${verba.dataBase}` : null,
    verba.correcaoAplicar
      ? `correção desde ${verba.correcaoInicio || verba.dataBase || "—"}`
      : "sem correção",
    verba.jurosAplicar
      ? `juros desde ${verba.jurosInicio || verba.dataBase || "—"}`
      : "sem juros",
  ].filter(Boolean);

  return (
    <section
      className="rounded-2xl border border-brand-200 bg-white shadow-card"
      aria-labelledby={`verba-title-${verba.id}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 bg-brand-50/60 px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">
            Verba {indice + 1}
          </p>
          <h3
            id={`verba-title-${verba.id}`}
            className="text-base font-semibold text-ink-950"
          >
            {verba.nome || "Verba sem nome"}
          </h3>
          <p className="mt-1 text-xs text-ink-600">
            {marcos.join(" · ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tooltip text="Cada verba tem suas próprias datas de correção e juros. O backend calcula cada rubrica de forma independente." />
          <Button type="button" variant="ghost" size="sm" onClick={onRemover}>
            Remover verba
          </Button>
        </div>
      </header>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}

export function montarPagamentosVerba(
  pagamentos: EstadoPagamentoVerba[],
): PagamentoPayload[] {
  return pagamentos
    .filter((pg) => pg.data && pg.valor.trim())
    .map((pg) => ({
      data: pg.data,
      valor: pg.valor.trim(),
      descricao: (pg.descricao ?? "").trim(),
    }));
}
