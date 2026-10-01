import { Input } from "../../components/ui/Form";
import { Tooltip } from "../../components/ui/Tooltip";

export interface EstadoIdentificacao {
  titulo: string;
  processo: string;
  parte: string;
}

interface Props {
  valor: EstadoIdentificacao;
  onChange: (parcial: Partial<EstadoIdentificacao>) => void;
}

export function SecaoIdentificacao({ valor, onChange }: Props) {
  return (
    <section className="space-y-4" aria-labelledby="sec-identificacao">
      <div className="flex items-center gap-2">
        <h2 id="sec-identificacao" className="text-base font-semibold text-ink-900">
          1. Identificação do cálculo
        </h2>
        <Tooltip text="Campos livres para organização. Não alteram a matemática — apenas identificam o processo na memória e nos relatórios." />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          id="titulo"
          label="Nome / descrição"
          required
          value={valor.titulo}
          onChange={(e) => onChange({ titulo: e.target.value })}
          placeholder="Ex.: Execução de sentença — honorários"
          tooltip="Aparece no cabeçalho do PDF/XLSX e na lista de cálculos."
        />
        <Input
          id="processo"
          label="Processo"
          value={valor.processo}
          onChange={(e) => onChange({ processo: e.target.value })}
          placeholder="0000000-00.0000.0.00.0000"
          tooltip="Número do processo (opcional). Usado apenas para rastreabilidade."
        />
        <Input
          id="parte"
          label="Parte"
          value={valor.parte}
          onChange={(e) => onChange({ parte: e.target.value })}
          placeholder="Ex.: Autor / Requerido"
          tooltip="Identificação da parte no cálculo (opcional)."
          className="md:col-span-2"
        />
      </div>
    </section>
  );
}
