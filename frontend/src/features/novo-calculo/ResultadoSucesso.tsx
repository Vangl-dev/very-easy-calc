import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Message } from "../../components/ui/Message";
import { api } from "../../lib/api";
import type { CalculoCriado } from "../../types/api";

interface Props {
  resultado: CalculoCriado;
  onReiniciar: () => void;
}

export function ResultadoSucesso({ resultado, onReiniciar }: Props) {
  return (
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
          <dd className="mt-1 text-sm font-medium text-ink-900">{resultado.tipo}</dd>
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
        <Button type="button" onClick={onReiniciar}>
          Criar outro cálculo
        </Button>
      </div>
    </Card>
  );
}
