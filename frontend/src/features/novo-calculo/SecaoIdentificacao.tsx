import { Input } from "../../components/ui/Form";

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
    <section className="space-y-5" aria-labelledby="sec-identificacao">
      <div>
        <p className="section-kicker">Identificação</p>
        <h2 id="sec-identificacao" className="section-title mt-1">
          Dados do cálculo
        </h2>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Input
          id="titulo"
          label="Nome / descrição"
          required
          value={valor.titulo}
          onChange={(e) => onChange({ titulo: e.target.value })}
          placeholder="Ex.: Execução de sentença — honorários"
        />
        <Input
          id="processo"
          label="Processo"
          value={valor.processo}
          onChange={(e) => onChange({ processo: e.target.value })}
          placeholder="0000000-00.0000.0.00.0000"
        />
        <Input
          id="parte"
          label="Parte"
          value={valor.parte}
          onChange={(e) => onChange({ parte: e.target.value })}
          placeholder="Ex.: Autor / Requerido"
          className="md:col-span-2"
        />
      </div>
    </section>
  );
}
