import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Message } from "../components/ui/Message";
import { Tooltip } from "../components/ui/Tooltip";
import { SecaoEncargos, encargoVazio, type EstadoEncargos } from "../features/novo-calculo/SecaoEncargos";
import { SecaoIdentificacao, type EstadoIdentificacao } from "../features/novo-calculo/SecaoIdentificacao";
import {
  SecaoPagamentos,
  type EstadoPagamento,
} from "../features/novo-calculo/SecaoPagamentos";
import {
  SecaoValorDatas,
  type EstadoValorDatas,
} from "../features/novo-calculo/SecaoValorDatas";
import {
  ErroApi,
  api,
  formatarDataHora,
  mensagemErroAmigavel,
} from "../lib/api";
import { coberturaInsuficientePara } from "../lib/cobertura";
import type {
  CalculoCriado,
  CalculoRequestPayload,
  CoberturaEfetiva,
  PagamentoPayload,
} from "../types/api";

type Passo = "formulario" | "revisao" | "sucesso";

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
}): CalculoRequestPayload {
  const { identificacao, valorDatas, encargos, pagamentos } = estado;

  const pagamentosParcela: PagamentoPayload[] = pagamentos
    .filter((pg) => pg.data && pg.valor.trim())
    .map((pg) => ({
      data: pg.data,
      valor: pg.valor.trim(),
      descricao: (pg.descricao ?? "").trim(),
    }));

  const correcao = {
    aplicar: encargos.correcao.aplicar,
    indexador: encargos.correcao.indexador,
    termo_final: valorDatas.dataFinal,
  };

  const juros = {
    aplicar: encargos.juros.aplicar,
    modalidade: encargos.juros.modalidade,
    base: encargos.juros.base,
    unidade: encargos.juros.unidade,
  };

  const multa = {
    aplicar: encargos.multa.aplicar,
    percentual: encargos.multa.percentual.trim() || null,
    valor_fixo: encargos.multa.valorFixo.trim() || null,
    base: encargos.multa.base,
  };

  const honorarios = {
    aplicar: encargos.honorarios.aplicar,
    percentual: encargos.honorarios.percentual.trim() || null,
    valor_fixo: encargos.honorarios.valorFixo.trim() || null,
    base: encargos.honorarios.base,
  };

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
    correcao,
    juros,
    multa,
    honorarios,
    pagamentos: [],
  };
}

