import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Form";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";
import { SecaoIdentificacao, type EstadoIdentificacao } from "../novo-calculo/SecaoIdentificacao";
import { DetalhesVerba } from "./DetalhesVerba";
import {
  formatarDataBR,
  montarPagamentosVerba,
  novaVerba,
  type EstadoVerba,
} from "./estadoVerba";
import { api, mensagemErroAmigavel } from "../../lib/api";
import { coberturaInsuficientePara } from "../../lib/cobertura";
import type {
  CalculoCivelPayload,
  CoberturaEfetiva,
  VerbaPayload,
} from "../../types/api";

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

function errosValidacao(
  identificacao: EstadoIdentificacao,
  dataBaseCalculo: string,
  verbas: EstadoVerba[],
): string[] {
  const erros: string[] = [];
  if (!identificacao.titulo.trim()) erros.push("Informe o nome do cálculo.");
  if (!dataBaseCalculo) erros.push("Informe a data da atualização.");
  if (verbas.length === 0) erros.push("Inclua ao menos uma verba.");
  verbas.forEach((verba, i) => {
    const rotulo = `Verba ${i + 1}`;
    if (!verba.nome.trim()) erros.push(`${rotulo}: informe o nome.`);
    if (!verba.valor.trim()) erros.push(`${rotulo}: informe o valor.`);
    if (!verba.dataBase) erros.push(`${rotulo}: informe a data-base.`);
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
    if (
      verba.jurosAplicar &&
      verba.jurosModalidade === "fixa" &&
      !verba.jurosTaxa.trim()
    ) {
      erros.push(`${rotulo}: informe a taxa de juros.`);
    }
  });
  return erros;
}

