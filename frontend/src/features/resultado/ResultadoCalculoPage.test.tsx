import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { CalculoCriado } from "../../types/api";
import { ResultadoCalculoPage } from "./ResultadoCalculoPage";

vi.mock("../../lib/api", () => ({
  api: {
    baseUrl: "http://localhost:8000",
    obterCalculo: vi.fn(),
  },
  formatarDataHora: (valor: unknown) => String(valor ?? ""),
  mensagemErroAmigavel: (erro: unknown) =>
    erro instanceof Error ? erro.message : String(erro),
  rotuloTipoCalculo: () => "Cálculo Cível",
}));

function baseCalculo(parcial: Partial<CalculoCriado>): CalculoCriado {
  return {
    codigo: "VEC-2026-000001",
    tipo: "parcelas",
    titulo: "Caso de teste",
    processo: "",
    parte: "",
    app_version: "1.0.0",
    created_at: "2026-09-30T12:00:00",
    resumo: {
      qtd_parcelas: 1,
      principal: "1000.00",
      total: "1000.00",
      saldo: "1000.00",
      pagamentos: "0.00",
      correcao: "0.00",
      juros: "0.00",
    },
    parcelas: [],
    bases: [],
    memoria: {},
    ...parcial,
  } as CalculoCriado;
}

