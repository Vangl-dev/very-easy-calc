import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import { Tooltip } from "../../components/ui/Tooltip";
import { SecaoIdentificacao, type EstadoIdentificacao } from "./SecaoIdentificacao";
import {
  CampoResumo,
  CabecalhoFormulario,
  CartaoRevisao,
  type Passo,
} from "./FluxoFormulario";
import { ResultadoSucesso } from "./ResultadoSucesso";
import { api, mensagemErroAmigavel } from "../../lib/api";
import { coberturaInsuficientePara } from "../../lib/cobertura";
import type {
  CalculoAtualizacaoPayload,
  CalculoCriado,
  CoberturaEfetiva,
} from "../../types/api";

interface EstadoAtualizacao {
  identificacao: EstadoIdentificacao;
  valorBase: string;
  dataBase: string;
  dataFinal: string;
  descricaoValor: string;
  correcaoAplicar: boolean;
  indexador: string;
}

function estadoInicial(): EstadoAtualizacao {
  return {
    identificacao: { titulo: "", processo: "", parte: "" },
    valorBase: "",
    dataBase: "",
    dataFinal: "",
    descricaoValor: "",
    correcaoAplicar: true,
    indexador: "tjsp_tabela_pratica",
  };
}

function errosValidacao(estado: EstadoAtualizacao): string[] {
  const erros: string[] = [];
  if (!estado.identificacao.titulo.trim()) {
    erros.push("Informe o nome/descrição do cálculo.");
  }
  if (!estado.valorBase.trim()) {
    erros.push("Informe o valor-base.");
  }
  if (!estado.dataBase) {
    erros.push("Informe a data-base do valor.");
  }
  if (!estado.dataFinal) {
    erros.push("Informe a data-final de atualização.");
  }
  if (
    estado.dataBase &&
    estado.dataFinal &&
    estado.dataFinal < estado.dataBase
  ) {
    erros.push("A data-final não pode ser anterior à data-base.");
  }
  return erros;
}

function montarPayload(estado: EstadoAtualizacao): CalculoAtualizacaoPayload {
  return {
    tipo: "atualizacao",
    titulo: estado.identificacao.titulo.trim(),
    processo: estado.identificacao.processo.trim(),
    parte: estado.identificacao.parte.trim(),
    data_base: estado.dataFinal,
    data_final: estado.dataFinal,
    valor_base: {
      valor: estado.valorBase.trim(),
      data_base: estado.dataBase,
      descricao: estado.descricaoValor.trim(),
    },
    correcao: {
      aplicar: estado.correcaoAplicar,
      indexador: estado.indexador,
      termo_final: estado.dataFinal,
    },
    juros: { aplicar: false },
    multa: { aplicar: false },
    honorarios: { aplicar: false },
  };
}