export function FormCivel() {
  const navigate = useNavigate();
  const [identificacao, setIdentificacao] = useState<EstadoIdentificacao>({
    titulo: "",
    processo: "",
    parte: "",
  });
  const [dataBaseCalculo, setDataBaseCalculo] = useState("");
  const [verbas, setVerbas] = useState<EstadoVerba[]>(() => [novaVerba()]);
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [cobertura, setCobertura] = useState<CoberturaEfetiva | null>(null);

  useEffect(() => {
    let ativo = true;
    api
      .coberturaIndexador("tjsp_tabela_pratica")
      .then((dados) => {
        if (ativo) setCobertura(dados);
      })
      .catch(() => {
        if (ativo) setCobertura(null);
      });
    return () => {
      ativo = false;
    };
  }, []);

  const avisos = useMemo(() => {
    const lista: string[] = [];
    if (!cobertura) return lista;
    for (const [i, verba] of verbas.entries()) {
      if (!verba.correcaoAplicar) continue;
      const fim = verba.correcaoFim || dataBaseCalculo;
      if (fim && coberturaInsuficientePara(cobertura, fim)) {
        lista.push(
          `Verba ${i + 1} (${verba.nome || "sem nome"}): correção até ${fim} ` +
            `além da cobertura (${cobertura.cobertura_efetiva.fim_rotulo}).`,
        );
      }
    }
    return lista;
  }, [verbas, dataBaseCalculo, cobertura]);

  function atualizarVerba(id: string, parcial: Partial<EstadoVerba>) {
    setVerbas((atual) => atual.map((v) => (v.id === id ? { ...v, ...parcial } : v)));
  }

  function incluirVerba() {
    setVerbas((atual) => [...atual, novaVerba()]);
  }

  function removerVerba(id: string) {
    setVerbas((atual) => atual.filter((v) => v.id !== id));
  }

  async function gerarCalculo() {
    setErros([]);
    setErroEnvio(null);
    const lista = errosValidacao(identificacao, dataBaseCalculo, verbas);
    setErros(lista);
    if (lista.length > 0) return;

    setEnviando(true);
    try {
      const payload = montarPayload(identificacao, dataBaseCalculo, verbas);
      const criado = await api.criarCalculo(payload);
      navigate(`/calculos/${encodeURIComponent(criado.codigo)}`);
    } catch (e) {
      setErroEnvio(mensagemErroAmigavel(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Cálculo Cível
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">
            Lançamento simples
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Monte o cálculo rapidamente com verbas. Configurações avançadas ficam
            em “Configurar detalhes”. O backend calcula — o React só coleta e envia.
          </p>
        </div>
        <Tooltip text="Cada verba tem suas próprias datas de correção e juros. O total aparece na tela de resultado, vindo do backend." />
      </div>

      {erros.length > 0 ? (
        <Message tom="danger" title="Corrija antes de gerar">
          <ul className="list-disc space-y-1 pl-5">
            {erros.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </Message>
      ) : null}
      {erroEnvio ? (
        <Message tom="danger" title="Falha no envio">
          {erroEnvio}
        </Message>
      ) : null}
      {avisos.map((a) => (
        <Message key={a} tom="warning">
          {a}
        </Message>
      ))}

      <Card>
        <div className="space-y-6">
          <SecaoIdentificacao
            valor={identificacao}
            onChange={(parcial) =>
              setIdentificacao((atual) => ({ ...atual, ...parcial }))
            }
          />

          <section className="space-y-3" aria-labelledby="sec-data-atualizacao">
            <div className="flex items-center gap-2">
              <h2
                id="sec-data-atualizacao"
                className="text-base font-semibold text-ink-900"
              >
                Data da atualização
              </h2>
              <Tooltip text="Data-base do cálculo (referência). Cada verba ainda tem sua própria data-base na coluna de detalhes." />
            </div>
            <div className="max-w-xs">
              <Input
                id="data-atualizacao"
                label="Data da atualização"
                required
                type="date"
                value={dataBaseCalculo}
                onChange={(e) => setDataBaseCalculo(e.target.value)}
              />
            </div>
          </section>

          <section className="space-y-3" aria-labelledby="sec-base-calculo">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <h2
                  id="sec-base-calculo"
                  className="text-base font-semibold text-ink-900"
                >
                  Base do cálculo
                </h2>
                <Tooltip text="Tabela simples de verbas. Use “Configurar detalhes” para multa, honorários, fim da correção/juros e pagamentos." />
              </div>
              <Button type="button" variant="secondary" size="sm" onClick={incluirVerba}>
                + Incluir verba
              </Button>
            </div>

            <div className="overflow-x-auto rounded-xl border border-ink-200">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-600">
                  <tr>
                    <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                      Verba
                    </th>
                    <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                      Valor
                    </th>
                    <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                      Início da correção
                    </th>
                    <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                      Início dos juros
                    </th>
                    <th
                      scope="col"
                      className="border-b border-ink-200 px-3 py-2.5 text-right"
                    >
                      Ações
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 bg-white">
                  {verbas.map((verba, indice) => (
                    <>
                      <tr key={verba.id} className="align-middle hover:bg-ink-50/60">
                        <td className="px-3 py-2">
                          <Input
                            id={`verba-nome-${verba.id}`}
                            label={`Verba ${indice + 1}`}
                            required
                            value={verba.nome}
                            onChange={(e) =>
                              atualizarVerba(verba.id, { nome: e.target.value })
                            }
                            placeholder="Ex.: Dano moral"
                            className="min-w-[140px]"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            id={`verba-valor-${verba.id}`}
                            label="Valor"
                            required
                            inputMode="decimal"
                            value={verba.valor}
                            onChange={(e) =>
                              atualizarVerba(verba.id, { valor: e.target.value })
                            }
                            placeholder="20000,00"
                            className="min-w-[100px]"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            id={`verba-correcao-inicio-${verba.id}`}
                            label="Correção desde"
                            type="date"
                            value={verba.correcaoInicio || verba.dataBase}
                            onChange={(e) =>
                              atualizarVerba(verba.id, {
                                correcaoInicio: e.target.value,
                                correcaoAplicar: true,
                              })
                            }
                            className="min-w-[140px]"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            id={`verba-juros-inicio-${verba.id}`}
                            label="Juros desde"
                            type="date"
                            value={verba.jurosInicio || verba.dataBase}
                            onChange={(e) =>
                              atualizarVerba(verba.id, {
                                jurosInicio: e.target.value,
                                jurosAplicar: true,
                              })
                            }
                            className="min-w-[140px]"
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          <div className="flex flex-col items-end gap-1">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                atualizarVerba(verba.id, {
                                  detalhesAbertos: !verba.detalhesAbertos,
                                })
                              }
                            >
                              {verba.detalhesAbertos
                                ? "Ocultar detalhes"
                                : "Configurar detalhes"}
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => removerVerba(verba.id)}
                            >
                              Remover
                            </Button>
                          </div>
                        </td>
                      </tr>
                      {verba.detalhesAbertos ? (
                        <tr key={`${verba.id}-detalhes`}>
                          <td colSpan={5} className="bg-ink-50/40 p-0">
                            <DetalhesVerba
                              verba={verba}
                              onChange={(parcial) =>
                                atualizarVerba(verba.id, parcial)
                              }
                              coberturaFim={
                                cobertura?.cobertura_efetiva.fim_rotulo ?? null
                              }
                            />
                          </td>
                        </tr>
                      ) : null}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {verbas.length === 0 ? (
              <Message tom="info">Nenhuma verba. Use “+ Incluir verba”.</Message>
            ) : null}

            <p className="text-xs text-ink-500">
              Ex.: Valor da causa · Dano moral · Honorários — cada linha com suas
              próprias datas de correção e juros. Datas vazias usam a data-base da
              verba (detalhes) ou a data da atualização.
            </p>
            <p className="text-xs text-ink-500">
              Data-base de cada verba (vencimento):{" "}
              {verbas.map((v, i) => (
                <span key={v.id} className="mr-2">
                  {v.nome || `#${i + 1}`}: {formatarDataBR(v.dataBase)}
                </span>
              ))}
            </p>
          </section>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-ink-100 pt-5">
          <Button type="button" size="lg" onClick={gerarCalculo} disabled={enviando}>
            {enviando ? "Gerando…" : "Gerar cálculo"}
          </Button>
          <span className="text-xs text-ink-500">
            Após gerar, você verá a memória de cálculo com PDF, XLSX e tabela completa.
          </span>
        </div>
      </Card>
    </div>
  );
}
