import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Form";
import { Message } from "../../components/ui/Message";
import { Switch } from "../../components/ui/Switch";
import { SecaoIdentificacao, type EstadoIdentificacao } from "../novo-calculo/SecaoIdentificacao";
import { ModoSimples } from "./ModoSimples";
import {
  BASES_ENCARGO,
  CORRECOES_REGIME,
  JUROS_REGIME,
  anexarPagamentosGlobais,
  aplicarEmTodas,
  aplicarEncargoGeral,
  contaDerivacao,
  dependentesDe,
  errosPagamentos,
  errosVerbas,
  formatarDataBR,
  formatarMoedaBR,
  fracaoDePercentual,
  montarVerbaPayload,
  novaPagamento,
  novaRegime,
  novaVerba,
  opcoesDeBase,
  podeRemoverVerba,
  resumoVerba,
  verbaSomavel,
  valorProjetado,
  type ConfigEncargoGeral,
  type EstadoPagamentoVerba,
  type EstadoRegime,
  type EstadoVerba,
  type TipoVerba,
} from "./estadoVerba";
import { api, mensagemErroAmigavel } from "../../lib/api";
import { coberturaInsuficientePara } from "../../lib/cobertura";
import { rotuloCompetenciaExtenso } from "../../lib/competencia";
import { obterRascunho, salvarRascunho } from "../../lib/rascunhos";
import type { CalculoCivelPayload, CoberturaEfetiva, EncargoConsolidadoPayload, VerbaPayload } from "../../types/api";

const INDEXADORES_CORRECAO = [{ valor: "tjsp_tabela_pratica", rotulo: "Tabela Prática TJSP" }];

const COLUNAS_LANCAMENTO =
  "gap-x-4 gap-y-3 lg:grid-cols-[9rem_9rem_10rem_minmax(0,1fr)_5rem] lg:gap-x-3 lg:gap-y-0 lg:items-end";

type ModoCalculo = "simples" | "detalhado";

type EstadoEncargoConsolidado = {
  ativo: boolean;
  tipo: "multa" | "honorarios";
  percentual: string;
  base: "principal" | "corrigido" | "com_juros";
};

type AvisoCriterioDesativado = {
  verba: string;
  criterio: "juros" | "correção monetária";
};

function criteriosDesativados(verbas: EstadoVerba[]): AvisoCriterioDesativado[] {
  return verbas.flatMap((verba, indice) => {
    const nome = verba.nome.trim() || `Verba ${indice + 1}`;
    const avisos: AvisoCriterioDesativado[] = [];
    if (!verba.jurosAplicar) avisos.push({ verba: nome, criterio: "juros" });
    if (!verba.correcaoAplicar) {
      avisos.push({ verba: nome, criterio: "correção monetária" });
    }
    return avisos;
  });
}

function separarPagamentosDasVerbas(
  verbas: VerbaPayload[],
  pagamentosGlobais: EstadoPagamentoVerba[] = [],
): {
  verbas: EstadoVerba[];
  pagamentos: EstadoPagamentoVerba[];
} {
  const pagamentos: EstadoPagamentoVerba[] = [];
  const hidratadas = verbas.map((verba, indice) => {
    for (const [pagamentoIndice, pagamento] of (verba.pagamentos ?? []).entries()) {
      pagamentos.push({
        id: `pagamento-revisao-${indice}-${pagamentoIndice}`,
        data: pagamento.data,
        valor: pagamento.valor,
        descricao: pagamento.descricao ?? "",
      });
    }
    // O formulário Cível tem uma única seção de pagamentos. Ao voltar, os
    // lançamentos retornam a ela e serão anexados uma única vez ao gerar.
    return hidratarVerba({ ...verba, pagamentos: [] }, indice);
  });
  // Payloads Cíveis atuais anexam o pagamento à verba-alvo. Em payloads
  // legados, sem esse anexo, mantemos a lista global. Nunca juntamos as duas
  // fontes para não reintroduzir o abatimento duas vezes.
  return {
    verbas: hidratadas,
    pagamentos: pagamentos.length > 0 ? pagamentos : pagamentosGlobais,
  };
}

function montarPayload(
  identificacao: EstadoIdentificacao,
  dataBaseCalculo: string,
  verbas: EstadoVerba[],
  pagamentos: EstadoPagamentoVerba[],
  encargoConsolidado: EstadoEncargoConsolidado,
  revisaoDe: string | null,
): CalculoCivelPayload {
  const pagamentosValidos = pagamentos.filter(
    (pg) => pg.data && pg.valor.trim(),
  );
  const verbasComPagamentos = anexarPagamentosGlobais(
    verbas,
    pagamentosValidos,
  );
  const componentes = encargoConsolidado.base === "principal"
    ? ["principal"] as const
    : encargoConsolidado.base === "corrigido"
      ? ["principal_corrigido"] as const
      : ["principal_corrigido", "juros_individuais"] as const;
  const encargos_consolidados: EncargoConsolidadoPayload[] = encargoConsolidado.ativo
    ? [{
      id: "encargo-consolidado-1",
      tipo: encargoConsolidado.tipo,
      ordem: 1,
      componentes: [...componentes],
      percentual: fracaoDePercentual(encargoConsolidado.percentual),
      entra_no_total: true,
    }]
    : [];
  return {
    tipo: "parcelas",
    titulo: identificacao.titulo.trim(),
    revisao_de: revisaoDe,
    processo: identificacao.processo.trim(),
    parte: identificacao.parte.trim(),
    data_base: dataBaseCalculo,
    verbas: verbasComPagamentos.map((v) => montarVerbaPayload(v, dataBaseCalculo)),
    correcao: { aplicar: false },
    juros: { aplicar: false },
    multa: { aplicar: false },
    honorarios: { aplicar: false },
    pagamentos: [],
    encargos_consolidados,
  };
}

function errosValidacao(
  identificacao: EstadoIdentificacao,
  dataBaseCalculo: string,
  verbas: EstadoVerba[],
  pagamentos: EstadoPagamentoVerba[],
): string[] {
  const erros: string[] = [];
  if (!identificacao.titulo.trim()) erros.push("Informe o nome do cálculo.");
  if (!dataBaseCalculo) erros.push("Informe até quando o cálculo deve ser atualizado.");
  erros.push(...errosVerbas(verbas, dataBaseCalculo));
  erros.push(...errosPagamentos(pagamentos));
  return erros;
}

function percentualParaTela(valor: string | null | undefined): string {
  if (!valor) return "";
  const numero = Number(valor);
  return Number.isFinite(numero) ? String(numero * 100) : "";
}

