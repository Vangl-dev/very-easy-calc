import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SecaoEncargos, encargoVazio, type EstadoEncargos } from "./SecaoEncargos";
import { SecaoIdentificacao, type EstadoIdentificacao } from "./SecaoIdentificacao";
import { SecaoPagamentos, type EstadoPagamento } from "./SecaoPagamentos";
import { SecaoValorDatas, type EstadoValorDatas } from "./SecaoValorDatas";
import {
  CampoResumo,
  CabecalhoFormulario,
  CartaoRevisao,
  type Passo,
} from "./FluxoFormulario";
import { ResultadoSucesso } from "./ResultadoSucesso";
import { api, formatarDataHora, mensagemErroAmigavel } from "../../lib/api";
import { coberturaInsuficientePara } from "../../lib/cobertura";
import type {
  CalculoCivelPayload,
  CalculoCriado,
  CoberturaEfetiva,
  PagamentoPayload,
} from "../../types/api";

function errosValidacao(estado: {
  identificacao: EstadoIdentificacao;
  valorDatas: EstadoValorDatas;
  encargos: EstadoEncargos;
  pagamentos: EstadoPagamento[];
}): string[] {
  const erros: string[] = [];
  if (!estado.identificacao.titulo.trim()) {
    erros.push("Informe o nome/descrição do cálculo.");
  }
  if (!estado.valorDatas.valorBase.trim()) {
    erros.push("Informe o valor-base/principal.");
  }
  if (!estado.valorDatas.dataBase) {
    erros.push("Informe a data-base do valor.");
  }
  if (!estado.valorDatas.dataFinal) {
    erros.push("Informe a data-final de atualização.");
  }
  if (
    estado.valorDatas.dataBase &&
    estado.valorDatas.dataFinal &&
    estado.valorDatas.dataFinal < estado.valorDatas.dataBase
  ) {
    erros.push("A data-final não pode ser anterior à data-base.");
  }

  const { multa, honorarios } = estado.encargos;
  for (const [nome, encargo] of [
    ["multa", multa],
    ["honorários", honorarios],
  ] as const) {
    if (!encargo.aplicar) continue;
    const temPercentual = encargo.percentual.trim() !== "";
    const temValor = encargo.valorFixo.trim() !== "";
    if (temPercentual && temValor) {
      erros.push(`Em ${nome}, informe percentual OU valor fixo — não ambos.`);
    }
    if (!temPercentual && !temValor) {
      erros.push(`Em ${nome} aplicado, informe percentual ou valor fixo.`);
    }
  }

  estado.pagamentos.forEach((pg, indice) => {
    if (!pg.data) erros.push(`Pagamento ${indice + 1}: informe a data.`);
    if (!pg.valor.trim()) erros.push(`Pagamento ${indice + 1}: informe o valor.`);
  });

  return erros;
}

function montarPayload(estado: {
  identificacao: EstadoIdentificacao;
  valorDatas: EstadoValorDatas;
  encargos: EstadoEncargos;
  pagamentos: EstadoPagamento[];
}): CalculoCivelPayload {
  const { identificacao, valorDatas, encargos, pagamentos } = estado;

  const pagamentosParcela: PagamentoPayload[] = pagamentos
    .filter((pg) => pg.data && pg.valor.trim())
    .map((pg) => ({
      data: pg.data,
      valor: pg.valor.trim(),
      descricao: (pg.descricao ?? "").trim(),
    }));

  return {
    tipo: "parcelas",
    titulo: identificacao.titulo.trim(),
    processo: identificacao.processo.trim(),
    parte: identificacao.parte.trim(),
    data_base: valorDatas.dataFinal,
    parcelas: [
      {
        numero: 1,
        vencimento: valorDatas.dataBase,
        principal: valorDatas.valorBase.trim(),
        descricao: "Valor-base do cálculo cível",
        pagamentos: pagamentosParcela,
      },
    ],
    correcao: {
      aplicar: encargos.correcao.aplicar,
      indexador: encargos.correcao.indexador,
      termo_final: valorDatas.dataFinal,
    },
    juros: {
      aplicar: encargos.juros.aplicar,
      modalidade: encargos.juros.modalidade,
      base: encargos.juros.base,
      unidade: encargos.juros.unidade,
    },
    multa: {
      aplicar: encargos.multa.aplicar,
      percentual: encargos.multa.percentual.trim() || null,
      valor_fixo: encargos.multa.valorFixo.trim() || null,
      base: encargos.multa.base,
    },
    honorarios: {
      aplicar: encargos.honorarios.aplicar,
      percentual: encargos.honorarios.percentual.trim() || null,
      valor_fixo: encargos.honorarios.valorFixo.trim() || null,
      base: encargos.honorarios.base,
    },
    pagamentos: [],
  };
}