async function renderizar(calculo: CalculoCriado) {
  vi.mocked(api.obterCalculo).mockResolvedValue(calculo);
  render(
    <MemoryRouter initialEntries={[`/calculos/${calculo.codigo}`]}>
      <Routes>
        <Route path="/calculos/:codigo" element={<ResultadoCalculoPage />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByText("Resumo");
}

beforeEach(() => {
  vi.mocked(api.obterCalculo).mockReset();
});

describe("resultado — Taxa Legal explícita", () => {
  it("mostra “Juros: Taxa Legal (BCB SGS 29543)” quando ela foi aplicada", async () => {
    await renderizar(
      baseCalculo({
        parcelas: [
          {
            numero: 1,
            principal: "44000.00",
            total: "54161.17",
            juros: {
              aplicado: true,
              modalidade: "taxa_legal",
              indexador: "taxa_legal",
              indexador_fonte: "Banco Central do Brasil",
              juros: "2177.36",
            },
          },
        ],
        bases: [
          { key: "taxa_legal", nome: "Taxa Legal (BCB SGS 29543)" },
        ],
      }),
    );

    expect(
      await screen.findByText("Juros: Taxa Legal (BCB SGS 29543)"),
    ).toBeTruthy();
  });

  it("não afirma Taxa Legal quando os juros não foram aplicados", async () => {
    await renderizar(
      baseCalculo({
        parcelas: [
          {
            numero: 1,
            principal: "1000.00",
            total: "1000.00",
            juros: { aplicado: false, modalidade: "nao_aplicar", juros: "0.00" },
          },
        ],
        bases: [],
      }),
    );

    await screen.findByText("Resumo");
    expect(screen.queryByText(/Juros: Taxa Legal/)).toBeNull();
  });
});

describe("resultado — SELIC como critério distinto", () => {
  it("mostra SELIC e nunca a chama de Taxa Legal", async () => {
    await renderizar(
      baseCalculo({
        parcelas: [
          {
            numero: 1,
            principal: "30018.44",
            total: "40000.00",
            correcao: {
              aplicado: true,
              indexador: "selic",
              segmentos: [{ indexador: "tjsp_tabela_pratica" }, { indexador: "selic" }],
            },
            juros: {
              aplicado: true,
              modalidade: "regimes",
              indexador: "selic",
              juros: "1000.00",
            },
          },
        ],
        bases: [
          { key: "tjsp_tabela_pratica", nome: "Tabela Prática TJSP" },
          { key: "selic", nome: "SELIC (BCB)" },
        ],
      }),
    );

    expect(await screen.findByText("Juros: SELIC")).toBeTruthy();
    expect(screen.getByText("Correção: SELIC")).toBeTruthy();
    expect(screen.queryByText(/Taxa Legal/)).toBeNull();
  });
});

describe("resultado — composição no total", () => {
  it("marca apenas a verba fora do total e mantém as demais visíveis", async () => {
    await renderizar(
      baseCalculo({
        memoria: {
          verbas: [
            {
              id: "causa",
              nome: "Valor da causa",
              tipo: "valor",
              entra_no_total: false,
            },
            {
              id: "sucumbencia",
              nome: "Honorários de sucumbência",
              tipo: "percentual",
              entra_no_total: true,
            },
          ],
        } as never,
      }),
    );

    const etiquetas = screen.getAllByText("Fora do total");
    expect(etiquetas).toHaveLength(1);
    expect(etiquetas[0].closest("li")?.textContent).toContain("Valor da causa");

    const itens = screen.getAllByRole("listitem");
    const sucumb = itens.find((li) =>
      li.textContent?.includes("Honorários de sucumbência"),
    );
    expect(sucumb).toBeTruthy();
    expect(sucumb?.textContent).not.toContain("Fora do total");
  });

  it("não exibe a etiqueta quando todas as verbas compõem o total", async () => {
    await renderizar(
      baseCalculo({
        memoria: {
          verbas: [
            { id: "causa", nome: "Valor da causa", tipo: "valor", entra_no_total: true },
          ],
        } as never,
      }),
    );

    expect(screen.queryByText("Fora do total")).toBeNull();
  });
});

describe("resultado — resumo com encargos", () => {
  it("mostra multa, honorários e pagamentos quando calculados", async () => {
    await renderizar(
      baseCalculo({
        resumo: {
          qtd_parcelas: 1,
          principal: "1000.00",
          total: "1300.00",
          saldo: "800.00",
          pagamentos: "500.00",
          correcao: "100.00",
          juros: "100.00",
          multa: "50.00",
          honorarios: "50.00",
        },
      }),
    );

    expect(screen.getByText("Principal")).toBeTruthy();
    expect(screen.getByText("Correção monetária")).toBeTruthy();
    expect(screen.getByText("Juros")).toBeTruthy();
    expect(screen.getByText("Multa")).toBeTruthy();
    expect(screen.getByText("Honorários")).toBeTruthy();
    expect(screen.getByText("Total atualizado")).toBeTruthy();
    expect(screen.getByText("Pagamentos e abatimentos")).toBeTruthy();
    expect(screen.getByText("Saldo final")).toBeTruthy();
  });

  it("oculta correção, juros, multa, honorários e pagamentos zerados", async () => {
    await renderizar(baseCalculo({}));

    expect(screen.getByText("Principal")).toBeTruthy();
    expect(screen.getByText("Total atualizado")).toBeTruthy();
    expect(screen.getByText("Saldo final")).toBeTruthy();
    expect(screen.queryByText("Correção monetária")).toBeNull();
    expect(screen.queryByText(/^Juros$/)).toBeNull();
    expect(screen.queryByText("Multa")).toBeNull();
    expect(screen.queryByText("Honorários")).toBeNull();
    expect(screen.queryByText("Pagamentos e abatimentos")).toBeNull();
  });
});

describe("resultado — retorno ao formulário", () => {
  it("volta por revisão, para preservar o cálculo salvo", async () => {
    await renderizar(baseCalculo({}));
    expect(screen.getByRole("link", { name: "Voltar ao cálculo" }).getAttribute("href"))
      .toBe("/novo-calculo?tipo=parcelas&revisar=VEC-2026-000001");
    expect(screen.getByRole("link", { name: "Criar revisão" }).getAttribute("href"))
      .toBe("/novo-calculo?tipo=parcelas&revisar=VEC-2026-000001");
  });

  it("avisa quais verbas ficaram sem juros ou correção", async () => {
    await renderizar(baseCalculo({
      parcelas: [{
        verba: { nome: "parcelas fls. 3" },
        juros: { aplicado: false },
        correcao: { aplicado: false },
      }],
    }));
    expect(screen.getByText("Confira antes de exportar")).toBeTruthy();
    expect(screen.getByText(/parcelas fls\. 3: juros não aplicados/i)).toBeTruthy();
    expect(screen.getByText(/parcelas fls\. 3: correção monetária não aplicada/i)).toBeTruthy();
  });
});