function hidratarVerba(verba: VerbaPayload, indice: number): EstadoVerba {
  const correcao = verba.correcao ?? { aplicar: false };
  const juros = verba.juros ?? { aplicar: false };
  const multa = verba.multa ?? { aplicar: false };
  const honorarios = verba.honorarios ?? { aplicar: false };
  return novaVerba({
    id: verba.id || `verba-revisao-${indice}`,
    tipo: verba.tipo ?? "valor", nome: verba.nome, descricao: verba.descricao ?? "",
    valor: verba.valor ?? "", percentual: percentualParaTela(verba.percentual),
    baseVerbaId: verba.base_verba_id ?? "", entraNoTotal: verba.entra_no_total ?? null,
    correcaoAplicar: correcao.aplicar, correcaoIndexador: correcao.indexador ?? "tjsp_tabela_pratica",
    correcaoInicio: correcao.termo_inicial ?? verba.data_base, correcaoFim: correcao.termo_final ?? "",
    jurosAplicar: juros.aplicar, jurosModalidade: juros.modalidade ?? "taxa_legal",
    jurosTaxa: percentualParaTela(juros.taxa), jurosBase: juros.base ?? "corrigido",
    jurosInicio: juros.inicio ?? "", jurosFim: juros.fim ?? "",
    multaAplicar: multa.aplicar, multaPercentual: percentualParaTela(multa.percentual),
    multaValorFixo: multa.valor_fixo ?? "", multaBase: multa.base ?? "corrigido",
    honorariosAplicar: honorarios.aplicar, honorariosPercentual: percentualParaTela(honorarios.percentual),
    honorariosValorFixo: honorarios.valor_fixo ?? "", honorariosBase: honorarios.base ?? "corrigido",
    pagamentos: (verba.pagamentos ?? []).map((p, i) => ({ id: `pagamento-revisao-${indice}-${i}`, data: p.data, valor: p.valor, descricao: p.descricao ?? "" })),
    regimes: (verba.regimes ?? []).map((r, i) => ({ id: `regime-revisao-${indice}-${i}`, dataInicio: r.data_inicio ?? "", dataFim: r.data_fim ?? "", correcao: r.criterio ?? r.correcao ?? "", juros: r.juros?.modalidade ?? "" })),
  });
}

interface CampoProps {
  htmlFor: string;
  rotulo: string;
  className?: string;
  children: ReactNode;
}

function Campo({ htmlFor, rotulo, className = "", children }: CampoProps) {
  return (
    <div className={`space-y-1 lg:space-y-0 ${className}`}>
      {htmlFor ? (
        <label htmlFor={htmlFor} className="label-legal lg:sr-only">
          {rotulo}
        </label>
      ) : (
        <span className="label-legal lg:sr-only">{rotulo}</span>
      )}
      {children}
    </div>
  );
}

interface CamposEncargoProps {
  prefixo: string;
  indice: string | number;
  percentual: string;
  valorFixo: string;
  base: string;
  onChange: (parcial: {
    percentual?: string;
    valorFixo?: string;
    base?: string;
  }) => void;
}

/** Percentual OU valor fixo — preencher um limpa o outro (o motor rejeita ambos). */
function CamposEncargo({
  prefixo,
  indice,
  percentual,
  valorFixo,
  base,
  onChange,
}: CamposEncargoProps) {
  const rotulo = prefixo === "multa" ? "Multa" : "Honorários";
  const rotuloBase = prefixo === "multa" ? "Base da multa" : "Base dos honorários";
  return (
    <div className="space-y-2">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor={`${prefixo}-percentual-${indice}`} className="label-legal">
            {rotulo} (%)
          </label>
          <div className="relative">
            <input
              id={`${prefixo}-percentual-${indice}`}
              type="text"
              inputMode="decimal"
              className="field-line pr-6"
              placeholder="10"
              value={percentual}
              onChange={(e) =>
                onChange({ percentual: e.target.value, valorFixo: "" })
              }
            />
            <span className="pointer-events-none absolute right-0 top-2 text-sm text-ink-500">
              %
            </span>
          </div>
        </div>
        <div className="space-y-1">
          <label htmlFor={`${prefixo}-fixo-${indice}`} className="label-legal">
            {rotulo} (valor fixo)
          </label>
          <input
            id={`${prefixo}-fixo-${indice}`}
            type="text"
            inputMode="decimal"
            className="field-line"
            placeholder="500,00"
            value={valorFixo}
            onChange={(e) =>
              onChange({ valorFixo: e.target.value, percentual: "" })
            }
          />
        </div>
      </div>
      <Select
        id={`${prefixo}-base-${indice}`}
        label={rotuloBase}
        className="sm:max-w-xs"
        value={base}
        onChange={(e) => onChange({ base: e.target.value })}
      >
        {BASES_ENCARGO.map((op) => (
          <option key={op.valor} value={op.valor}>
            {op.rotulo}
          </option>
        ))}
      </Select>
      <p className="text-[11px] text-ink-500">
        Preencha o percentual OU o valor fixo — nunca os dois.
      </p>
    </div>
  );
}

interface LinhaValorProps {
  verba: EstadoVerba;
  indice: number;
  verbas: EstadoVerba[];
  onChange: (parcial: Partial<EstadoVerba>) => void;
  onRemover: () => void;
}

