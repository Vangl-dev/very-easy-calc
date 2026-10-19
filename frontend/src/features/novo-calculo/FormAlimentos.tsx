import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Form";
import { Message } from "../../components/ui/Message";
import { CabecalhoFormulario } from "./FluxoFormulario";
import { SecaoIdentificacao } from "./SecaoIdentificacao";
import {
  estadoInicialAlimentos,
  montarPayloadAlimentos,
  novaRegra,
  novoPagamento,
  validarAlimentos,
  type EstadoAlimentos,
  type PagamentoAlimento,
  type RegraAlimento,
} from "./alimentos";
import { api, mensagemErroAmigavel } from "../../lib/api";
import { competenciaValida, rotuloCompetencia } from "../../lib/competencia";

interface BlocoRegraProps {
  regra: RegraAlimento;
  indice: number;
  total: number;
  onChange: (parcial: Partial<RegraAlimento>) => void;
  onRemover: () => void;
}

function BlocoRegra({ regra, indice, total, onChange, onRemover }: BlocoRegraProps) {
  const rotulo = `Regra ${indice + 1}`;
  return (
    <li className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-ink-900">{rotulo}</span>
        {total > 1 ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemover}
            aria-label={`Remover ${rotulo}`}
          >
            Remover
          </Button>
        ) : null}
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Input
          id={`regra-percentual-${regra.id}`}
          label="Percentual do salário mínimo"
          required
          inputMode="decimal"
          value={regra.percentual}
          onChange={(e) => onChange({ percentual: e.target.value, tipo: "percentual" })}
          placeholder="85"
          hint="85 = 85% do salário mínimo de cada mês"
        />
        <Input
          id={`regra-inicio-${regra.id}`}
          label="Mês/ano inicial"
          required
          value={regra.inicio}
          onChange={(e) => onChange({ inicio: e.target.value })}
          placeholder="04/2023"
          hint={
            regra.inicio && competenciaValida(regra.inicio)
              ? `De ${rotuloCompetencia(regra.inicio)}`
              : "De — formato MM/AAAA"
          }
        />
        <Input
          id={`regra-fim-${regra.id}`}
          label="Mês/ano final"
          value={regra.fim}
          onChange={(e) => onChange({ fim: e.target.value, tipo: "percentual" })}
          placeholder="09/2026"
          hint={
            regra.fim
              ? competenciaValida(regra.fim)
                ? `Até ${rotuloCompetencia(regra.fim)}`
                : "Até — formato MM/AAAA"
              : "Até em branco = segue até a data da atualização"
          }
        />
      </div>
    </li>
  );
}

interface LinhaPagamentoProps {
  pagamento: PagamentoAlimento;
  indice: number;
  onChange: (parcial: Partial<PagamentoAlimento>) => void;
  onRemover: () => void;
}

function LinhaPagamento({ pagamento, indice, onChange, onRemover }: LinhaPagamentoProps) {
  return (
    <tr className="border-b border-ink-100 bg-white last:border-b-0 hover:bg-ink-50/60">
      <td className="px-3 py-2 align-top">
        <Input
          id={`pg-comp-${pagamento.id}`}
          label="Competência"
          required
          value={pagamento.competencia}
          onChange={(e) => onChange({ competencia: e.target.value })}
          placeholder="01/2026"
          hint={
            pagamento.competencia && competenciaValida(pagamento.competencia)
              ? rotuloCompetencia(pagamento.competencia)
              : "MM/AAAA"
          }
        />
      </td>
      <td className="px-3 py-2 align-top">
        <Input
          id={`pg-data-${pagamento.id}`}
          label="Data do pagamento"
          required
          type="date"
          value={pagamento.data}
          onChange={(e) => onChange({ data: e.target.value })}
        />
      </td>
      <td className="px-3 py-2 align-top">
        <Input
          id={`pg-valor-${pagamento.id}`}
          label="Valor pago"
          required
          inputMode="decimal"
          value={pagamento.valor}
          onChange={(e) => onChange({ valor: e.target.value })}
          placeholder="200,00"
          hint="Valor pago na competência"
        />
      </td>
      <td className="px-3 py-2 text-right align-bottom">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onRemover}
          aria-label={`Remover pagamento ${indice + 1}`}
        >
          Remover
        </Button>
      </td>
    </tr>
  );
}