export function FormAtualizacao() {
  const [estado, setEstado] = useState<EstadoAtualizacao>(estadoInicial);
  const [passo, setPasso] = useState<Passo>("formulario");
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<CalculoCriado | null>(null);
  const [cobertura, setCobertura] = useState<CoberturaEfetiva | null>(null);

  useEffect(() => {
    if (!estado.correcaoAplicar) {
      setCobertura(null);
      return;
    }
    let ativo = true;
    api
      .coberturaIndexador(estado.indexador)
      .then((dados) => {
        if (ativo) setCobertura(dados);
      })
      .catch(() => {
        if (ativo) setCobertura(null);
      });
    return () => {
      ativo = false;
    };
  }, [estado.correcaoAplicar, estado.indexador]);

  const avisos = useMemo(() => {
    const lista: string[] = [];
    if (estado.dataBase && estado.dataFinal && estado.dataFinal < estado.dataBase) {
      lista.push(
        "A data-final é anterior à data-base do valor. Ajuste antes de continuar.",
      );
    }
    if (
      estado.correcaoAplicar &&
      cobertura &&
      estado.dataFinal &&
      coberturaInsuficientePara(cobertura, estado.dataFinal)
    ) {
      lista.push(
        `A cobertura de ${cobertura.oficial.name} termina em ` +
          `${cobertura.cobertura_efetiva.fim_rotulo}. ` +
          `A data-final ${estado.dataFinal} está além dessa série — o backend pode retornar cobertura_insuficiente.`,
      );
    }
    return lista;
  }, [
    estado.dataBase,
    estado.dataFinal,
    estado.correcaoAplicar,
    cobertura,
  ]);

  function atualizar(parcial: Partial<EstadoAtualizacao>) {
    setEstado((atual) => ({ ...atual, ...parcial }));
  }

  function reiniciar() {
    setEstado(estadoInicial());
    setErros([]);
    setErroEnvio(null);
    setResultado(null);
    setPasso("formulario");
  }

  async function enviar() {
    setEnviando(true);
    setErroEnvio(null);
    try {
      const criado = await api.criarCalculo(montarPayload(estado));
      setResultado(criado);
      setPasso("sucesso");
    } catch (e) {
      setErroEnvio(mensagemErroAmigavel(e));
      setPasso("revisao");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-6">
      <CabecalhoFormulario
        eyebrow="Atualização monetária"
        titulo="Valor-base → data-final"
        descricao="Fluxo próprio para atualizar um valor nominal até a data escolhida. O React apenas coleta e envia; fatores e correção são calculados no backend."
        dica="Datas passadas e futuras são permitidas. A data-final nunca é preenchida automaticamente com a data de hoje."
      />

      {passo === "sucesso" && resultado ? (
        <ResultadoSucesso resultado={resultado} onReiniciar={reiniciar} />
      ) : null}

      {passo === "formulario" ? (
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            const lista = errosValidacao(estado);
            setErros(lista);
            setErroEnvio(null);
            if (lista.length === 0) setPasso("revisao");
          }}
        >
          <Card>
            <div className="space-y-8">
              <SecaoIdentificacao
                valor={estado.identificacao}
                onChange={(parcial) =>
                  atualizar({
                    identificacao: { ...estado.identificacao, ...parcial },
                  })
                }
              />

              <section className="space-y-4" aria-labelledby="sec-valor-atual">
                <div className="flex items-center gap-2">
                  <h2
                    id="sec-valor-atual"
                    className="text-base font-semibold text-ink-900"
                  >
                    2. Valor e datas de atualização
                  </h2>
                  <Tooltip text="Informe o valor original e as duas datas. O backend aplica o índice oficial entre a data-base e a data-final — sem fatores no React." />
                </div>

                <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900">
                  <p className="font-medium">
                    Valor em{" "}
                    <span className="font-mono">
                      {estado.dataBase || "[data-base]"}
                    </span>{" "}
                    → atualizar até{" "}
                    <span className="font-mono">
                      {estado.dataFinal || "[data-final]"}
                    </span>
                  </p>
                  {estado.valorBase ? (
                    <p className="mt-1 text-xs text-brand-800">
                      Valor-base informado:{" "}
                      <span className="font-mono font-semibold">
                        {estado.valorBase}
                      </span>
                    </p>
                  ) : null}
                </div>

                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <Input
                    id="atual-valor"
                    label="Valor-base"
                    required
                    inputMode="decimal"
                    value={estado.valorBase}
                    onChange={(e) => atualizar({ valorBase: e.target.value })}
                    placeholder="10000,00"
                    tooltip="Valor original (causa, contrato, dano). Enviado como texto para conversão Decimal no backend."
                  />
                  <Input
                    id="atual-data-base"
                    label="Data-base do valor"
                    required
                    type="date"
                    value={estado.dataBase}
                    onChange={(e) => atualizar({ dataBase: e.target.value })}
                    tooltip="Data em que o valor-base foi fixado. Pode ser no passado."
                  />
                  <Input
                    id="atual-data-final"
                    label="Data-final"
                    required
                    type="date"
                    value={estado.dataFinal}
                    onChange={(e) => atualizar({ dataFinal: e.target.value })}
                    tooltip="Data até a qual deseja atualizar. Você escolhe — não é sempre hoje."
                  />
                  <Input
                    id="atual-descricao"
                    label="Descrição do valor"
                    value={estado.descricaoValor}
                    onChange={(e) => atualizar({ descricaoValor: e.target.value })}
                    placeholder="Valor da causa"
                    className="md:col-span-2 lg:col-span-3"
                  />
                </div>

                {avisos.map((aviso) => (
                  <p
                    key={aviso}
                    className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
                  >
                    {aviso}
                  </p>
                ))}
              </section>

              <section className="space-y-3" aria-labelledby="sec-correcao-atual">
                <div className="flex items-center gap-2">
                  <h2
                    id="sec-correcao-atual"
                    className="text-base font-semibold text-ink-900"
                  >
                    3. Correção monetária
                  </h2>
                  <Tooltip text="Se desativada, o valor-base é mantido como informado. Se ativada, o backend usa a série oficial do indexador entre as datas." />
                </div>
                <Switch
                  id="atual-correcao"
                  checked={estado.correcaoAplicar}
                  onChange={(correcaoAplicar) => atualizar({ correcaoAplicar })}
                  label="Aplicar correção monetária"
                  description="Consulta o indexador oficial no backend. Sem correção, apenas o valor-base é registrado."
                />
                {estado.correcaoAplicar ? (
                  <Select
                    id="atual-indexador"
                    label="Indexador"
                    value={estado.indexador}
                    onChange={(e) => atualizar({ indexador: e.target.value })}
                    tooltip="Série versionada no backend (Tabela Prática TJSP). O frontend não aplica fatores."
                  >
                    <option value="tjsp_tabela_pratica">
                      Tabela Prática TJSP (correção monetária)
                    </option>
                  </Select>
                ) : (
                  <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
                    Correção monetária <strong>não aplicada</strong>.
                  </p>
                )}
                {cobertura && estado.correcaoAplicar ? (
                  <p className="text-xs text-ink-500">
                    Cobertura informada: {cobertura.oficial.name} ·{" "}
                    {cobertura.cobertura_efetiva.inicio_rotulo} a{" "}
                    {cobertura.cobertura_efetiva.fim_rotulo}
                    {cobertura.cobertura_efetiva.inclui_manual
                      ? " (inclui cadastros manuais)"
                      : ""}
                  </p>
                ) : null}
              </section>
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-ink-100 pt-5">
              <Button type="submit" size="lg">
                Revisar dados
              </Button>
              <Button type="button" variant="ghost" onClick={reiniciar}>
                Limpar formulário
              </Button>
            </div>
          </Card>
        </form>
      ) : null}

      {passo === "revisao" ? (
        <CartaoRevisao
          erros={erros}
          erroEnvio={erroEnvio}
          enviando={enviando}
          onVoltar={() => {
            setPasso("formulario");
            setErroEnvio(null);
          }}
          onEnviar={enviar}
        >
          <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900">
            <p className="font-medium">
              Valor em{" "}
              <span className="font-mono">{estado.dataBase || "—"}</span> →
              atualizar até <span className="font-mono">{estado.dataFinal || "—"}</span>
            </p>
          </div>
          <dl className="grid gap-3 sm:grid-cols-2">
            <CampoResumo
              rotulo="Título"
              valor={estado.identificacao.titulo || "—"}
            />
            <CampoResumo
              rotulo="Processo"
              valor={estado.identificacao.processo || "—"}
            />
            <CampoResumo rotulo="Parte" valor={estado.identificacao.parte || "—"} />
            <CampoResumo
              rotulo="Valor-base"
              valor={<span className="font-mono">{estado.valorBase || "—"}</span>}
            />
            <CampoResumo
              rotulo="Data-base"
              valor={<span className="font-mono">{estado.dataBase || "—"}</span>}
            />
            <CampoResumo
              rotulo="Data-final"
              valor={<span className="font-mono">{estado.dataFinal || "—"}</span>}
            />
            <CampoResumo
              rotulo="Descrição"
              valor={estado.descricaoValor || "—"}
            />
            <CampoResumo
              rotulo="Correção monetária"
              valor={
                estado.correcaoAplicar
                  ? `Sim — ${estado.indexador}`
                  : "Não aplicada"
              }
            />
          </dl>
        </CartaoRevisao>
      ) : null}
    </div>
  );
}
