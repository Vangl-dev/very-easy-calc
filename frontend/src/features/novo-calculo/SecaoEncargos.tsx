import { Input, Select } from "../../components/ui/Form";
import { Switch } from "../../components/ui/Switch";
import { Tooltip } from "../../components/ui/Tooltip";

export interface EstadoEncargo {
  aplicar: boolean;
  percentual: string;
  valorFixo: string;
  base: string;
  modalidade: string;
  unidade: string;
  indexador: string;
}

export interface EstadoEncargos {
  correcao: { aplicar: boolean; indexador: string };
  juros: EstadoEncargo;
  multa: EstadoEncargo;
  honorarios: EstadoEncargo;
}

export function encargoVazio(aplicar = false): EstadoEncargo {
  return {
    aplicar,
    percentual: "",
    valorFixo: "",
    base: "corrigido",
    modalidade: "taxa_legal",
    unidade: "mensal",
    indexador: "tjsp_tabela_pratica",
  };
}

interface Props {
  valor: EstadoEncargos;
  onChange: (parcial: Partial<EstadoEncargos>) => void;
  jurosDisponiveis: boolean;
}

export function SecaoEncargos({ valor, onChange, jurosDisponiveis }: Props) {
  return (
    <section className="space-y-4" aria-labelledby="sec-encargos">
      <div className="flex items-center gap-2">
        <h2 id="sec-encargos" className="text-base font-semibold text-ink-900">
          3. Correção, juros e encargos
        </h2>
        <Tooltip text="Cada componente é opcional. 'Não aplicar' é uma regra válida e explícita — o backend só calcula o que estiver habilitado." />
      </div>

      <div className="space-y-3">
        <Switch
          id="correcao-aplicar"
          checked={valor.correcao.aplicar}
          onChange={(aplicar) =>
            onChange({ correcao: { ...valor.correcao, aplicar } })
          }
          label="Aplicar correção monetária"
          description="Atualiza o valor-base com o índice oficial (Tabela Prática TJSP) entre a data-base e a data-final."
        />
        {valor.correcao.aplicar ? (
          <div className="rounded-xl border border-ink-200 bg-white p-4">
            <Select
              id="correcao-indexador"
              label="Indexador de correção"
              value={valor.correcao.indexador}
              onChange={(e) =>
                onChange({
                  correcao: { ...valor.correcao, indexador: e.target.value },
                })
              }
              tooltip="Série oficial versionada no backend. O frontend não aplica fatores."
            >
              <option value="tjsp_tabela_pratica">
                Tabela Prática TJSP (correção monetária)
              </option>
            </Select>
          </div>
        ) : (
          <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
            Correção monetária <strong>não aplicada</strong> — o principal será
            mantido como informado.
          </p>
        )}
      </div>

      <div className="space-y-3">
        <Switch
          id="juros-aplicar"
          checked={valor.juros.aplicar}
          onChange={(aplicar) => onChange({ juros: { ...valor.juros, aplicar } })}
          label="Aplicar juros"
          description="Juros entre a data-base do valor e a data-final do cálculo, conforme a modalidade escolhida no backend."
        />
        {valor.juros.aplicar ? (
          <div className="grid gap-4 rounded-xl border border-ink-200 bg-white p-4 md:grid-cols-2">
            <Select
              id="juros-modalidade"
              label="Modalidade de juros"
              value={valor.juros.modalidade}
              onChange={(e) =>
                onChange({ juros: { ...valor.juros, modalidade: e.target.value } })
              }
              tooltip="Taxa Legal usa a série oficial BCB SGS 29543 no backend."
            >
              <option value="taxa_legal">Taxa Legal (BCB SGS 29543)</option>
              <option value="nao_aplicar">Não aplicar (mesmo com o interruptor ligado)</option>
            </Select>
            <Select
              id="juros-base"
              label="Base de incidência"
              value={valor.juros.base}
              onChange={(e) =>
                onChange({ juros: { ...valor.juros, base: e.target.value } })
              }
              tooltip="Sobre qual montante os juros incidem. Definido no backend."
            >
              <option value="corrigido">Valor corrigido</option>
              <option value="principal">Principal histórico</option>
              <option value="com_juros">Principal + correção + juros</option>
            </Select>
          </div>
        ) : (
          <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
            Juros <strong>não aplicados</strong> (parâmetro explícito do usuário).
          </p>
        )}
        {!jurosDisponiveis ? (
          <p className="text-xs text-ink-500">
            A base de juros (Taxa Legal) pode não cobrir datas futuras além da série
            oficial — o backend avisará se faltar cobertura.
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-2xl border border-ink-200 bg-white p-4">
          <Switch
            id="multa-aplicar"
            checked={valor.multa.aplicar}
            onChange={(aplicar) => onChange({ multa: { ...valor.multa, aplicar } })}
            label="Multa"
            description="Percentual ou valor fixo sobre a base configurada."
          />
          {valor.multa.aplicar ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                id="multa-percentual"
                label="Percentual da multa"
                inputMode="decimal"
                value={valor.multa.percentual}
                onChange={(e) =>
                  onChange({ multa: { ...valor.multa, percentual: e.target.value } })
                }
                placeholder="0.02"
                hint="Ex.: 0.02 = 2%"
                tooltip="Informe apenas um modo: percentual OU valor fixo."
              />
              <Input
                id="multa-valor"
                label="Valor fixo da multa"
                inputMode="decimal"
                value={valor.multa.valorFixo}
                onChange={(e) =>
                  onChange({ multa: { ...valor.multa, valorFixo: e.target.value } })
                }
                placeholder="150,00"
                hint="Use se não for percentual"
              />
              <Select
                id="multa-base"
                label="Base da multa"
                value={valor.multa.base}
                onChange={(e) =>
                  onChange({ multa: { ...valor.multa, base: e.target.value } })
                }
                className="sm:col-span-2"
                tooltip="O backend aplica o percentual/valor sobre esta base já calculada."
              >
                <option value="corrigido">Valor corrigido</option>
                <option value="principal">Principal histórico</option>
                <option value="com_juros">Principal + correção + juros</option>
              </Select>
            </div>
          ) : null}
        </div>

        <div className="space-y-3 rounded-2xl border border-ink-200 bg-white p-4">
          <Switch
            id="honorarios-aplicar"
            checked={valor.honorarios.aplicar}
            onChange={(aplicar) =>
              onChange({ honorarios: { ...valor.honorarios, aplicar } })
            }
            label="Honorários"
            description="Percentual ou valor fixo sobre a base configurada."
          />
          {valor.honorarios.aplicar ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                id="honorarios-percentual"
                label="Percentual dos honorários"
                inputMode="decimal"
                value={valor.honorarios.percentual}
                onChange={(e) =>
                  onChange({
                    honorarios: { ...valor.honorarios, percentual: e.target.value },
                  })
                }
                placeholder="0.10"
                hint="Ex.: 0.10 = 10%"
              />
              <Input
                id="honorarios-valor"
                label="Valor fixo dos honorários"
                inputMode="decimal"
                value={valor.honorarios.valorFixo}
                onChange={(e) =>
                  onChange({
                    honorarios: { ...valor.honorarios, valorFixo: e.target.value },
                  })
                }
                placeholder="500,00"
              />
              <Select
                id="honorarios-base"
                label="Base dos honorários"
                value={valor.honorarios.base}
                onChange={(e) =>
                  onChange({
                    honorarios: { ...valor.honorarios, base: e.target.value },
                  })
                }
                className="sm:col-span-2"
              >
                <option value="corrigido">Valor corrigido</option>
                <option value="principal">Principal histórico</option>
                <option value="com_juros">Principal + correção + juros</option>
              </Select>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
