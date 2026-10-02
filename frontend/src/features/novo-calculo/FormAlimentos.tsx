import { useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Form";
import { Tooltip } from "../../components/ui/Tooltip";
import { SecaoBlocosAlimentos, novaRegraAlimento } from "./SecaoBlocosAlimentos";
import {
  SecaoAtualizacaoAlimentos,
  estadoAtualizacaoInicial,
  type EstadoAtualizacaoAlimentos,
} from "./SecaoAtualizacaoAlimentos";
import {
  SecaoPagamentosAlimentos,
  type EstadoPagamentoAlimento,
} from "./SecaoPagamentosAlimentos";
import { SecaoIdentificacao, type EstadoIdentificacao } from "./SecaoIdentificacao";
import {
  CampoResumo,
  CabecalhoFormulario,
  CartaoRevisao,
  type Passo,
} from "./FluxoFormulario";
import { ResultadoSucesso } from "./ResultadoSucesso";
import { api, mensagemErroAmigavel } from "../../lib/api";
import {
  competenciaValida,
  fimDoMesISO,
  rotuloCompetencia,
} from "../../lib/competencia";
import type {
  CalculoAlimentosPayload,
  CalculoCriado,
  PagamentoPayload,
  RegraAlimentoPayload,
} from "../../types/api";

interface EstadoAlimentos {
  identificacao: EstadoIdentificacao;
  ate: string;
  diaVencimento: string;
  dataBase: string;
  regras: ReturnType<typeof novaRegraAlimento>[];
  pagamentos: EstadoPagamentoAlimento[];
  atualizacao: EstadoAtualizacaoAlimentos;
}

function estadoInicial(): EstadoAlimentos {
  return {
    identificacao: { titulo: "", processo: "", parte: "" },
    ate: "",
    diaVencimento: "10",
    dataBase: "",
    regras: [
      novaRegraAlimento({
        inicio: "",
        fim: "",
        tipo: "salario_minimo",
        percentual: "0.30",
      }),
    ],
    pagamentos: [],
    atualizacao: estadoAtualizacaoInicial(),
  };
}

function errosValidacao(estado: EstadoAlimentos): string[] {
  const erros: string[] = [];
  if (!estado.identificacao.titulo.trim()) {
    erros.push("Informe o nome/descrição do cálculo.");
  }
  if (!estado.ate.trim()) {
    erros.push("Informe o período final (até).");
  } else if (!competenciaValida(estado.ate)) {
    erros.push("Período final inválido — use MM/AAAA ou YYYY-MM.");
  }
  if (!estado.regras.length) {
    erros.push("Adicione ao menos um bloco de regra.");
  }
  estado.regras.forEach((regra, indice) => {
    const rotulo = `Bloco ${indice + 1}`;
    if (!regra.inicio.trim()) {
      erros.push(`${rotulo}: informe a data inicial de vigência.`);
    } else if (!competenciaValida(regra.inicio)) {
      erros.push(`${rotulo}: início inválido (MM/AAAA ou YYYY-MM).`);
    }
    if (regra.fim.trim() && !competenciaValida(regra.fim)) {
      erros.push(`${rotulo}: fim inválido (MM/AAAA ou YYYY-MM).`);
    }
    if (regra.tipo === "salario_minimo" && !regra.percentual.trim()) {
      erros.push(`${rotulo}: informe o percentual do salário mínimo.`);
    }
    if (regra.tipo === "fixo" && !regra.valor.trim()) {
      erros.push(`${rotulo}: informe o valor fixo.`);
    }
  });
  estado.pagamentos.forEach((pg, indice) => {
    if (!pg.competencia.trim()) {
      erros.push(`Pagamento ${indice + 1}: informe a competência.`);
    } else if (!competenciaValida(pg.competencia)) {
      erros.push(
        `Pagamento ${indice + 1}: competência inválida (MM/AAAA ou YYYY-MM).`,
      );
    }
    if (!pg.data) erros.push(`Pagamento ${indice + 1}: informe a data.`);
    if (!pg.valor.trim()) erros.push(`Pagamento ${indice + 1}: informe o valor.`);
  });
  if (
    estado.atualizacao.jurosAplicar &&
    estado.atualizacao.jurosModalidade === "fixa" &&
    !estado.atualizacao.jurosTaxa.trim()
  ) {
    erros.push("Informe a taxa mensal dos juros (ex.: 0.01 = 1% ao mês).");
  }
  return erros;
}

function montarPayload(estado: EstadoAlimentos): CalculoAlimentosPayload {
  const regras: RegraAlimentoPayload[] = estado.regras.map((regra) => {
    const base: RegraAlimentoPayload = {
      inicio: regra.inicio.trim(),
      fim: regra.fim.trim() || null,
      tipo: regra.tipo,
      descricao: regra.descricao.trim(),
    };
    if (regra.tipo === "salario_minimo") {
      return { ...base, percentual: regra.percentual.trim(), valor: null };
    }
    return { ...base, percentual: null, valor: regra.valor.trim() };
  });

  const pagamentos: PagamentoPayload[] = estado.pagamentos
    .filter((pg) => pg.competencia.trim() && pg.data && pg.valor.trim())
    .map((pg) => ({
      competencia: pg.competencia.trim(),
      data: pg.data,
      valor: pg.valor.trim(),
      descricao: (pg.descricao ?? "").trim(),
    }));

  const dataBase =
    estado.dataBase.trim() || fimDoMesISO(estado.ate) || fimDoMesISO(estado.ate) || "";

  return {
    tipo: "alimentos",
    titulo: estado.identificacao.titulo.trim(),
    processo: estado.identificacao.processo.trim(),
    parte: estado.identificacao.parte.trim(),
    data_base: dataBase,
    alimentos: {
      regras,
      ate: estado.ate.trim(),
      dia_vencimento: Number(estado.diaVencimento) || 10,
    },
    correcao: {
      aplicar: estado.atualizacao.correcaoAplicar,
      indexador: estado.atualizacao.correcaoIndexador,
      termo_inicial: null,
      termo_final: null,
    },
    juros: {
      aplicar: estado.atualizacao.jurosAplicar,
      modalidade: estado.atualizacao.jurosModalidade,
      taxa:
        estado.atualizacao.jurosModalidade === "fixa"
          ? estado.atualizacao.jurosTaxa.trim() || null
          : null,
      unidade: "mensal",
      base: estado.atualizacao.jurosBase,
      inicio: null,
      fim: null,
    },
    multa: { aplicar: false },
    honorarios: { aplicar: false },
    pagamentos,
  };
}

function rotuloRegra(regra: {
  tipo: string;
  percentual: string;
  valor: string;
  inicio: string;
  fim: string;
  descricao: string;
}): string {
  const vigencia = `${rotuloCompetencia(regra.inicio)}–${
    regra.fim ? rotuloCompetencia(regra.fim) : "em diante"
  }`;
  if (regra.tipo === "salario_minimo") {
    return `${vigencia}: ${regra.percentual || "?"} do salário mínimo`;
  }
  return `${vigencia}: valor fixo ${regra.valor || "?"}`;
}

export function FormAlimentos() {
  const [estado, setEstado] = useState<EstadoAlimentos>(estadoInicial);
  const [passo, setPasso] = useState<Passo>("formulario");
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<CalculoCriado | null>(null);

  const sugestaoDataBase = useMemo(() => fimDoMesISO(estado.ate), [estado.ate]);

  function atualizar(parcial: Partial<EstadoAlimentos>) {
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
        eyebrow="Alimentos"
        titulo="Novo cálculo de alimentos"
        descricao="Blocos de regras (percentual do salário mínimo ou valor fixo) por competência. Cada competência é gerada no backend — o React não calcula salário mínimo nem aplica percentuais."
        dica="O salário mínimo é consultado por competência no backend. Mudanças dentro do ano são respeitadas; não se usa o valor atual retroativamente."
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
              <SecaoBlocosAlimentos
                regras={estado.regras}
                onChange={(regras) => atualizar({ regras })}
                ate={estado.ate}
                onAteChange={(ate) => atualizar({ ate })}
                diaVencimento={estado.diaVencimento}
                onDiaVencimentoChange={(diaVencimento) =>
                  atualizar({ diaVencimento })
                }
              />
              <section className="space-y-3" aria-labelledby="sec-data-base-alim">
                <div className="flex items-center gap-2">
                  <h2
                    id="sec-data-base-alim"
                    className="text-base font-semibold text-ink-900"
                  >
                    3. Data-base de referência
                  </h2>
                  <Tooltip text="Data usada pelo backend como referência do cálculo (correção/juros, quando aplicados). Pode ser preenchida manualmente ou sugerida no fim do período." />
                </div>
                <Input
                  id="alimentos-data-base"
                  label="Data-base do cálculo"
                  type="date"
                  value={estado.dataBase}
                  onChange={(e) => atualizar({ dataBase: e.target.value })}
                  hint={
                    sugestaoDataBase
                      ? `Sugestão (fim de ${rotuloCompetencia(estado.ate)}): ${sugestaoDataBase}`
                      : "Preencha ou aguarde o período final para sugestão"
                  }
                />
              </section>
              <SecaoAtualizacaoAlimentos
                valor={estado.atualizacao}
                onChange={(parcial) =>
                  atualizar({
                    atualizacao: { ...estado.atualizacao, ...parcial },
                  })
                }
              />
              <SecaoPagamentosAlimentos
                pagamentos={estado.pagamentos}
                onChange={(pagamentos) => atualizar({ pagamentos })}
              />
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
              rotulo="Período"
              valor={
                <span className="font-mono">
                  {estado.regras[0]?.inicio
                    ? rotuloCompetencia(estado.regras[0].inicio)
                    : "—"}{" "}
                  → {estado.ate ? rotuloCompetencia(estado.ate) : "—"}
                </span>
              }
            />
            <CampoResumo
              rotulo="Data-base"
              valor={
                <span className="font-mono">
                  {estado.dataBase || sugestaoDataBase || "—"}
                </span>
              }
            />
            <CampoResumo
              rotulo="Dia de vencimento"
              valor={estado.diaVencimento || "10"}
            />
            <CampoResumo
              rotulo="Correção monetária"
              valor={
                estado.atualizacao.correcaoAplicar
                  ? "Tabela Prática TJSP"
                  : "Não aplicada"
              }
            />
            <CampoResumo
              rotulo="Juros"
              valor={
                estado.atualizacao.jurosAplicar
                  ? estado.atualizacao.jurosModalidade === "fixa"
                    ? `${estado.atualizacao.jurosTaxa || "—"} ao mês desde o vencimento`
                    : "Taxa Legal (BCB)"
                  : "Não aplicados"
              }
            />
          </dl>
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-ink-900">
              Blocos de regras (enviados ao backend)
            </h3>
            <ul className="mt-2 space-y-1 text-sm text-ink-800">
              {estado.regras.map((regra) => (
                <li key={regra.id}>{rotuloRegra(regra)}</li>
              ))}
            </ul>
          </div>
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-ink-900">
              Pagamentos por competência
            </h3>
            {estado.pagamentos.filter((p) => p.competencia && p.valor).length ===
            0 ? (
              <p className="mt-1 text-sm text-ink-500">Nenhum pagamento.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm text-ink-800">
                {estado.pagamentos
                  .filter((p) => p.competencia && p.valor)
                  .map((p) => (
                    <li key={p.id}>
                      {rotuloCompetencia(p.competencia)} — {p.valor}
                      {p.descricao ? ` (${p.descricao})` : ""}
                    </li>
                  ))}
              </ul>
            )}
          </div>
          <p className="mt-4 text-xs text-ink-500">
            O backend gerará uma parcela por competência, consultando o salário
            mínimo vigente em cada uma (quando a regra for percentual).
          </p>
        </CartaoRevisao>
      ) : null}
    </div>
  );
}
