import { Link, useSearchParams } from "react-router-dom";
import { Message } from "../components/ui/Message";
import { FormAlimentos } from "../features/novo-calculo/FormAlimentos";
import { FormAtualizacao } from "../features/novo-calculo/FormAtualizacao";
import { FormCivel } from "../features/civel/FormCivel";

const tipos = [
  {
    id: "parcelas",
    titulo: "Cálculo Cível (verbas)",
    resumo: "Lançamento simples de verbas com datas independentes.",
  },
  {
    id: "alimentos",
    titulo: "Alimentos",
    resumo: "Percentual do salário mínimo ou valor fixo por competência.",
  },
  {
    id: "atualizacao",
    titulo: "Atualização monetária",
    resumo: "Valor-base + data final escolhida pelo usuário.",
  },
];

export function NovoCalculoPage() {
  const [params] = useSearchParams();
  const tipo = params.get("tipo") ?? "parcelas";

  if (tipo === "alimentos") {
    return <FormAlimentos />;
  }
  if (tipo === "atualizacao") {
    return <FormAtualizacao />;
  }
  if (tipo === "parcelas" || tipo === "") {
    return <FormCivel />;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
          Tipo desconhecido
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-ink-950">
          Novo cálculo — {tipo}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-600">
          Escolha um dos fluxos disponíveis. Todos enviam o payload para o backend —
          sem regras matemáticas no React.
        </p>
      </div>
      <Message tom="info" title="Fluxos disponíveis">
        <ul className="list-disc space-y-1 pl-5">
          {tipos.map((item) => (
            <li key={item.id}>
              <Link
                to={`/novo-calculo?tipo=${item.id}`}
                className="font-medium text-brand-700 hover:underline"
              >
                {item.titulo}
              </Link>
              {" — "}
              {item.resumo}
            </li>
          ))}
        </ul>
      </Message>
    </div>
  );
}