function LinhaValor({ verba, indice, verbas, onChange, onRemover }: LinhaValorProps) {
  const nomesPorId = useMemo(() => {
    const mapa = new Map<string, string>();
    verbas.forEach((v, i) => mapa.set(v.id, v.nome.trim() || `Lançamento ${i + 1}`));
    return mapa;
  }, [verbas]);

  const opcoes = opcoesDeBase(verbas, verba.id);
  const dependentes = dependentesDe(verba.id, verbas);
  const projetado = verba.tipo === "percentual" ? valorProjetado(verba, verbas) : null;
  const derivado = verba.tipo === "percentual";

  function parcialMulta(parcial: {
    percentual?: string;
    valorFixo?: string;
    base?: string;
  }): Partial<EstadoVerba> {
    return {
      ...(parcial.percentual !== undefined
        ? { multaPercentual: parcial.percentual }
        : {}),
      ...(parcial.valorFixo !== undefined
        ? { multaValorFixo: parcial.valorFixo }
        : {}),
      ...(parcial.base !== undefined ? { multaBase: parcial.base } : {}),
    };
  }

  function parcialHonorarios(parcial: {
    percentual?: string;
    valorFixo?: string;
    base?: string;
  }): Partial<EstadoVerba> {
    return {
      ...(parcial.percentual !== undefined
        ? { honorariosPercentual: parcial.percentual }
        : {}),
      ...(parcial.valorFixo !== undefined
        ? { honorariosValorFixo: parcial.valorFixo }
        : {}),
      ...(parcial.base !== undefined ? { honorariosBase: parcial.base } : {}),
    };
  }

  function atualizarRegime(id: string, parcial: Partial<EstadoRegime>) {
    onChange({
      regimes: verba.regimes.map((r) => (r.id === id ? { ...r, ...parcial } : r)),
    });
  }

  function trocarTipo(tipo: TipoVerba) {
    if (tipo === verba.tipo) return;
    if (tipo === "percentual") {
      onChange({
        tipo,
        valor: "",
        baseVerbaId: opcoes[0]?.id ?? "",
        percentual: verba.percentual || "",
      });
    } else {
      onChange({ tipo, baseVerbaId: "", percentual: "", valor: "" });
    }
  }

  return (
    <li className="border-b border-line px-4 py-4 transition-colors last:border-b-0 hover:bg-ink-50/40">
      <div className={`grid grid-cols-2 ${COLUNAS_LANCAMENTO}`}>
        <div className="space-y-1 lg:space-y-0">
          <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium text-ink-800">
            <input
              type="checkbox"
              checked={verba.correcaoAplicar}
              onChange={(e) => onChange({ correcaoAplicar: e.target.checked })}
              className="h-4 w-4 accent-brand-700"
              aria-label={`Aplicar correção monetária no lançamento ${indice + 1}`}
            />
            <span className="sr-only">Aplicar </span>
            Correção monetária
          </label>
          {verba.correcaoAplicar ? (
            <>
              <label
                htmlFor={`lanc-correcao-${verba.id}`}
                className="label-legal lg:sr-only"
              >
                Correção desde
              </label>
              <input
                id={`lanc-correcao-${verba.id}`}
                type="date"
                required
                className="field-line"
                value={verba.correcaoInicio}
                onChange={(e) => onChange({ correcaoInicio: e.target.value })}
              />
            </>
          ) : (
            <p className="text-[12px] text-ink-400">Correção desativada</p>
          )}
        </div>

        <div className="space-y-1 lg:space-y-0">
          <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium text-ink-800">
            <input
              type="checkbox"
              checked={verba.jurosAplicar}
              onChange={(e) => onChange({ jurosAplicar: e.target.checked })}
              className="h-4 w-4 accent-brand-700"
              aria-label={`Aplicar juros no lançamento ${indice + 1}`}
            />
            Juros
          </label>
          {verba.jurosAplicar ? (
            <>
              <p className="text-[11px] leading-tight text-ink-500">
                Taxa Legal (BCB SGS 29543)
              </p>
              <label
                htmlFor={`lanc-juros-${verba.id}`}
                className="label-legal lg:sr-only"
              >
                Juros desde
              </label>
              <input
                id={`lanc-juros-${verba.id}`}
                type="date"
                required
                className="field-line"
                value={verba.jurosInicio}
                onChange={(e) => onChange({ jurosInicio: e.target.value })}
              />
            </>
          ) : (
            <p className="text-[12px] text-ink-400">Juros desativados</p>
          )}
        </div>

        <Campo
          htmlFor={derivado ? "" : `lanc-valor-${verba.id}`}
          rotulo="Valor"
          className="col-span-2 lg:col-span-1"
        >
          {derivado ? (
            <p className="font-display text-[15px] text-ink-900">
              {projetado !== null ? formatarMoedaBR(projetado) : "R$ —"}
            </p>
          ) : (
            <>
              <input
                id={`lanc-valor-${verba.id}`}
                type="text"
                required
                inputMode="decimal"
                className="field-line"
                placeholder="44000,00"
                value={verba.valor}
                onChange={(e) => onChange({ valor: e.target.value })}
              />
              {opcoes.length > 0 ? (
                <button
                  type="button"
                  aria-label={`Usar percentual de outra verba no lançamento ${indice + 1}`}
                  onClick={() =>
                    onChange({
                      tipo: "percentual",
                      valor: "",
                      baseVerbaId: opcoes[0].id,
                      percentual: "",
                    })
                  }
                  className="mt-1.5 block text-[11px] font-semibold uppercase tracking-legal text-brand-700 hover:underline"
                >
                  Percentual de outra verba
                </button>
              ) : null}
            </>
          )}
        </Campo>

        <Campo
          htmlFor={`lanc-descricao-${verba.id}`}
          rotulo="Descrição"
          className="col-span-2 lg:col-span-1"
        >
          <input
            id={`lanc-descricao-${verba.id}`}
            type="text"
            required
            className="field-line"
            placeholder="Ex.: Valor da causa"
            value={verba.nome}
            onChange={(e) => onChange({ nome: e.target.value, descricao: e.target.value })}
          />
        </Campo>

        <div className="col-span-2 flex items-end lg:col-span-1 lg:justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemover}
            aria-label={`Remover lançamento ${indice + 1}`}
          >
            Remover
          </Button>
        </div>
      </div>

      {derivado ? (
        <div className="mt-3 rounded border border-line bg-ink-50/60 px-3 py-3 sm:px-4">
          <fieldset>
            <legend className="label-legal">Como calcular</legend>
            <div className="mt-1.5 flex flex-wrap gap-x-6 gap-y-2">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-800">
                <input
                  type="radio"
                  name={`tipo-verba-${verba.id}`}
                  checked={verba.tipo === "valor"}
                  onChange={() => trocarTipo("valor")}
                  className="accent-brand-700"
                />
                Informar valor
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-800">
                <input
                  type="radio"
                  name={`tipo-verba-${verba.id}`}
                  checked={verba.tipo === "percentual"}
                  onChange={() => trocarTipo("percentual")}
                  className="accent-brand-700"
                />
                Percentual de outra verba
              </label>
            </div>
          </fieldset>

          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-[10rem_16rem_minmax(0,1fr)]">
            <div className="space-y-1">
              <label htmlFor={`lanc-percentual-${verba.id}`} className="label-legal">
                Percentual
              </label>
              <div className="relative">
                <input
                  id={`lanc-percentual-${verba.id}`}
                  type="text"
                  required
                  inputMode="decimal"
                  className="field-line pr-6"
                  placeholder="12"
                  value={verba.percentual}
                  onChange={(e) => onChange({ percentual: e.target.value })}
                />
                <span className="pointer-events-none absolute right-0 top-2 text-sm text-ink-500">
                  %
                </span>
              </div>
            </div>

            <Select
              id={`lanc-base-${verba.id}`}
              label="Sobre"
              required
              value={verba.baseVerbaId}
              onChange={(e) => onChange({ baseVerbaId: e.target.value })}
            >
              <option value="">Selecione…</option>
              {opcoes.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.rotulo}
                </option>
              ))}
            </Select>

            <div className="space-y-1 sm:col-span-2 lg:col-span-1">
              <span className="label-legal">Prévia</span>
              {verba.percentual.trim() && verba.baseVerbaId ? (
                <p className="text-sm font-medium text-ink-800">
                  {resumoVerba(verba, nomesPorId)}
                </p>
              ) : null}
              <p className="font-display text-[15px] text-ink-900">
                {contaDerivacao(verba, verbas) ?? "Informe o percentual e escolha a base."}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onChange({ regimes: [...verba.regimes, novaRegime()] })}
          className="text-[11px] font-semibold uppercase tracking-legal text-brand-700 hover:underline"
        >
          + Adicionar regra de atualização
        </button>
        {verba.regimes.length > 0 ? (
          <span className="text-[11px] text-ink-500">
            {verba.regimes.length === 1
              ? "1 período com critério próprio"
              : `${verba.regimes.length} períodos com critério próprio`}
          </span>
        ) : null}
      </div>

      {verba.regimes.length > 0 ? (
        <fieldset className="mt-3 rounded border border-line bg-ink-50/60 px-3 py-3 sm:px-4">
          <legend className="label-legal">Regras de atualização</legend>
          <ul className="mt-2 space-y-3">
            {verba.regimes.map((regime, ridx) => (
              <li
                key={regime.id}
                className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[8rem_8rem_minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end"
              >
                <Input
                  id={`regime-inicio-${regime.id}`}
                  label="De"
                  type="date"
                  value={regime.dataInicio}
                  onChange={(e) =>
                    atualizarRegime(regime.id, { dataInicio: e.target.value })
                  }
                />
                <Input
                  id={`regime-fim-${regime.id}`}
                  label="Até"
                  type="date"
                  value={regime.dataFim}
                  onChange={(e) =>
                    atualizarRegime(regime.id, { dataFim: e.target.value })
                  }
                />
                <Select
                  id={`regime-correcao-${regime.id}`}
                  label="Correção do período"
                  value={regime.correcao}
                  onChange={(e) =>
                    atualizarRegime(regime.id, { correcao: e.target.value })
                  }
                >
                  {CORRECOES_REGIME.map((op) => (
                    <option key={op.valor} value={op.valor}>
                      {op.rotulo}
                    </option>
                  ))}
                </Select>
                <Select
                  id={`regime-juros-${regime.id}`}
                  label="Juros do período"
                  value={regime.juros}
                  onChange={(e) =>
                    atualizarRegime(regime.id, { juros: e.target.value })
                  }
                >
                  {JUROS_REGIME.map((op) => (
                    <option key={op.valor} value={op.valor}>
                      {op.rotulo}
                    </option>
                  ))}
                </Select>
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Remover regra de atualização ${ridx + 1}`}
                    onClick={() =>
                      onChange({
                        regimes: verba.regimes.filter((r) => r.id !== regime.id),
                      })
                    }
                  >
                    Remover
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-ink-500">
            O motor divide o período na troca de critério; a competência da troca
            pertence ao regime seguinte.
          </p>
        </fieldset>
      ) : null}

      <fieldset className="mt-3 rounded border border-line bg-ink-50/60 px-3 py-3 sm:px-4">
        <legend className="label-legal">Multa e honorários</legend>
        <div className="mt-1.5 space-y-4">
          <div>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium text-ink-800">
              <input
                type="checkbox"
                checked={verba.multaAplicar}
                onChange={(e) => onChange({ multaAplicar: e.target.checked })}
                className="h-4 w-4 accent-brand-700"
                aria-label={`Aplicar multa no lançamento ${indice + 1}`}
              />
              Multa
            </label>
            {verba.multaAplicar ? (
              <div className="mt-2">
                <CamposEncargo
                  prefixo="multa"
                  indice={verba.id}
                  percentual={verba.multaPercentual}
                  valorFixo={verba.multaValorFixo}
                  base={verba.multaBase}
                  onChange={(parcial) => onChange(parcialMulta(parcial))}
                />
              </div>
            ) : (
              <p className="mt-1 text-[12px] text-ink-400">Multa desativada</p>
            )}
          </div>
          <div>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium text-ink-800">
              <input
                type="checkbox"
                checked={verba.honorariosAplicar}
                onChange={(e) => onChange({ honorariosAplicar: e.target.checked })}
                className="h-4 w-4 accent-brand-700"
                aria-label={`Aplicar honorários no lançamento ${indice + 1}`}
              />
              Honorários
            </label>
            {verba.honorariosAplicar ? (
              <div className="mt-2">
                <CamposEncargo
                  prefixo="honorarios"
                  indice={verba.id}
                  percentual={verba.honorariosPercentual}
                  valorFixo={verba.honorariosValorFixo}
                  base={verba.honorariosBase}
                  onChange={(parcial) => onChange(parcialHonorarios(parcial))}
                />
              </div>
            ) : (
              <p className="mt-1 text-[12px] text-ink-400">Honorários desativados</p>
            )}
          </div>
        </div>
      </fieldset>

      {dependentes.length > 0 ? (
        <p className="mt-2 text-xs text-ink-500">
          Usada como base por:{" "}
          <span className="text-brand-700">
            {dependentes.map((d) => d.nome || "lançamento sem nome").join(", ")}
          </span>
        </p>
      ) : null}

      <div className="mt-3 border-t border-line pt-3">
        <Select
          id={`lanc-total-${verba.id}`}
          label="Compõe o total da execução"
          className="sm:max-w-xs"
          hint="Padrão: a verba usada como base por outra fica fora do total; as demais entram."
          value={
            verba.entraNoTotal === true
              ? "true"
              : verba.entraNoTotal === false
                ? "false"
                : ""
          }
          onChange={(e) =>
            onChange({
              entraNoTotal:
                e.target.value === "" ? null : e.target.value === "true",
            })
          }
        >
          <option value="">Padrão</option>
          <option value="true">Sim — soma no total</option>
          <option value="false">Não — fica fora do total</option>
        </Select>
      </div>
    </li>
  );
}

interface SecaoEncargosProps {
  verbas: EstadoVerba[];
  onAlternarCorrecao: (ligado: boolean) => void;
  onAlternarJuros: (ligado: boolean) => void;
  onJurosBase: (base: string) => void;
  onMulta: (parcial: Partial<ConfigEncargoGeral>) => void;
  onHonorarios: (parcial: Partial<ConfigEncargoGeral>) => void;
}

function SecaoEncargos({
  verbas,
  onAlternarCorrecao,
  onAlternarJuros,
  onJurosBase,
  onMulta,
  onHonorarios,
}: SecaoEncargosProps) {
  const vazio = verbas.length === 0;
  const correcaoGlobal = !vazio && verbas.every((v) => v.correcaoAplicar);
  const jurosGlobal = !vazio && verbas.every((v) => v.jurosAplicar);
  const refMulta = verbas.find((v) => v.multaAplicar);
  const refHon = verbas.find((v) => v.honorariosAplicar);
  const jurosBase = verbas.find((v) => v.jurosAplicar)?.jurosBase ?? "corrigido";
  const somaveis = verbas.filter((v) => verbaSomavel(v, verbas));
  const multaAtiva = Boolean(refMulta);
  const honAtiva = Boolean(refHon);
  const baseConsolidada = verbas.length > 1 && (multaAtiva || honAtiva);
  const multaFixaSoPrimeira = multaAtiva && refMulta?.multaValorFixo.trim() && somaveis.length > 1;
  const honFixaSoPrimeira = honAtiva && refHon?.honorariosValorFixo.trim() && somaveis.length > 1;

  return (
    <div className="mt-4 space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <Switch
          id="enc-correcao"
          label="Correção monetária"
          description="Tabela Prática TJSP, automática até a data final."
          checked={correcaoGlobal}
          onChange={onAlternarCorrecao}
          disabled={vazio}
        />
        <Switch
          id="enc-juros"
          label="Juros"
          description="Taxa Legal (BCB SGS 29543), desde a data de cada valor."
          checked={jurosGlobal}
          onChange={onAlternarJuros}
          disabled={vazio}
        />
      </div>

      {jurosGlobal ? (
        <div className="max-w-xs">
          <Select
            id="enc-juros-base"
            label="Juros sobre"
            value={jurosBase}
            onChange={(e) => onJurosBase(e.target.value)}
          >
            <option value="corrigido">Valor corrigido</option>
            <option value="principal">Valor original</option>
          </Select>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-3">
          <Switch
            id="enc-multa"
            label="Multa"
            description="Percentual sobre cada valor, ou valor fixo lançado uma vez."
            checked={multaAtiva}
            onChange={(c) => onMulta({ aplicar: c })}
            disabled={vazio}
          />
          {multaAtiva && refMulta ? (
            <div className="rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3">
              <CamposEncargo
                prefixo="multa"
                indice="global"
                percentual={refMulta.multaPercentual}
                valorFixo={refMulta.multaValorFixo}
                base={refMulta.multaBase}
                onChange={onMulta}
              />
            </div>
          ) : null}
        </div>
        <div className="space-y-3">
          <Switch
            id="enc-honorarios"
            label="Honorários"
            description="Percentual sobre cada valor, ou valor fixo lançado uma vez."
            checked={honAtiva}
            onChange={(c) => onHonorarios({ aplicar: c })}
            disabled={vazio}
          />
          {honAtiva && refHon ? (
            <div className="rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3">
              <CamposEncargo
                prefixo="honorarios"
                indice="global"
                percentual={refHon.honorariosPercentual}
                valorFixo={refHon.honorariosValorFixo}
                base={refHon.honorariosBase}
                onChange={onHonorarios}
              />
            </div>
          ) : null}
        </div>
      </div>

      {multaFixaSoPrimeira || honFixaSoPrimeira ? (
        <p className="rounded border border-line bg-ink-50/60 px-3 py-2 text-[12px] text-ink-600">
          Valor fixo lançado uma única vez, no primeiro valor que compõe o total —
          sem multiplicar por cada linha.
        </p>
      ) : null}

      {baseConsolidada ? (
        <p className="rounded border border-line bg-ink-50/60 px-3 py-2 text-[12px] text-ink-600">
          Com mais de um valor, multa e honorários percentuais incidem sobre cada
          valor e são somados (podem diferir em centavos do total consolidado).
          O cálculo sobre base consolidada chega na próxima fase.
        </p>
      ) : null}
    </div>
  );
}

interface SecaoPagamentosProps {
  pagamentos: EstadoPagamentoVerba[];
  onAtualizar: (id: string, parcial: Partial<EstadoPagamentoVerba>) => void;
  onAdicionar: () => void;
  onRemover: (id: string) => void;
}

function SecaoPagamentos({
  pagamentos,
  onAtualizar,
  onAdicionar,
  onRemover,
}: SecaoPagamentosProps) {
  const [confirmando, setConfirmando] = useState<string | null>(null);

  return (
    <section className="border-t border-line pt-6" aria-labelledby="sec-pagamentos">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="section-kicker">Pagamentos</p>
          <h2 id="sec-pagamentos" className="section-title mt-1">
            Pagamentos e abatimentos
          </h2>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={onAdicionar}>
          + Adicionar pagamento
        </Button>
      </div>
      <p className="mt-3 max-w-[70ch] text-[13px] leading-relaxed text-ink-500">
        Cada pagamento abate o saldo atualizado. Na memória de cálculo eles
        aparecem lançados uma única vez, no primeiro valor que compõe o total —
        sem dupla subtração.
      </p>

      {pagamentos.length === 0 ? (
        <p className="mt-4 border border-dashed border-edge bg-paper px-4 py-6 text-center text-sm text-ink-500">
          Nenhum pagamento lançado. Use “+ Adicionar pagamento” quando houver
          abatimentos.
        </p>
      ) : (
        <div className="mt-4 border border-line bg-panel">
          <div className="hidden border-b border-line bg-ink-50 px-4 pb-2 pt-2.5 text-[11px] font-semibold uppercase tracking-legal text-ink-500 sm:grid sm:grid-cols-[9rem_9rem_minmax(0,1fr)_7.5rem] sm:gap-3">
            <span>Data</span>
            <span>Valor</span>
            <span>Descrição</span>
            <span className="text-right">Ações</span>
          </div>
          <ul>
            {pagamentos.map((pg, i) => (
              <li key={pg.id} className="border-b border-line px-4 py-3 last:border-b-0">
                <div className="grid gap-3 sm:grid-cols-[9rem_9rem_minmax(0,1fr)_7.5rem] sm:items-end">
                  <Input
                    id={`pgto-data-${pg.id}`}
                    label="Data"
                    type="date"
                    required
                    value={pg.data}
                    onChange={(e) => onAtualizar(pg.id, { data: e.target.value })}
                  />
                  <Input
                    id={`pgto-valor-${pg.id}`}
                    label="Valor"
                    inputMode="decimal"
                    required
                    placeholder="500,00"
                    value={pg.valor}
                    onChange={(e) => onAtualizar(pg.id, { valor: e.target.value })}
                  />
                  <Input
                    id={`pgto-descricao-${pg.id}`}
                    label="Descrição"
                    placeholder="Ex.: Pagamento parcial"
                    value={pg.descricao}
                    onChange={(e) =>
                      onAtualizar(pg.id, { descricao: e.target.value })
                    }
                  />
                  <div className="flex items-end">
                    {confirmando === pg.id ? (
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        aria-label={`Confirmar remoção do pagamento ${i + 1}`}
                        onClick={() => {
                          setConfirmando(null);
                          onRemover(pg.id);
                        }}
                      >
                        Confirmar
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Remover pagamento ${i + 1}`}
                        onClick={() => setConfirmando(pg.id)}
                      >
                        Remover
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export function FormCivel() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [identificacao, setIdentificacao] = useState<EstadoIdentificacao>({
    titulo: "",
    processo: "",
    parte: "",
  });
  const [dataBaseCalculo, setDataBaseCalculo] = useState("");
  const [indexador, setIndexador] = useState(INDEXADORES_CORRECAO[0].valor);
  const [verbas, setVerbas] = useState<EstadoVerba[]>(() => [novaVerba()]);
  const [pagamentos, setPagamentos] = useState<EstadoPagamentoVerba[]>([]);
  const [encargoConsolidado, setEncargoConsolidado] = useState<EstadoEncargoConsolidado>({
    ativo: false, tipo: "multa", percentual: "10", base: "corrigido",
  });
  const [revisaoDe, setRevisaoDe] = useState<string | null>(null);
  const [modo, setModo] = useState<ModoCalculo>(() =>
    params.get("modo") === "detalhado" ? "detalhado" : "simples",
  );
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [cobertura, setCobertura] = useState<CoberturaEfetiva | null>(null);
  const [idRascunho, setIdRascunho] = useState<string | null>(null);
  const [avisoRascunho, setAvisoRascunho] = useState<string | null>(null);
  const [confirmacaoCriterios, setConfirmacaoCriterios] = useState<
    AvisoCriterioDesativado[] | null
  >(null);

  useEffect(() => {
    const id = params.get("rascunho");
    if (!id) return;
    const rascunho = obterRascunho(id);
    if (!rascunho) return;
    setIdentificacao(rascunho.estado.identificacao);
    setDataBaseCalculo(rascunho.estado.dataBaseCalculo);
    setIndexador(rascunho.estado.indexador);
    setVerbas(rascunho.estado.verbas);
    setPagamentos(rascunho.estado.pagamentos ?? []);
    setEncargoConsolidado(rascunho.estado.encargoConsolidado ?? {
      ativo: false, tipo: "multa", percentual: "10", base: "corrigido",
    });
    setModo(rascunho.estado.modo ?? modo);
    setIdRascunho(rascunho.id);
    setAvisoRascunho("Rascunho reaberto com os dados como estavam.");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const codigoRevisao = params.get("revisar");
    if (!codigoRevisao) return;
    let ativo = true;
    api.obterCalculo(codigoRevisao).then((calculo) => {
      if (!ativo) return;
      const payload = calculo.payload;
      if (!payload || payload.tipo !== "parcelas" || !payload.verbas) {
        setErroEnvio("Este cálculo não possui um payload cível editável para revisão.");
        return;
      }
      const consolidados = payload.encargos_consolidados ?? [];
      if (consolidados.length > 1 || consolidados.some((e) => e.tipo === "juros" || e.valor_fixo || e.predecessores?.length)) {
        setErroEnvio("A revisão contém encargos consolidados que este formulário ainda não representa fielmente. Use o modo detalhado futuro; nenhum dado foi descartado.");
        return;
      }
      setIdentificacao({ titulo: payload.titulo, processo: payload.processo, parte: payload.parte });
      setDataBaseCalculo(payload.data_base);
      const pagamentosGlobais = (payload.pagamentos ?? []).map((pagamento, indice) => ({
        id: `pagamento-global-revisao-${indice}`,
        data: pagamento.data,
        valor: pagamento.valor,
        descricao: pagamento.descricao ?? "",
      }));
      const estadoHidratado = separarPagamentosDasVerbas(
        payload.verbas,
        pagamentosGlobais,
      );
      setVerbas(estadoHidratado.verbas);
      setPagamentos(estadoHidratado.pagamentos);
      const indexadorDaVerba = payload.verbas.find((v) => v.correcao?.indexador)?.correcao?.indexador;
      if (indexadorDaVerba) setIndexador(indexadorDaVerba);
      setRevisaoDe(calculo.codigo);
      const encargo = consolidados[0];
      if (encargo) {
        const componentes = encargo.componentes ?? [];
        const base = componentes.includes("juros_individuais") ? "com_juros" : componentes.includes("principal_corrigido") ? "corrigido" : "principal";
        setEncargoConsolidado({ ativo: true, tipo: encargo.tipo as "multa" | "honorarios", percentual: percentualParaTela(encargo.percentual), base });
      } else {
        setEncargoConsolidado({ ativo: false, tipo: "multa", percentual: "10", base: "corrigido" });
      }
      const detalhado = payload.verbas.some((v) => v.tipo === "percentual" || (v.regimes?.length ?? 0) > 0 || (v.parcelas?.length ?? 0) > 0);
      setModo(detalhado ? "detalhado" : "simples");
      setAvisoRascunho(`Revisão de ${calculo.codigo}: o original será preservado.`);
    }).catch((e) => { if (ativo) setErroEnvio(mensagemErroAmigavel(e)); });
    return () => { ativo = false; };
  }, [params]);

  useEffect(() => {
    let ativo = true;
    api
      .coberturaIndexador(indexador)
      .then((dados) => {
        if (ativo) setCobertura(dados);
      })
      .catch(() => {
        if (ativo) setCobertura(null);
      });
    return () => {
      ativo = false;
    };
  }, [indexador]);

  const aviso = useMemo(() => {
    if (!cobertura || !dataBaseCalculo) return null;
    if (!coberturaInsuficientePara(cobertura, dataBaseCalculo)) return null;

    const nome = cobertura.oficial.name;
    const oficialAte = cobertura.oficial.fim_rotulo;
    const efetivaAte = cobertura.cobertura_efetiva.fim_rotulo;
    const coberturaTexto =
      cobertura.cobertura_efetiva.inclui_manual && oficialAte !== efetivaAte
        ? `A série oficial vai até ${oficialAte} e há cadastros manuais até ${efetivaAte}.`
        : `A série está publicada até ${efetivaAte}.`;
    const competencia =
      rotuloCompetenciaExtenso(dataBaseCalculo) ?? formatarDataBR(dataBaseCalculo);

    return (
      `${nome}: falta o índice de ${competencia}. ${coberturaTexto} ` +
      `A data final pedida é ${formatarDataBR(dataBaseCalculo)}. O sistema não repete o índice ` +
      `do mês anterior nem inventa fator — só entram valores publicados ou cadastros oficiais ` +
      `registrados em Bases e Indexadores. Cadastre o índice de ${competencia} ou ajuste a data final.`
    );
  }, [cobertura, dataBaseCalculo]);

  function trocarIndexador(chave: string) {
    setIndexador(chave);
    setVerbas((atual) => atual.map((v) => ({ ...v, correcaoIndexador: chave })));
  }

  function atualizarVerba(id: string, parcial: Partial<EstadoVerba>) {
    setVerbas((atual) => atual.map((v) => (v.id === id ? { ...v, ...parcial } : v)));
    setErroRemocao(null);
  }

  function incluirVerba() {
    setErroRemocao(null);
    setVerbas((atual) => {
      // Se o controle simples já estiver ligado para todas as verbas, a nova
      // linha deve herdar esse critério. Sem isso, acrescentar uma verba após
      // ligar juros gerava silenciosamente `aplicar: false` apenas nela.
      const jurosEmTodas = atual.length > 0 && atual.every((v) => v.jurosAplicar);
      const referenciaJuros = atual.find((v) => v.jurosAplicar);
      return [
        ...atual,
        novaVerba({
          correcaoIndexador: indexador,
          jurosAplicar: jurosEmTodas,
          jurosModalidade: referenciaJuros?.jurosModalidade ?? "taxa_legal",
          jurosBase: referenciaJuros?.jurosBase ?? "corrigido",
        }),
      ];
    });
  }

  function removerVerba(id: string) {
    const bloqueio = podeRemoverVerba(id, verbas);
    if (!bloqueio.ok) {
      setErroRemocao(
        `${bloqueio.motivos.join("; ")}. Remova ou aponte outra base antes de excluir.`,
      );
      return false;
    }
    setErroRemocao(null);
    setVerbas((atual) => atual.filter((v) => v.id !== id));
    return true;
  }

  function alternarCorrecao(ligado: boolean) {
    setVerbas((atual) => aplicarEmTodas(atual, { correcaoAplicar: ligado }));
  }

  function alternarJuros(ligado: boolean) {
    setVerbas((atual) =>
      aplicarEmTodas(atual, {
        jurosAplicar: ligado,
        jurosModalidade: "taxa_legal",
      }),
    );
  }

  function definirJurosBase(base: string) {
    setVerbas((atual) => aplicarEmTodas(atual, { jurosBase: base }));
  }

  function atualizarMulta(parcial: Partial<ConfigEncargoGeral>) {
    setVerbas((atual) => {
      const ref = atual.find((v) => v.multaAplicar);
      return aplicarEncargoGeral(atual, "multa", {
        aplicar: ref?.multaAplicar ?? false,
        percentual: ref?.multaPercentual ?? "",
        valorFixo: ref?.multaValorFixo ?? "",
        base: ref?.multaBase ?? "corrigido",
        ...parcial,
      });
    });
  }

  function atualizarHonorarios(parcial: Partial<ConfigEncargoGeral>) {
    setVerbas((atual) => {
      const ref = atual.find((v) => v.honorariosAplicar);
      return aplicarEncargoGeral(atual, "honorarios", {
        aplicar: ref?.honorariosAplicar ?? false,
        percentual: ref?.honorariosPercentual ?? "",
        valorFixo: ref?.honorariosValorFixo ?? "",
        base: ref?.honorariosBase ?? "corrigido",
        ...parcial,
      });
    });
  }

  function atualizarPagamento(id: string, parcial: Partial<EstadoPagamentoVerba>) {
    setPagamentos((atual) =>
      atual.map((pg) => (pg.id === id ? { ...pg, ...parcial } : pg)),
    );
  }

  async function enviarCalculo() {
    setEnviando(true);
    try {
      const payload = montarPayload(
        identificacao,
        dataBaseCalculo,
        verbas,
        pagamentos,
        encargoConsolidado,
        revisaoDe,
      );
      const criado = await api.criarCalculo(payload);
      navigate(`/calculos/${encodeURIComponent(criado.codigo)}`);
    } catch (e) {
      setErroEnvio(mensagemErroAmigavel(e));
    } finally {
      setEnviando(false);
    }
  }

  function gerarCalculo() {
    setErros([]);
    setErroEnvio(null);
    const lista = errosValidacao(identificacao, dataBaseCalculo, verbas, pagamentos);
    const percentualConsolidado = Number(encargoConsolidado.percentual.replace(",", "."));
    if (encargoConsolidado.ativo && (!Number.isFinite(percentualConsolidado) || percentualConsolidado <= 0)) {
      lista.push("Informe um percentual positivo para o encargo consolidado.");
    }
    setErros(lista);
    if (lista.length > 0) return;
    const avisos = criteriosDesativados(verbas);
    if (avisos.length > 0) {
      setConfirmacaoCriterios(avisos);
      return;
    }
    void enviarCalculo();
  }

  function salvarRascunhoAtual() {
    const salvo = salvarRascunho(
      { identificacao, dataBaseCalculo, indexador, verbas, pagamentos, modo, encargoConsolidado },
      idRascunho,
    );
    setIdRascunho(salvo.id);
    setErros([]);
    setErroEnvio(null);
    setAvisoRascunho(
      `“${salvo.titulo}” salvo. Reabra em Rascunhos, na tela inicial.`,
    );
  }

  const simples = modo === "simples";

  return (
    <div className="mx-auto max-w-page space-y-8">
      <header className="border-b border-line pb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-kicker">Cálculo Cível</p>
            <h1 className="mt-2 text-[28px] leading-tight text-ink-950">Novo cálculo</h1>
            <p className="mt-2 max-w-[56ch] text-[14px] leading-relaxed text-ink-500">
              {simples
                ? "Preencha como em uma planilha: descrição, data e valor. A correção e os juros são aplicados automaticamente até a data final."
                : "Modo detalhado: cada lançamento decide suas próprias datas, correção, juros, multa e honorários."}
            </p>
          </div>
          <div
            role="group"
            aria-label="Modo do formulário"
            className="flex items-center gap-2"
          >
            <Button
              type="button"
              variant={simples ? "primary" : "outline"}
              size="sm"
              aria-pressed={simples}
              onClick={() => setModo("simples")}
            >
              Simples
            </Button>
            <Button
              type="button"
              variant={!simples ? "primary" : "outline"}
              size="sm"
              aria-pressed={!simples}
              onClick={() => setModo("detalhado")}
            >
              Detalhado
            </Button>
          </div>
        </div>
      </header>

      {erros.length > 0 ? (
        <Message tom="danger" title="Corrija antes de gerar">
          <ul className="list-disc space-y-1 pl-5">
            {erros.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </Message>
      ) : null}
      {avisoRascunho ? (
        <Message tom="success" title="Rascunho">
          {avisoRascunho}
        </Message>
      ) : null}
      {erroEnvio ? (
        <Message tom="danger" title="Falha no envio">
          {erroEnvio}
        </Message>
      ) : null}
      {aviso ? (
        <Message tom="warning" title="Data final sem índice publicado">
          {aviso}
        </Message>
      ) : null}

      <div className="sheet-panel">
        <div className="space-y-8 px-6 py-6 lg:px-8 lg:py-8">
          <section aria-labelledby="sec-identificacao">
            <SecaoIdentificacao
              valor={identificacao}
              onChange={(parcial) =>
                setIdentificacao((atual) => ({ ...atual, ...parcial }))
              }
            />
          </section>

          <section className="border-t border-line pt-6" aria-labelledby="sec-atualizacao">
            <div>
              <p className="section-kicker">Atualização</p>
              <h2 id="sec-atualizacao" className="section-title mt-1">
                Data final e correção
              </h2>
            </div>
            <div className="mt-4 grid gap-5 md:grid-cols-2 lg:max-w-2xl">
              <Input
                id="atualizar-ate"
                label="Atualizar cálculo até"
                required
                type="date"
                value={dataBaseCalculo}
                onChange={(e) => setDataBaseCalculo(e.target.value)}
                hint="Única data final do cálculo."
              />
              <Select
                id="indice-correcao"
                label="Correção monetária"
                required
                value={indexador}
                onChange={(e) => trocarIndexador(e.target.value)}
                hint="Aplicada automaticamente entre as datas informadas."
              >
                {INDEXADORES_CORRECAO.map((op) => (
                  <option key={op.valor} value={op.valor}>
                    {op.rotulo}
                  </option>
                ))}
              </Select>
            </div>
          </section>

          <section className="border-t border-line pt-6" aria-labelledby="sec-valores">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="section-kicker">Valores</p>
                <h2 id="sec-valores" className="section-title mt-1">
                  Lista de valores
                </h2>
              </div>
              {simples ? null : (
                <Button type="button" variant="secondary" size="sm" onClick={incluirVerba}>
                  + Adicionar valor
                </Button>
              )}
            </div>

            {erroRemocao ? (
              <div className="mt-4">
                <Message tom="warning" title="Não foi possível remover">
                  {erroRemocao}
                </Message>
              </div>
            ) : null}

            {verbas.length === 0 ? (
              <div className="mt-5">
                <p className="border border-dashed border-edge bg-paper px-4 py-8 text-center text-sm text-ink-500">
                  Nenhum valor lançado. Use “+ Adicionar valor”.
                </p>
                {simples ? (
                  <div className="mt-4">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={incluirVerba}
                    >
                      + Adicionar valor
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : simples ? (
              <ModoSimples
                verbas={verbas}
                onAtualizar={atualizarVerba}
                onAdicionar={incluirVerba}
                onRemover={removerVerba}
                onEditarDetalhado={() => setModo("detalhado")}
              />
            ) : (
              <div className="mt-5 border border-line bg-panel">
                <div
                  className={`hidden border-b border-line bg-ink-50 px-4 pb-2 pt-2.5 text-[11px] font-semibold uppercase tracking-legal text-ink-500 lg:grid ${COLUNAS_LANCAMENTO}`}
                >
                  <span>Correção desde</span>
                  <span>Juros desde</span>
                  <span>Valor</span>
                  <span>Descrição</span>
                  <span className="text-right">Ações</span>
                </div>
                <ul>
                  {verbas.map((verba, indice) => (
                    <LinhaValor
                      key={verba.id}
                      verba={verba}
                      indice={indice}
                      verbas={verbas}
                      onChange={(parcial) => atualizarVerba(verba.id, parcial)}
                      onRemover={() => removerVerba(verba.id)}
                    />
                  ))}
                </ul>
              </div>
            )}

            {simples ? (
              <p className="mt-3 max-w-[70ch] text-xs leading-relaxed text-ink-500">
                A data de cada valor define o início da correção e dos juros. A
                correção usa a Tabela Prática TJSP e os juros usam a Taxa Legal
                (BCB SGS 29543), automáticos até a data final — sem fatores ou
                percentuais para digitar. Detalhes por lançamento (regras de
                atualização, composição do total, verbas derivadas) ficam no modo
                detalhado.
              </p>
            ) : (
              <p className="mt-3 text-xs text-ink-500">
                Cada lançamento decide sozinho o que atualiza: marque Correção
                monetária e/ou Juros e informe a data de cada um — os dois podem
                ficar desligados. A correção usa a Tabela Prática TJSP e os juros
                usam a Taxa Legal (BCB SGS 29543), automáticos até a data final —
                sem fatores ou percentuais para digitar.
              </p>
            )}
          </section>

          {simples ? (
            <section className="border-t border-line pt-6" aria-labelledby="sec-encargos">
              <div>
                <p className="section-kicker">Encargos</p>
                <h2 id="sec-encargos" className="section-title mt-1">
                  Correção, juros, multa e honorários
                </h2>
              </div>
              <SecaoEncargos
                verbas={verbas}
                onAlternarCorrecao={alternarCorrecao}
                onAlternarJuros={alternarJuros}
                onJurosBase={definirJurosBase}
                onMulta={atualizarMulta}
                onHonorarios={atualizarHonorarios}
              />
              <div className="mt-4 rounded-xl border border-line bg-ink-50/60 p-4">
                <Switch
                  id="encargo-consolidado"
                  label="Encargo único sobre o total"
                  description="Calcula multa ou honorários uma única vez, depois de somar as verbas selecionadas."
                  checked={encargoConsolidado.ativo}
                  onChange={(ativo) => setEncargoConsolidado((atual) => ({ ...atual, ativo }))}
                  disabled={verbas.length === 0}
                />
                {encargoConsolidado.ativo ? (
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <Select id="encargo-consolidado-tipo" label="Tipo" value={encargoConsolidado.tipo} onChange={(e) => setEncargoConsolidado((atual) => ({ ...atual, tipo: e.target.value as EstadoEncargoConsolidado["tipo"] }))}>
                      <option value="multa">Multa</option>
                      <option value="honorarios">Honorários</option>
                    </Select>
                    <Input id="encargo-consolidado-percentual" label="Percentual (%)" inputMode="decimal" value={encargoConsolidado.percentual} onChange={(e) => setEncargoConsolidado((atual) => ({ ...atual, percentual: e.target.value }))} />
                    <Select id="encargo-consolidado-base" label="Base" value={encargoConsolidado.base} onChange={(e) => setEncargoConsolidado((atual) => ({ ...atual, base: e.target.value as EstadoEncargoConsolidado["base"] }))}>
                      <option value="principal">Valores originais</option>
                      <option value="corrigido">Valores corrigidos</option>
                      <option value="com_juros">Corrigidos + juros</option>
                    </Select>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          <SecaoPagamentos
            pagamentos={pagamentos}
            onAtualizar={atualizarPagamento}
            onAdicionar={() =>
              setPagamentos((atual) => [...atual, novaPagamento()])
            }
            onRemover={(id) =>
              setPagamentos((atual) => atual.filter((pg) => pg.id !== id))
            }
          />
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-line px-6 py-5 lg:px-8">
          <Button type="button" size="lg" onClick={gerarCalculo} disabled={enviando}>
            {enviando ? "Gerando…" : "Gerar cálculo"}
          </Button>
          <Button type="button" variant="outline" onClick={salvarRascunhoAtual}>
            Salvar rascunho
          </Button>
          <span className="text-[13px] text-ink-500">
            “Salvar rascunho” guarda o formulário incompleto sem validar; “Gerar
            cálculo” abre a memória com tabela, PDF e XLSX.
          </span>
        </div>
        {confirmacaoCriterios ? (
          <div className="border-t border-line bg-amber-50 px-6 py-5 lg:px-8" role="alertdialog" aria-labelledby="confirmacao-criterios-titulo">
            <p id="confirmacao-criterios-titulo" className="font-semibold text-amber-950">
              Confirmar critérios desativados
            </p>
            <p className="mt-1 text-sm text-amber-900">
              As configurações abaixo não serão aplicadas. Deseja mantê-las?
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-950">
              {confirmacaoCriterios.map((aviso) => (
                <li key={`${aviso.verba}-${aviso.criterio}`}>
                  {aviso.verba}: {aviso.criterio} {aviso.criterio === "juros" ? "desativados" : "desativada"}.
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button
                type="button"
                onClick={() => {
                  setConfirmacaoCriterios(null);
                  void enviarCalculo();
                }}
                disabled={enviando}
              >
                Manter configurações e calcular
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setConfirmacaoCriterios(null)}
                disabled={enviando}
              >
                Voltar e revisar
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