export function NovoCalculoPage() {
  const [params] = useSearchParams();
  const tipoParam = params.get("tipo") ?? "parcelas";

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

  const ehCivel = tipoParam === "parcelas" || tipoParam === "";

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

  function atualizarIdentificacao(parcial: Partial<EstadoIdentificacao>) {
    setIdentificacao((atual) => ({ ...atual, ...parcial }));
  }

  function atualizarValorDatas(parcial: Partial<EstadoValorDatas>) {
    setValorDatas((atual) => ({ ...atual, ...parcial }));
  }

  function atualizarEncargos(parcial: Partial<EstadoEncargos>) {
    setEncargos((atual) => ({ ...atual, ...parcial }));
  }

  function irParaRevisao() {
    setErroEnvio(null);
    const lista = errosValidacao({ identificacao, valorDatas, encargos, pagamentos });
    setErros(lista);
    if (lista.length === 0) {
      setPasso("revisao");
    }
  }

  function voltarFormulario() {
    setPasso("formulario");
    setErroEnvio(null);
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
      if (e instanceof ErroApi && e.corpo.erro === "cobertura_insuficiente") {
        setErroEnvio(mensagemErroAmigavel(e));
      } else {
        setErroEnvio(mensagemErroAmigavel(e));
      }
      setPasso("revisao");
    } finally {
      setEnviando(false);
    }
  }

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

  if (!ehCivel) {
    return (
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Em preparação
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">
            Novo cálculo — {tipoParam}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Esta etapa cobre o <strong>Cálculo Cível</strong>. Alimentos e
            atualização monetária terão formulário dedicado em seguida, sempre
            enviando o payload para o backend — sem regras matemáticas no React.
          </p>
        </div>
        <Message tom="info" title="Cálculo Cível disponível">
          <Link
            to="/novo-calculo?tipo=parcelas"
            className="font-medium text-brand-700 hover:underline"
          >
            Abrir o formulário de Cálculo Cível
          </Link>
        </Message>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Cálculo Cível
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">
            Novo cálculo
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Preencha os campos abaixo. O React apenas coleta e envia os dados para{" "}
            <code className="font-mono text-xs">POST /api/calculos</code>. Toda a
            matemática (correção, juros, encargos) é executada no backend.
          </p>
        </div>
        <Tooltip text="Datas passadas e futuras são permitidas. A data-final é sempre a que você escolher — não há preenchimento automático com 'hoje'." />
      </div>

      {passo === "sucesso" && resultado ? (
        <Card title="Cálculo criado" description="Resposta do backend">
          <Message tom="success" title="Enviado com sucesso">
            Código VEC gerado e persistido no SQLite.
          </Message>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
              <dt className="text-xs uppercase text-ink-500">Código</dt>
              <dd className="mt-1 font-mono text-sm font-semibold text-brand-700">
                {resultado.codigo}
              </dd>
            </div>
            <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
              <dt className="text-xs uppercase text-ink-500">Tipo</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {resultado.tipo}
              </dd>
            </div>
            <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
              <dt className="text-xs uppercase text-ink-500">Total</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {resultado.resumo?.total ?? "—"}
              </dd>
            </div>
            <div className="rounded-xl border border-ink-100 bg-white px-3 py-2.5">
              <dt className="text-xs uppercase text-ink-500">Saldo</dt>
              <dd className="mt-1 text-sm font-medium text-ink-900">
                {resultado.resumo?.saldo ?? "—"}
              </dd>
            </div>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={`${api.baseUrl}/api/calculos/${resultado.codigo}/pdf`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="secondary" size="sm">
                Baixar PDF
              </Button>
            </a>
            <a
              href={`${api.baseUrl}/api/calculos/${resultado.codigo}/xlsx`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="secondary" size="sm">
                Baixar XLSX
              </Button>
            </a>
            <a
              href={`${api.baseUrl}/api/calculos/${resultado.codigo}/memoria`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline" size="sm">
                Abrir memória de cálculo
              </Button>
            </a>
            <Link to={`/meus-calculos?codigo=${encodeURIComponent(resultado.codigo)}`}>
              <Button variant="ghost" size="sm">
                Ver em Meus cálculos
              </Button>
            </Link>
          </div>
          <div className="mt-4">
            <Button type="button" onClick={reiniciar}>
              Criar outro cálculo
            </Button>
          </div>
        </Card>
      ) : null}

      {passo === "formulario" ? (
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            irParaRevisao();
          }}
        >
          <Card>
            <div className="space-y-8">
              <SecaoIdentificacao
                valor={identificacao}
                onChange={atualizarIdentificacao}
              />
              <SecaoValorDatas
                valor={valorDatas}
                onChange={atualizarValorDatas}
                avisos={avisosDatas}
              />
              <SecaoEncargos
                valor={encargos}
                onChange={atualizarEncargos}
                jurosDisponiveis={Boolean(cobertura)}
              />
              <SecaoPagamentos
                pagamentos={pagamentos}
                onChange={setPagamentos}
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
        <Card title="Revisão antes do envio" description="Confira os dados enviados ao backend">
          {erros.length > 0 ? (
            <Message tom="danger" title="Corrija os itens abaixo">
              <ul className="list-disc space-y-1 pl-5">
                {erros.map((erro) => (
                  <li key={erro}>{erro}</li>
                ))}
              </ul>
            </Message>
          ) : null}
          {erroEnvio ? (
            <Message tom="danger" title="Falha no envio">
              {erroEnvio}
            </Message>
          ) : null}

          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase text-ink-500">Título</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {identificacao.titulo || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Processo</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {identificacao.processo || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Parte</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {identificacao.parte || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Valor-base</dt>
              <dd className="mt-0.5 font-mono text-sm font-medium text-ink-900">
                {valorDatas.valorBase || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Data-base</dt>
              <dd className="mt-0.5 font-mono text-sm font-medium text-ink-900">
                {valorDatas.dataBase || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Data-final</dt>
              <dd className="mt-0.5 font-mono text-sm font-medium text-ink-900">
                {valorDatas.dataFinal || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Correção monetária</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {encargos.correcao.aplicar
                  ? `Sim — ${encargos.correcao.indexador}`
                  : "Não aplicada"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Juros</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {encargos.juros.aplicar
                  ? `Sim — ${encargos.juros.modalidade}`
                  : "Não aplicados"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Multa</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {encargos.multa.aplicar
                  ? encargos.multa.percentual
                    ? `${encargos.multa.percentual} (${encargos.multa.base})`
                    : `${encargos.multa.valorFixo} (${encargos.multa.base})`
                  : "Não aplicada"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-ink-500">Honorários</dt>
              <dd className="mt-0.5 text-sm font-medium text-ink-900">
                {encargos.honorarios.aplicar
                  ? encargos.honorarios.percentual
                    ? `${encargos.honorarios.percentual} (${encargos.honorarios.base})`
                    : `${encargos.honorarios.valorFixo} (${encargos.honorarios.base})`
                  : "Não aplicados"}
              </dd>
            </div>
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

          <div className="mt-6 flex flex-wrap gap-3 border-t border-ink-100 pt-5">
            <Button
              type="button"
              size="lg"
              onClick={enviar}
              disabled={enviando || erros.length > 0}
            >
              {enviando ? "Enviando…" : "Confirmar e calcular no backend"}
            </Button>
            <Button type="button" variant="outline" onClick={voltarFormulario}>
              Voltar e editar
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
