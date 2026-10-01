import { useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { Message } from "../components/ui/Message";
import { Tooltip } from "../components/ui/Tooltip";

const tipos = [
  {
    id: "parcelas",
    titulo: "Cálculo Cível (parcelas)",
    resumo: "Parcelas com correção, juros, multa, honorários e pagamentos.",
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
  const tipo = params.get("tipo") ?? "";

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
            Preparação
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-ink-950">Novo cálculo</h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            A estrutura de entrada está pronta. O formulário completo (regras de
            alimentos, blocos, pagamentos e datas) será ligado ao backend na próxima
            etapa — sem duplicar lógica de índices no React.
          </p>
        </div>
        <Tooltip text="O POST /api/calculos recebe o payload; o motor Python calcula; a resposta traz memória, PDF e XLSX." />
      </div>

      <Message tom="info" title="Formulário completo em breve">
        Esta tela mapeia o que será implementado. Enquanto isso, use a API
        validada (<code className="font-mono">POST /api/calculos</code>) para
        testar cálculos reais.
      </Message>

      <div className="grid gap-4 md:grid-cols-3">
        {tipos.map((item) => {
          const ativo = tipo === item.id;
          return (
            <Card
              key={item.id}
              title={item.titulo}
              description={item.resumo}
              className={ativo ? "border-brand-300 ring-2 ring-brand-500/20" : ""}
            >
              <p className="text-xs text-ink-500">
                {ativo
                  ? "Tipo selecionado na URL — pronto para o formulário."
                  : "Aguardando implementação do formulário."}
              </p>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
