import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { listarRascunhos, salvarRascunho, type RascunhoCivel } from "../lib/rascunhos";
import type { CalculoResumo } from "../types/api";
import { DashboardPage } from "./DashboardPage";

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      health: vi.fn(),
      listarCalculos: vi.fn(),
      excluirCalculo: vi.fn(),
      limparCalculos: vi.fn(),
    },
  };
});

const DOIS: CalculoResumo[] = [
  {
    codigo: "VEC-2026-000001",
    tipo: "parcelas",
    titulo: "Caso um",
    processo: "0000001-00.2026.8.26.0001",
    parte: "Autor",
    app_version: "1.0.0",
    created_at: "2026-09-01T12:00:00+00:00",
  },
  {
    codigo: "VEC-2026-000002",
    tipo: "alimentos",
    titulo: "Caso dois",
    processo: "0000002-00.2026.8.26.0002",
    parte: "Autor",
    app_version: "1.0.0",
    created_at: "2026-09-02T12:00:00+00:00",
  },
];

function renderizar() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

function rascunhoExemplo(titulo: string): RascunhoCivel {
  return salvarRascunho({
    identificacao: { titulo, processo: "", parte: "" },
    dataBaseCalculo: "",
    indexador: "tjsp_tabela_pratica",
    verbas: [],
  });
}

async function aguardarTabela() {
  await screen.findByRole("checkbox", {
    name: /selecionar cálculo vec-2026-000001/i,
  });
  await waitFor(() => {
    expect(
      (screen.getByRole("button", { name: /limpar tudo/i }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.health).mockReset();
  vi.mocked(api.health).mockResolvedValue({
    status: "ok",
    app: "Very Easy Calc",
    version: "1.0.0",
  });
  vi.mocked(api.listarCalculos).mockReset();
  vi.mocked(api.listarCalculos).mockResolvedValue(DOIS);
  vi.mocked(api.excluirCalculo).mockReset();
  vi.mocked(api.excluirCalculo).mockResolvedValue(undefined);
  vi.mocked(api.limparCalculos).mockReset();
  vi.mocked(api.limparCalculos).mockResolvedValue({ excluidos: 2 });
});

describe("Cálculos recentes — gerenciamento", () => {
  it("4. exclui o cálculo selecionado", async () => {
    vi.mocked(api.listarCalculos)
      .mockResolvedValueOnce(DOIS)
      .mockResolvedValueOnce([DOIS[1]]);
    renderizar();
    await aguardarTabela();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /selecionar cálculo vec-2026-000001/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: /excluir selecionados/i }));

    await waitFor(() => {
      expect(api.excluirCalculo).toHaveBeenCalledWith("VEC-2026-000001");
    });
    expect(api.excluirCalculo).toHaveBeenCalledTimes(1);
    expect(api.limparCalculos).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(
        screen.queryByRole("checkbox", {
          name: /selecionar cálculo vec-2026-000001/i,
        }),
      ).toBeNull();
    });
    expect(
      screen.getByRole("checkbox", { name: /selecionar cálculo vec-2026-000002/i }),
    ).toBeTruthy();
  });

  it("5. limpar todos os cálculos exige confirmação e não apaga rascunhos", async () => {
    rascunhoExemplo("Rascunho que fica");
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderizar();
    await aguardarTabela();

    fireEvent.click(screen.getByRole("button", { name: /limpar tudo/i }));

    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(api.limparCalculos).not.toHaveBeenCalled();
    expect(listarRascunhos()).toHaveLength(1);

    confirmar.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: /limpar tudo/i }));

    await waitFor(() => {
      expect(api.limparCalculos).toHaveBeenCalledTimes(1);
    });
    expect(listarRascunhos()).toHaveLength(1);
    confirmar.mockRestore();
  });
});

describe("Rascunhos", () => {
  it("8. exclui rascunho sem tocar nos cálculos concluídos", async () => {
    const salvo = rascunhoExemplo("Meu rascunho");
    renderizar();

    expect(await screen.findByText("Meu rascunho")).toBeTruthy();
    const continuar = screen.getByRole("link", { name: /continuar/i });
    expect(continuar.getAttribute("href")).toContain(
      `rascunho=${encodeURIComponent(salvo.id)}`,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Excluir rascunho Meu rascunho" }),
    );

    expect(listarRascunhos()).toHaveLength(0);
    expect(screen.queryByText("Meu rascunho")).toBeNull();
    expect(api.excluirCalculo).not.toHaveBeenCalled();
    expect(api.limparCalculos).not.toHaveBeenCalled();
  });
});