export function FormCivel() {
  const [identificacao, setIdentificacao] = useState<EstadoIdentificacao>({
    titulo: "",
    processo: "",
    parte: "",
  });
  const [valorDatas, setValorDatas] = useState<EstadoValorDatas>({
    valorBase: "",
    dataBase: "",
    dataFinal: "",
  });
  const [encargos, setEncargos] = useState<EstadoEncargos>({
    correcao: { aplicar: true, indexador: "tjsp_tabela_pratica" },
    juros: encargoVazio(false),
    multa: encargoVazio(false),
    honorarios: encargoVazio(false),
  });
  const [pagamentos, setPagamentos] = useState<EstadoPagamento[]>([]);
  const [passo, setPasso] = useState<Passo>("formulario");
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<CalculoCriado | null>(null);
  const [cobertura, setCobertura] = useState<CoberturaEfetiva | null>(null);

  useEffect(() => {
    if (!encargos.correcao.aplicar) {
      setCobertura(null);
      return;
    }
    let ativo = true;
    api
      .coberturaIndexador(encargos.correcao.indexador)
      .then((dados) => {
        if (ativo) setCobertura(dados);
      })
      .catch(() => {
        if (ativo) setCobertura(null);
      });
    return () => {
      ativo = false;
    };
  }, [encargos.correcao.aplicar, encargos.correcao.indexador]);

  const avisosDatas = useMemo(() => {
    const lista: string[] = [];
    if (!valorDatas.dataFinal || !valorDatas.dataBase) return lista;
    if (valorDatas.dataFinal < valorDatas.dataBase) {
      lista.push(
        "A data-final informada é anterior à data-base. Ajuste antes de continuar.",
      );
    }
    if (
      encargos.correcao.aplicar &&
      cobertura &&
      valorDatas.dataFinal &&
      coberturaInsuficientePara(cobertura, valorDatas.dataFinal)
    ) {
      lista.push(
        `A cobertura oficial de ${cobertura.oficial.name} termina em ` +
          `${cobertura.cobertura_efetiva.fim_rotulo}. ` +
          `A data-final ${valorDatas.dataFinal} está além dessa série — o backend pode retornar cobertura_insuficiente.`,
      );
    }
    return lista;
  }, [
    valorDatas.dataBase,
    valorDatas.dataFinal,
    encargos.correcao.aplicar,
    cobertura,
  ]);

  function reiniciar() {
    setIdentificacao({ titulo: "", processo: "", parte: "" });
    setValorDatas({ valorBase: "", dataBase: "", dataFinal: "" });
    setEncargos({
      correcao: { aplicar: true, indexador: "tjsp_tabela_pratica" },
      juros: encargoVazio(false),
      multa: encargoVazio(false),
      honorarios: encargoVazio(false),
    });
    setPagamentos([]);
    setErros([]);
    setErroEnvio(null);
    setResultado(null);
    setPasso("formulario");
  }

  async function enviar() {
    setEnviando(true);
    setErroEnvio(null);
    try {
      const payload = montarPayload({ identificacao, valorDatas, encargos, pagamentos });
      const criado = await api.criarCalculo(payload);
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
        eyebrow="Cálculo Cível"
        titulo="Novo cálculo"
        descricao="O React apenas coleta e envia os dados para POST /api/calculos. Toda a matemática (correção, juros, encargos) é executada no backend."
        dica="Datas passadas e futuras são permitidas. A data-final é sempre a que você escolher — não há preenchimento automático com 'hoje'."
      />

      {passo === "sucesso" && resultado ? (
        <ResultadoSucesso resultado={resultado} onReiniciar={reiniciar} />
      ) : null}

      {passo === "formulario" ? (
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            const lista = errosValidacao({
              identificacao,
              valorDatas,
              encargos,
              pagamentos,
            });
            setErros(lista);
            setErroEnvio(null);
            if (lista.length === 0) setPasso("revisao");
          }}
        >
          <Card>
            <div className="space-y-8">
              <SecaoIdentificacao
                valor={identificacao}
                onChange={(parcial) =>
                  setIdentificacao((atual) => ({ ...atual, ...parcial }))
                }
              />
              <SecaoValorDatas
                valor={valorDatas}
                onChange={(parcial) =>
                  setValorDatas((atual) => ({ ...atual, ...parcial }))
                }
                avisos={avisosDatas}
              />
              <SecaoEncargos
                valor={encargos}
                onChange={(parcial) =>
                  setEncargos((atual) => ({ ...atual, ...parcial }))
                }
                jurosDisponiveis={Boolean(cobertura)}
              />
              <SecaoPagamentos pagamentos={pagamentos} onChange={setPagamentos} />
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
          <dl className="grid gap-3 sm:grid-cols-2">
            <CampoResumo rotulo="Título" valor={identificacao.titulo || "—"} />
            <CampoResumo rotulo="Processo" valor={identificacao.processo || "—"} />
            <CampoResumo rotulo="Parte" valor={identificacao.parte || "—"} />
            <CampoResumo
              rotulo="Valor-base"
              valor={
                <span className="font-mono">{valorDatas.valorBase || "—"}</span>
              }
            />
            <CampoResumo
              rotulo="Data-base"
              valor={
                <span className="font-mono">{valorDatas.dataBase || "—"}</span>
              }
            />
            <CampoResumo
              rotulo="Data-final"
              valor={
                <span className="font-mono">{valorDatas.dataFinal || "—"}</span>
              }
            />
            <CampoResumo
              rotulo="Correção monetária"
              valor={
                encargos.correcao.aplicar
                  ? `Sim — ${encargos.correcao.indexador}`
                  : "Não aplicada"
              }
            />
            <CampoResumo
              rotulo="Juros"
              valor={
                encargos.juros.aplicar
                  ? `Sim — ${encargos.juros.modalidade}`
                  : "Não aplicados"
              }
            />
            <CampoResumo
              rotulo="Multa"
              valor={
                encargos.multa.aplicar
                  ? encargos.multa.percentual
                    ? `${encargos.multa.percentual} (${encargos.multa.base})`
                    : `${encargos.multa.valorFixo} (${encargos.multa.base})`
                  : "Não aplicada"
              }
            />
            <CampoResumo
              rotulo="Honorários"
              valor={
                encargos.honorarios.aplicar
                  ? encargos.honorarios.percentual
                    ? `${encargos.honorarios.percentual} (${encargos.honorarios.base})`
                    : `${encargos.honorarios.valorFixo} (${encargos.honorarios.base})`
                  : "Não aplicados"
              }
            />
          </dl>
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-ink-900">Pagamentos</h3>
            {pagamentos.filter((p) => p.data && p.valor).length === 0 ? (
              <p className="mt-1 text-sm text-ink-500">Nenhum pagamento.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm text-ink-800">
                {pagamentos
                  .filter((p) => p.data && p.valor)
                  .map((p) => (
                    <li key={p.id}>
                      {formatarDataHora(`${p.data}T12:00:00`)} — {p.valor}
                      {p.descricao ? ` (${p.descricao})` : ""}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </CartaoRevisao>
      ) : null}
    </div>
  );
}
