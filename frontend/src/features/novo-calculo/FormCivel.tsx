import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Form";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";
import {
  CardVerba,
  montarPagamentosVerba,
  novaVerba,
  type EstadoVerba,
} from "./CardVerba";
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
  CalculoCivelPayload,
  CalculoCriado,
  CoberturaEfetiva,
  VerbaPayload,
} from "../../types/api";

function errosValidacao(
  identificacao: EstadoIdentificacao,
  dataBaseCalculo: string,
  verbas: EstadoVerba[],
): string[] {
  const erros: string[] = [];
  if (!identificacao.titulo.trim()) {
    erros.push("Informe o nome/descrição do cálculo.");
  }
  if (!dataBaseCalculo) {
    erros.push("Informe a data-base do cálculo (referência).");
  }
  if (verbas.length === 0) {
    erros.push("Adicione ao menos uma verba.");
  }
  verbas.forEach((verba, indice) => {
    const rotulo = `Verba ${indice + 1}`;
    if (!verba.nome.trim()) erros.push(`${rotulo}: informe o nome.`);
    if (!verba.valor.trim()) erros.push(`${rotulo}: informe o valor.`);
    if (!verba.dataBase) erros.push(`${rotulo}: informe a data-base/vencimento.`);
    if (
      verba.correcaoAplicar &&
      verba.correcaoInicio &&
      verba.correcaoFim &&
      verba.correcaoFim < verba.correcaoInicio
    ) {
      erros.push(`${rotulo}: fim da correção anterior ao início.`);
    }
    if (
      verba.jurosAplicar &&
      verba.jurosInicio &&
      verba.jurosFim &&
      verba.jurosFim < verba.jurosInicio
    ) {
      erros.push(`${rotulo}: fim dos juros anterior ao início.`);
    }
    if (verba.jurosAplicar && verba.jurosModalidade === "fixa" && !verba.jurosTaxa.trim()) {
      erros.push(`${rotulo}: informe a taxa de juros (modalidade fixa).`);
    }
    for (const [nome, pct, valorFixo] of [
      ["multa", verba.multaPercentual, verba.multaValorFixo],
      ["honorários", verba.honorariosPercentual, verba.honorariosValorFixo],
    ] as const) {
      const temPct = pct.trim() !== "";
      const temValor = valorFixo.trim() !== "";
      if (nome === "multa" && !verba.multaAplicar) continue;
      if (nome === "honorários" && !verba.honorariosAplicar) continue;
      if (temPct && temValor) {
        erros.push(`${rotulo}: em ${nome}, informe % OU valor fixo.`);
      }
      if (!temPct && !temValor) {
        erros.push(`${rotulo}: em ${nome}, informe % ou valor fixo.`);
      }
    }
    verba.pagamentos.forEach((pg, i) => {
      if (!pg.data) erros.push(`${rotulo}: pagamento ${i + 1} sem data.`);
      if (!pg.valor.trim()) erros.push(`${rotulo}: pagamento ${i + 1} sem valor.`);
    });
  });
  return erros;
}

function montarVerbaPayload(verba: EstadoVerba): VerbaPayload {
  return {
    nome: verba.nome.trim(),
    valor: verba.valor.trim(),
    data_base: verba.dataBase,
    descricao: verba.descricao.trim(),
    correcao: {
      aplicar: verba.correcaoAplicar,
      indexador: verba.correcaoIndexador,
      termo_inicial: verba.correcaoInicio || verba.dataBase || null,
      termo_final: verba.correcaoFim || null,
    },
    juros: {
      aplicar: verba.jurosAplicar,
      modalidade: verba.jurosModalidade,
      taxa: verba.jurosModalidade === "fixa" ? verba.jurosTaxa.trim() || null : null,
      unidade: "mensal",
      base: verba.jurosBase,
      inicio: verba.jurosInicio || verba.dataBase || null,
      fim: verba.jurosFim || null,
    },
    multa: {
      aplicar: verba.multaAplicar,
      percentual: verba.multaPercentual.trim() || null,
      valor_fixo: verba.multaValorFixo.trim() || null,
      base: verba.multaBase,
    },
    honorarios: {
      aplicar: verba.honorariosAplicar,
      percentual: verba.honorariosPercentual.trim() || null,
      valor_fixo: verba.honorariosValorFixo.trim() || null,
      base: verba.honorariosBase,
    },
    pagamentos: montarPagamentosVerba(verba.pagamentos),
    parcelas: [],
  };
}

