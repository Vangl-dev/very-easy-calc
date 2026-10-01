import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Message } from "../../components/ui/Message";
import { Tooltip } from "../../components/ui/Tooltip";

export type Passo = "formulario" | "revisao" | "sucesso";

interface CabecalhoProps {
  eyebrow: string;
  titulo: string;
  descricao: string;
  dica: string;
}

export function CabecalhoFormulario({ eyebrow, titulo, descricao, dica }: CabecalhoProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
          {eyebrow}
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-ink-950">{titulo}</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-600">{descricao}</p>
      </div>
      <Tooltip text={dica} />
    </div>
  );
}

interface RevisaoProps {
  erros: string[];
  erroEnvio: string | null;
  enviando: boolean;
  children: React.ReactNode;
  onVoltar: () => void;
  onEnviar: () => void;
}

export function CartaoRevisao({
  erros,
  erroEnvio,
  enviando,
  children,
  onVoltar,
  onEnviar,
}: RevisaoProps) {
  return (
    <Card
      title="Revisão antes do envio"
      description="Confira os dados enviados ao backend"
    >
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
      <div className="mt-4">{children}</div>
      <div className="mt-6 flex flex-wrap gap-3 border-t border-ink-100 pt-5">
        <Button
          type="button"
          size="lg"
          onClick={onEnviar}
          disabled={enviando || erros.length > 0}
        >
          {enviando ? "Enviando…" : "Confirmar e calcular no backend"}
        </Button>
        <Button type="button" variant="outline" onClick={onVoltar}>
          Voltar e editar
        </Button>
      </div>
    </Card>
  );
}

export function CampoResumo({
  rotulo,
  valor,
}: {
  rotulo: string;
  valor: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs uppercase text-ink-500">{rotulo}</dt>
      <dd className="mt-0.5 text-sm font-medium text-ink-900">{valor}</dd>
    </div>
  );
}
