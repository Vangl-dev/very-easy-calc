import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { CalculoAlimentosPayload, CalculoCriado } from "../../types/api";
import { FormAlimentos } from "./FormAlimentos";

vi.mock("../../lib/api", () => ({
  api: { criarCalculo: vi.fn() },
  mensagemErroAmigavel: (erro: unknown) =>
    erro instanceof Error ? erro.message : String(erro),
}));

function Resultado() {
  const { codigo } = useParams<{ codigo: string }>();
  return <p>resultado {codigo}</p>;
}

function renderizar() {
  return render(
    <MemoryRouter initialEntries={["/novo-calculo?tipo=alimentos"]}>
      <Routes>
        <Route path="/novo-calculo" element={<FormAlimentos />} />
        <Route path="/calculos/:codigo" element={<Resultado />} />
      </Routes>
    </MemoryRouter>,
  );
}

function digitar(rotulo: RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } });
}

function digitarUltimo(rotulo: RegExp, valor: string) {
  const campos = screen.getAllByLabelText(rotulo);
  fireEvent.change(campos[campos.length - 1], { target: { value: valor } });
}

function botao(nome: RegExp) {
  return screen.getByRole("button", { name: nome });
}

function preencherIdentificacaoEPadrao() {
  digitar(/^nome \/ descrição/i, "Alimentos — 85% do salário mínimo");
  digitar(/^mês\/ano inicial/i, "04/2023");
  digitar(/^percentual do salário mínimo/i, "85");
  digitar(/^atualizar até/i, "2026-09-30");
}

beforeEach(() => {
  vi.mocked(api.criarCalculo).mockReset();
  vi.mocked(api.criarCalculo).mockResolvedValue({
    codigo: "VEC-2026-000001",
  } as CalculoCriado);
});

describe("FormAlimentos", () => {
  it("exibe os erros de validação ao gerar cálculo com dado inválido (regressão do botão mudo)", async () => {
    renderizar();
    preencherIdentificacaoEPadrao();
    digitar(/^mês\/ano inicial/i, "abr/2023");

    fireEvent.click(botao(/gerar cálculo/i));

    expect(
      await screen.findByText(/Regra 1: início inválido — use MM\/AAAA/i),
    ).toBeTruthy();
    expect(api.criarCalculo).not.toHaveBeenCalled();
  });

  it("aponta todos os campos pendentes, inclusive a data da atualização", async () => {
    renderizar();
    fireEvent.click(botao(/gerar cálculo/i));

    expect(await screen.findByText(/Informe o nome\/descrição do cálculo/i)).toBeTruthy();
    expect(screen.getByText(/Informe a data da atualização/i)).toBeTruthy();
    expect(screen.getByText(/Regra 1: informe o mês\/ano inicial/i)).toBeTruthy();
    expect(api.criarCalculo).not.toHaveBeenCalled();
  });

  it("gera o cálculo com percentual convertido, correção e juros automáticos", async () => {
    renderizar();
    preencherIdentificacaoEPadrao();

    fireEvent.click(botao(/adicionar pagamento/i));
    digitarUltimo(/^competência/i, "01/2026");
    digitarUltimo(/^data do pagamento/i, "2026-01-10");
    digitarUltimo(/^valor pago/i, "200,00");

    fireEvent.click(botao(/gerar cálculo/i));

    expect(await screen.findByText(/resultado VEC-2026-000001/i)).toBeTruthy();

    const payload = vi.mocked(api.criarCalculo).mock.calls[0][0] as CalculoAlimentosPayload;
    expect(payload.tipo).toBe("alimentos");
    expect(payload.data_base).toBe("2026-09-30");
    expect(payload.alimentos.ate).toBe("09/2026");
    expect(payload.alimentos.regras[0]).toMatchObject({
      inicio: "04/2023",
      tipo: "salario_minimo",
      percentual: "0.85",
    });
    expect(payload.correcao).toMatchObject({
      aplicar: true,
      indexador: "tjsp_tabela_pratica",
    });
    expect(payload.juros).toMatchObject({
      aplicar: true,
      modalidade: "fixa",
      taxa: "0.01",
    });
    expect(payload.pagamentos).toEqual([
      {
        competencia: "01/2026",
        data: "2026-01-10",
        valor: "200,00",
        descricao: "",
      },
    ]);
  });

  it("mantém cada pagamento na sua competência ao lançar vários meses", async () => {
    renderizar();
    preencherIdentificacaoEPadrao();

    for (const mes of ["01", "02", "03"]) {
      fireEvent.click(botao(/adicionar pagamento/i));
      digitarUltimo(/^competência/i, `${mes}/2026`);
      digitarUltimo(/^data do pagamento/i, `2026-${mes}-10`);
      digitarUltimo(/^valor pago/i, "200,00");
    }

    fireEvent.click(botao(/gerar cálculo/i));
    expect(await screen.findByText(/resultado VEC-2026-000001/i)).toBeTruthy();

    const payload = vi.mocked(api.criarCalculo).mock.calls[0][0] as CalculoAlimentosPayload;
    expect((payload.pagamentos ?? []).map((p) => p.competencia)).toEqual([
      "01/2026",
      "02/2026",
      "03/2026",
    ]);
    expect((payload.pagamentos ?? []).map((p) => p.data)).toEqual([
      "2026-01-10",
      "2026-02-10",
      "2026-03-10",
    ]);
  });
});