export function FormAlimentos() {
  const navigate = useNavigate();
  const [estado, setEstado] = useState<EstadoAlimentos>(estadoInicialAlimentos);
  const [erros, setErros] = useState<string[]>([]);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function atualizar(parcial: Partial<EstadoAlimentos>) {
    setEstado((atual) => ({ ...atual, ...parcial }));
    setErros([]);
  }

  function alterarRegra(id: string, parcial: Partial<RegraAlimento>) {
    atualizar({
      regras: estado.regras.map((r) => (r.id === id ? { ...r, ...parcial } : r)),
    });
  }

  function removerRegra(id: string) {
    atualizar({ regras: estado.regras.filter((r) => r.id !== id) });
  }

  function alterarPagamento(id: string, parcial: Partial<PagamentoAlimento>) {
    atualizar({
      pagamentos: estado.pagamentos.map((p) =>
        p.id === id ? { ...p, ...parcial } : p,
      ),
    });
  }

  function removerPagamento(id: string) {
    atualizar({ pagamentos: estado.pagamentos.filter((p) => p.id !== id) });
  }

  function reiniciar() {
    setEstado(estadoInicialAlimentos());
    setErros([]);
    setErroEnvio(null);
  }

  async function gerarCalculo() {
    setErroEnvio(null);
    const lista = validarAlimentos(estado);
    setErros(lista);
    if (lista.length > 0) return;

    setEnviando(true);
    try {
      const criado = await api.criarCalculo(montarPayloadAlimentos(estado));
      navigate(`/calculos/${encodeURIComponent(criado.codigo)}`);
    } catch (e) {
      setErroEnvio(mensagemErroAmigavel(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-6">
      <CabecalhoFormulario
        eyebrow="Alimentos"
        titulo="Novo cálculo de alimentos"
        descricao="Informe a regra, os pagamentos e a data da atualização. Correção pela Tabela Prática TJSP e juros de 1% ao mês são aplicados automaticamente."
        dica="Cada competência do período vira uma linha no resultado, com o salário mínimo daquele mês, correção e juros até a data informada."
      />

      {erros.length > 0 ? (
        <Message tom="danger" title="Corrija antes de gerar">
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

      <form
        noValidate
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          void gerarCalculo();
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

            <section className="space-y-4" aria-labelledby="sec-regra-alimentos">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2
                  id="sec-regra-alimentos"
                  className="text-base font-semibold text-ink-900"
                >
                  2. Regra da obrigação
                </h2>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    atualizar({
                      regras: [
                        ...estado.regras,
                        novaRegra({ tipo: "percentual" }),
                      ],
                    })
                  }
                >
                  + Nova regra
                </Button>
              </div>

              <p className="text-sm text-ink-600">
                Percentual do salário mínimo, período De/Até. Ex.: 85% · De
                04/2023 · Até 09/2026.
              </p>

              <ul className="space-y-3">
                {estado.regras.map((regra, indice) => (
                  <BlocoRegra
                    key={regra.id}
                    regra={regra}
                    indice={indice}
                    total={estado.regras.length}
                    onChange={(parcial) => alterarRegra(regra.id, parcial)}
                    onRemover={() => removerRegra(regra.id)}
                  />
                ))}
              </ul>
            </section>

            <section className="space-y-3" aria-labelledby="sec-pag-alimentos">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2
                  id="sec-pag-alimentos"
                  className="text-base font-semibold text-ink-900"
                >
                  3. Pagamentos realizados
                </h2>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    atualizar({ pagamentos: [...estado.pagamentos, novoPagamento()] })
                  }
                >
                  + Adicionar pagamento
                </Button>
              </div>

              {estado.pagamentos.length === 0 ? (
                <p className="rounded-lg border border-dashed border-ink-300 bg-white px-3 py-4 text-sm text-ink-500">
                  Nenhum pagamento lançado. Use “+ Adicionar pagamento” para
                  informar o que já foi pago, mês a mês.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-ink-200">
                  <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                    <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-600">
                      <tr>
                        <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                          Competência
                        </th>
                        <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                          Data do pagamento
                        </th>
                        <th scope="col" className="border-b border-ink-200 px-3 py-2.5">
                          Valor pago
                        </th>
                        <th
                          scope="col"
                          className="border-b border-ink-200 px-3 py-2.5 text-right"
                        >
                          Ações
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {estado.pagamentos.map((pagamento, indice) => (
                        <LinhaPagamento
                          key={pagamento.id}
                          pagamento={pagamento}
                          indice={indice}
                          onChange={(parcial) => alterarPagamento(pagamento.id, parcial)}
                          onRemover={() => removerPagamento(pagamento.id)}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <p className="text-xs text-ink-500">
                Ex.: 01/2026 · 10/01/2026 · R$ 200,00 — repita para cada mês pago.
              </p>
            </section>

            <section className="space-y-3" aria-labelledby="sec-atualizacao">
              <h2
                id="sec-atualizacao"
                className="text-base font-semibold text-ink-900"
              >
                4. Atualização
              </h2>
              <div className="max-w-xs">
                <Input
                  id="alimentos-atualizar-ate"
                  label="Atualizar até"
                  required
                  type="date"
                  value={estado.atualizarAte}
                  onChange={(e) => atualizar({ atualizarAte: e.target.value })}
                  hint="Ex.: 30/09/2026 — correção e juros valem até aqui"
                />
              </div>
            </section>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-ink-100 pt-5">
            <Button type="submit" size="lg" disabled={enviando}>
              {enviando ? "Gerando…" : "GERAR CÁLCULO"}
            </Button>
            <Button type="button" variant="ghost" onClick={reiniciar}>
              Limpar formulário
            </Button>
            <span className="text-xs text-ink-500">
              Tabela Prática TJSP + juros de 1% ao mês — automáticos, sem
              configuração extra.
            </span>
          </div>
        </Card>
      </form>
    </div>
  );
}