function montarPayload(
  identificacao: EstadoIdentificacao,
  dataBaseCalculo: string,
  verbas: EstadoVerba[],
): CalculoCivelPayload {
  return {
    tipo: "parcelas",
    titulo: identificacao.titulo.trim(),
    processo: identificacao.processo.trim(),
    parte: identificacao.parte.trim(),
    data_base: dataBaseCalculo,
    verbas: verbas.map(montarVerbaPayload),
    correcao: { aplicar: false },
    juros: { aplicar: false },
    multa: { aplicar: false },
    honorarios: { aplicar: false },
    pagamentos: [],
  };
}

function rotuloData(iso: string): string {
  return iso || "—";
}

export function FormCivel() {
  const [identificacao, setIdentificacao] = useState<EstadoIdentificacao>({
    titulo: "",
    processo: "",
    parte: "",
  });
  const [dataBaseCalculo, setDataBaseCalculo] = useState("");
  const [verbas, setVerbas] = useState<EstadoVerba[]>(() => [novaVerba()]);
  const [passo, setPasso] = useState<Passo>("formulario");
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<CalculoCriado | null>(null);
  const [cobertura, setCobertura] = useState<CoberturaEfetiva | null>(null);

  const indexadores = useMemo(() => {
    const chaves = new Set(
      verbas.filter((v) => v.correcaoAplicar).map((v) => v.correcaoIndexador),
    );
    return chaves.size ? Array.from(chaves) : ["tjsp_tabela_pratica"];
  }, [verbas]);

  useEffect(() => {
    let ativo = true;
    const chave = indexadores[0];
    api
      .coberturaIndexador(chave)
      .then((dados) => {
        if (ativo) setCobertura(dados);
      })
      .catch(() => {
        if (ativo) setCobertura(null);
      });
    return () => {
      ativo = false;
    };
  }, [indexadores]);

  const avisos = useMemo(() => {
    const lista: string[] = [];
    if (!cobertura) return lista;
    for (const [i, verba] of verbas.entries()) {
      if (!verba.correcaoAplicar) continue;
      const fim = verba.correcaoFim || dataBaseCalculo;
      if (fim && coberturaInsuficientePara(cobertura, fim)) {
        lista.push(
          `Verba ${i + 1} (${verba.nome || "sem nome"}): a correção vai até ${fim}, ` +
            `além da cobertura de ${cobertura.oficial.name} (${cobertura.cobertura_efetiva.fim_rotulo}).`,
        );
      }
    }
    return lista;
  }, [verbas, dataBaseCalculo, cobertura]);

  function atualizarVerba(id: string, parcial: Partial<EstadoVerba>) {
    setVerbas((atual) =>
      atual.map((v) => (v.id === id ? { ...v, ...parcial } : v)),
    );
  }

  function removerVerba(id: string) {
    setVerbas((atual) => atual.filter((v) => v.id !== id));
  }

  function reiniciar() {
    setIdentificacao({ titulo: "", processo: "", parte: "" });
    setDataBaseCalculo("");
    setVerbas([novaVerba()]);
    setErros([]);
    setErroEnvio(null);
    setResultado(null);
    setPasso("formulario");
  }

  async function enviar() {
    setEnviando(true);
    setErroEnvio(null);
    try {
      const payload = montarPayload(identificacao, dataBaseCalculo, verbas);
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
        eyebrow="Cálculo Cível · Verbas"
        titulo="Novo cálculo por verbas"
        descricao="Cada verba tem valor, datas e regras independentes. O React apenas coleta e envia verbas[] ao backend — sem calcular correção, juros ou totais."
        dica="Ex.: Dano moral com correção desde 10/05/2020 e juros desde 15/03/2024; Honorários com juros desde 01/08/2023. As datas não são globais."
      />

      {passo === "sucesso" && resultado ? (
        <ResultadoSucesso resultado={resultado} onReiniciar={reiniciar} />
      ) : null}

      {passo === "formulario" ? (
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            const lista = errosValidacao(identificacao, dataBaseCalculo, verbas);
            setErros(lista);
            setErroEnvio(null);
            if (lista.length === 0) setPasso("revisao");
          }}
        >
          <Card>
            <div className="space-y-6">
              <SecaoIdentificacao
                valor={identificacao}
                onChange={(parcial) =>
                  setIdentificacao((atual) => ({ ...atual, ...parcial }))
                }
              />
              <section className="space-y-2" aria-labelledby="sec-data-base-calc">
                <div className="flex items-center gap-2">
                  <h2
                    id="sec-data-base-calc"
                    className="text-base font-semibold text-ink-900"
                  >
                    Data-base do cálculo
                  </h2>
                  <Tooltip text="Data de referência do cálculo (fim padrão de correção/juros quando a verba não define o término). Cada verba ainda tem sua própria data-base/vencimento." />
                </div>
                <div className="max-w-sm">
                  <Input
                    id="data-base-calculo"
                    label="Data-base de referência"
                    required
                    type="date"
                    value={dataBaseCalculo}
                    onChange={(e) => setDataBaseCalculo(e.target.value)}
                    tooltip="Usada pelo backend como data de referência do cálculo. Não substitui as datas individuais das verbas."
                  />
                </div>
              </section>

              <section className="space-y-4" aria-labelledby="sec-verbas">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h2
                      id="sec-verbas"
                      className="text-base font-semibold text-ink-900"
                    >
                      Verbas do cálculo
                    </h2>
                    <Tooltip text="Adicione quantas verbas precisar (dano moral, honorários, restituição…). Cada cartão é independente." />
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setVerbas((atual) => [...atual, novaVerba()])}
                  >
                    + Adicionar verba
                  </Button>
                </div>

                {avisos.map((aviso) => (
                  <Message key={aviso} tom="warning">
                    {aviso}
                  </Message>
                ))}

                {verbas.length === 0 ? (
                  <Message tom="info">
                    Nenhuma verba. Clique em “Adicionar verba” para começar.
                  </Message>
                ) : (
                  <div className="space-y-4">
                    {verbas.map((verba, indice) => (
                      <CardVerba
                        key={verba.id}
                        verba={verba}
                        indice={indice}
                        onChange={(parcial) => atualizarVerba(verba.id, parcial)}
                        onRemover={() => removerVerba(verba.id)}
                        coberturaFim={cobertura?.cobertura_efetiva.fim_rotulo ?? null}
                      />
                    ))}
                  </div>
                )}
              </section>
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-ink-100 pt-5">
              <Button type="submit" size="lg">
                Revisar verbas
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
              rotulo="Data-base do cálculo"
              valor={<span className="font-mono">{rotuloData(dataBaseCalculo)}</span>}
            />
          </dl>

          <div className="mt-4 space-y-3">
            <h3 className="text-sm font-semibold text-ink-900">
              Verbas ({verbas.length})
            </h3>
            {verbas.map((verba, indice) => (
              <div
                key={verba.id}
                className="rounded-xl border border-ink-200 bg-white p-3"
              >
                <p className="text-sm font-semibold text-ink-900">
                  Verba {indice + 1} — {verba.nome || "sem nome"}
                </p>
                <ul className="mt-1 space-y-0.5 text-sm text-ink-700">
                  <li>
                    Valor:{" "}
                    <span className="font-mono">{verba.valor || "—"}</span> ·
                    Vencimento:{" "}
                    <span className="font-mono">{rotuloData(verba.dataBase)}</span>
                  </li>
                  <li>
                    Correção:{" "}
                    {verba.correcaoAplicar
                      ? `sim · desde ${rotuloData(verba.correcaoInicio || verba.dataBase)} · até ${rotuloData(verba.correcaoFim || dataBaseCalculo)} · ${verba.correcaoIndexador}`
                      : "não aplicada"}
                  </li>
                  <li>
                    Juros:{" "}
                    {verba.jurosAplicar
                      ? `sim · desde ${rotuloData(verba.jurosInicio || verba.dataBase)} · ${verba.jurosModalidade}`
                      : "não aplicados"}
                  </li>
                  <li>
                    Multa: {verba.multaAplicar ? "sim" : "não"} · Honorários:{" "}
                    {verba.honorariosAplicar ? "sim" : "não"}
                  </li>
                  <li>
                    Pagamentos:{" "}
                    {verba.pagamentos.filter((p) => p.data && p.valor).length || 0}
                  </li>
                </ul>
              </div>
            ))}
          </div>

          <Message tom="info" className="mt-4">
            O total geral será exibido após o envio, com o valor retornado pelo
            backend. O frontend não soma nem recalcula verbas.
          </Message>
        </CartaoRevisao>
      ) : null}
    </div>
  );
}
