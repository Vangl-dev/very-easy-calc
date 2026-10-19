import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { listarRascunhos, salvarRascunho } from "../../lib/rascunhos";
import type { CalculoCivelPayload, CalculoCriado, CoberturaEfetiva } from "../../types/api";
import { FormCivel } from "./FormCivel";
import {
  anexarPagamentosGlobais,
  aplicarEncargoGeral,
  errosPagamentos,
  errosRegimes,
  errosVerbas,
  fracaoDePercentual,
  montarRegimesPayload,
  montarVerbaPayload,
  novaPagamento,
  novaRegime,
  novaVerba,
  podeRemoverVerba,
  resumoVerba,
  type EstadoVerba,
} from "./estadoVerba";

vi.mock("../../lib/api", () => ({
  api: {
    criarCalculo: vi.fn(),
    coberturaIndexador: vi.fn(),
    obterCalculo: vi.fn(),
  },
  mensagemErroAmigavel: (erro: unknown) =>
    erro instanceof Error ? erro.message : String(erro),
}));

function Resultado() {
  const { codigo } = useParams<{ codigo: string }>();
  return <p>resultado {codigo}</p>;
}

const coberturaTjsp: CoberturaEfetiva = {
  key: "tjsp_tabela_pratica",
  oficial: {
    inicio: "1990-01",
    fim: "2026-09",
    inicio_rotulo: "janeiro/1990",
    fim_rotulo: "setembro/2026",
    total: 429,
    version: "2026.09",
    name: "Tabela Prática TJSP",
    kind: "correcao",
    source: "AASP",
  },
  manual: [],
  cobertura_efetiva: {
    inicio: "1990-01",
    fim: "2026-09",
    inicio_rotulo: "janeiro/1990",
    fim_rotulo: "setembro/2026",
    total: 429,
    inclui_manual: false,
  },
  nota: "",
};

/** Os testes legados exercitam o modo detalhado; o modo simples é o padrão da URL limpa. */
function renderizar(entrada = "/novo-calculo?tipo=parcelas&modo=detalhado") {
  return render(
    <MemoryRouter initialEntries={[entrada]}>
      <Routes>
        <Route path="/novo-calculo" element={<FormCivel />} />
        <Route path="/calculos/:codigo" element={<Resultado />} />
      </Routes>
    </MemoryRouter>,
  );
}

function camposDe(rotulo: RegExp): HTMLInputElement[] {
  return screen
    .getAllByLabelText(rotulo)
    .filter(
      (el): el is HTMLInputElement =>
        el instanceof HTMLInputElement && el.type !== "radio",
    );
}

function digitar(rotulo: RegExp, valor: string, indice = 0) {
  fireEvent.change(camposDe(rotulo)[indice], { target: { value: valor } });
}

function selecionarBase(rotuloBase: string, indice = 0) {
  const selects = screen
    .getAllByLabelText(/^sobre/i)
    .filter((el): el is HTMLSelectElement => el instanceof HTMLSelectElement);
  const select = selects[indice];
  const opcao = Array.from(select.options).find((o) =>
    o.textContent?.includes(rotuloBase),
  );
  fireEvent.change(select, { target: { value: opcao?.value ?? "" } });
}

function botao(nome: RegExp) {
  return screen.getByRole("button", { name: nome });
}

/** Fluxo novo: testes que cobrem outro comportamento confirmam o aviso sem
 * perder as assertions originais sobre o payload enviado. */
function confirmarCriteriosSeNecessario() {
  const confirmar = screen.queryByRole("button", {
    name: "Manter configurações e calcular",
  });
  if (confirmar) fireEvent.click(confirmar);
}

interface DadosLinha {
  correcao: string;
  juros?: string;
  descricao: string;
  valor?: string;
}

function ativarJuros(indice: number) {
  const controle = screen.getByRole("checkbox", {
    name: new RegExp(`aplicar juros no lançamento ${indice + 1}`, "i"),
  }) as HTMLInputElement;
  // Uma nova linha herda juros quando todas as anteriores já os utilizam.
  // O auxiliar deve garantir o estado ligado, sem inverter a escolha herdada.
  if (!controle.checked) fireEvent.click(controle);
}

async function preencherLinha(indice: number, dados: DadosLinha) {
  digitar(/^correção desde/i, dados.correcao, indice);
  if (dados.juros) {
    ativarJuros(indice);
    await waitFor(() => {
      expect(camposDe(/^juros desde/i)).toHaveLength(indice + 1);
    });
    digitar(/^juros desde/i, dados.juros, indice);
  }
  if (dados.valor !== undefined) digitar(/^valor/i, dados.valor, indice);
  digitar(/^descrição/i, dados.descricao, indice);
}

async function preencherCasoDerivado(options?: { datasDiferentes?: boolean }) {
  renderizar();
  digitar(/^nome \/ descrição/i, "Cível — causa e sucumbência");
  digitar(/^atualizar cálculo até/i, "2026-09-30");

  await preencherLinha(0, {
    correcao: "2022-08-30",
    juros: "2026-04-24",
    valor: "44000,00",
    descricao: "Valor da causa",
  });

  fireEvent.click(botao(/\+ adicionar valor/i));
  await waitFor(() => {
    expect(camposDe(/^correção desde/i)).toHaveLength(2);
  });

  await preencherLinha(1, {
    correcao: options?.datasDiferentes ? "2023-01-01" : "2022-08-30",
    juros: options?.datasDiferentes ? "2024-05-10" : "2026-04-24",
    descricao: "Honorários de sucumbência",
  });

  fireEvent.click(
    botao(/usar percentual de outra verba no lançamento 2/i),
  );
  digitar(/^percentual/i, "12");
  selecionarBase("Valor da causa");
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.criarCalculo).mockReset();
  vi.mocked(api.criarCalculo).mockResolvedValue({
    codigo: "VEC-2026-000010",
  } as CalculoCriado);
  vi.mocked(api.coberturaIndexador).mockReset();
  vi.mocked(api.coberturaIndexador).mockRejectedValue(new Error("offline"));
  vi.mocked(api.obterCalculo).mockReset();
});

describe("estadoVerba — verbas derivadas", () => {
  it("converte 12% em 0.12 para o payload", () => {
    expect(fracaoDePercentual("12")).toBe("0.12");
    expect(fracaoDePercentual("12,5")).toBe("0.125");
  });

  it("monta payload de verba derivada com base_verba_id e percentual", () => {
    const base = novaVerba({
      id: "causa",
      nome: "Valor da causa",
      valor: "44000,00",
      correcaoInicio: "2022-08-30",
      jurosInicio: "2026-04-24",
      jurosAplicar: true,
    });
    const derivada = novaVerba({
      id: "sucumbencia",
      tipo: "percentual",
      nome: "Honorários de sucumbência",
      percentual: "12",
      baseVerbaId: "causa",
      correcaoInicio: "2022-08-30",
      jurosInicio: "2026-04-24",
      jurosAplicar: true,
    });

    const pBase = montarVerbaPayload(base, "2026-09-30");
    const pDer = montarVerbaPayload(derivada, "2026-09-30");

    expect(pBase.tipo).toBe("valor");
    expect(pBase.valor).toBe("44000,00");
    expect(pBase.id).toBe("causa");

    expect(pDer.tipo).toBe("percentual");
    expect(pDer.base_verba_id).toBe("causa");
    expect(pDer.percentual).toBe("0.12");
    expect(pDer.valor).toBeNull();
    expect(pDer.correcao?.termo_inicial).toBe("2022-08-30");
    expect(pDer.juros?.inicio).toBe("2026-04-24");
  });

  it("não copia datas da base automaticamente — cada verba tem as suas", () => {
    const base = novaVerba({
      id: "causa",
      nome: "Valor da causa",
      valor: "44000,00",
      correcaoInicio: "2022-08-30",
      jurosInicio: "2026-04-24",
      jurosAplicar: true,
    });
    const derivada = novaVerba({
      id: "hon",
      tipo: "percentual",
      nome: "Honorários",
      percentual: "12",
      baseVerbaId: "causa",
      correcaoInicio: "2023-01-01",
      jurosInicio: "2024-05-10",
      jurosAplicar: true,
    });
    const payload = montarVerbaPayload(derivada, "2026-09-30");
    expect(payload.correcao?.termo_inicial).toBe("2023-01-01");
    expect(payload.juros?.inicio).toBe("2024-05-10");
    expect(payload.correcao?.termo_inicial).not.toBe(
      montarVerbaPayload(base, "2026-09-30").correcao?.termo_inicial,
    );
  });

  it("impede remover verba que é base de outra", () => {
    const base = novaVerba({ id: "causa", nome: "Valor da causa", valor: "100" });
    const derivada = novaVerba({
      id: "hon",
      tipo: "percentual",
      nome: "Honorários",
      percentual: "12",
      baseVerbaId: "causa",
    });
    const bloqueio = podeRemoverVerba("causa", [base, derivada]);
    expect(bloqueio.ok).toBe(false);
    expect(bloqueio.motivos[0]).toContain("Honorários");
    expect(podeRemoverVerba("hon", [base, derivada]).ok).toBe(true);
  });

  it("resumo visual mostra 12% de… sem virar texto no campo Valor", () => {
    const derivada = novaVerba({
      tipo: "percentual",
      nome: "Honorários de sucumbência",
      percentual: "12",
      baseVerbaId: "causa",
    });
    const mapa = new Map([["causa", "Valor da causa"]]);
    expect(resumoVerba(derivada, mapa)).toBe("12% de Valor da causa");
    expect(derivada.valor).toBe("");
  });
});

describe("FormCivel — lista de lançamentos", () => {
  it("cria o caso 44.000 + 12% de sucumbência e envia payload estruturado", async () => {
    await preencherCasoDerivado();

    expect(screen.getAllByText(/12% de Valor da causa/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/R\$ 44\.000,00 × 12% = R\$ 5\.280,00/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/^R\$ 5\.280,00$/)).toBeTruthy();

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.data_base).toBe("2026-09-30");
    expect(payload.verbas).toHaveLength(2);

    const [causa, sucumb] = payload.verbas;
    expect(causa.tipo).toBe("valor");
    expect(causa.valor).toBe("44000,00");
    expect(causa.data_base).toBe("2022-08-30");
    expect(causa.correcao?.indexador).toBe("tjsp_tabela_pratica");
    expect(causa.correcao?.termo_inicial).toBe("2022-08-30");
    expect(causa.juros?.inicio).toBe("2026-04-24");

    expect(sucumb.tipo).toBe("percentual");
    expect(sucumb.base_verba_id).toBe(causa.id);
    expect(sucumb.percentual).toBe("0.12");
    expect(sucumb.valor).toBeNull();
    expect(sucumb.correcao?.termo_inicial).toBe("2022-08-30");
    expect(sucumb.juros?.inicio).toBe("2026-04-24");

    expect(String(sucumb.valor ?? "")).not.toMatch(/%/);
  });

  it("permite datas diferentes na verba derivada", async () => {
    await preencherCasoDerivado({ datasDiferentes: true });

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    const [, hon] = payload.verbas;
    expect(hon.correcao?.termo_inicial).toBe("2023-01-01");
    expect(hon.juros?.inicio).toBe("2024-05-10");
  });

  it("impede remover lançamento que é base de outro", async () => {
    renderizar();
    digitar(/^nome \/ descrição/i, "Dependências");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    await preencherLinha(0, {
      correcao: "2022-08-30",
      juros: "2026-04-24",
      valor: "100,00",
      descricao: "Valor da causa",
    });

    fireEvent.click(botao(/\+ adicionar valor/i));
    await preencherLinha(1, {
      correcao: "2022-08-30",
      juros: "2026-04-24",
      descricao: "Sucumbência",
    });
    fireEvent.click(
      botao(/usar percentual de outra verba no lançamento 2/i),
    );
    digitar(/^percentual/i, "12");
    selecionarBase("Valor da causa");

    await waitFor(() => {
      expect(screen.getAllByText(/usada como base por/i).length).toBeGreaterThan(0);
    });

    fireEvent.click(botao(/remover lançamento 1/i));

    await waitFor(() => {
      expect(screen.getByText(/depende desta verba/i)).toBeTruthy();
    });
    expect(screen.getAllByLabelText(/^descrição/i)).toHaveLength(2);
  });

  it("mostra a lista com uma data final única e sem campos técnicos", () => {
    renderizar();

    expect(screen.getByLabelText(/^atualizar cálculo até/i)).toBeTruthy();
    expect(screen.getByLabelText(/^correção monetária/i)).toBeTruthy();
    expect(screen.getAllByText(/Tabela Prática TJSP/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /\+ adicionar valor/i })).toBeTruthy();
    expect(screen.queryByLabelText(/^data\*?$/i)).toBeNull();
    expect(screen.queryByText(/data-base/i)).toBeNull();
    expect(screen.queryByText(/base_verba_id/i)).toBeNull();
    expect(screen.queryByText(/detalhes da verba/i)).toBeNull();
  });

  it("exige correção, valor, descrição e data final — nunca data de juros desligados", () => {
    renderizar();
    fireEvent.click(botao(/gerar cálculo/i));

    expect(screen.getByText(/informe a descrição/i)).toBeTruthy();
    expect(screen.getByText(/informe a data da correção/i)).toBeTruthy();
    expect(screen.queryByText(/informe a data de início dos juros/i)).toBeNull();
    expect(screen.getByText(/informe o valor/i)).toBeTruthy();
    expect(screen.getByText(/até quando o cálculo deve ser atualizado/i)).toBeTruthy();
    expect(screen.queryByText(/informe a data\./i)).toBeNull();
  });

  it("com juros marcados, a data dos juros volta a ser exigida", () => {
    renderizar();
    ativarJuros(0);
    fireEvent.click(botao(/gerar cálculo/i));

    expect(screen.getByText(/informe a data de início dos juros/i)).toBeTruthy();
  });

  it("explica a falta de índice da data final sem bloquear o cálculo", async () => {
    vi.mocked(api.coberturaIndexador).mockResolvedValue(coberturaTjsp);
    renderizar();
    digitar(/^atualizar cálculo até/i, "2026-10-05");

    await waitFor(() => {
      expect(screen.getByText(/falta o índice de outubro\/2026/i)).toBeTruthy();
    });
    expect(screen.getByText(/Data final sem índice publicado/i)).toBeTruthy();
    expect(screen.getByText(/publicada até setembro\/2026/i)).toBeTruthy();
    expect(screen.getByText(/não repete o índice do mês anterior/i)).toBeTruthy();
    expect((botao(/gerar cálculo/i) as HTMLButtonElement).disabled).toBe(false);
  });
});
const DATA_FINAL_VALIDA = "2026-09-30";

function verbaSimples(parcial: Partial<EstadoVerba> = {}): EstadoVerba {
  return novaVerba({ nome: "Verba", valor: "1000,00", ...parcial });
}

describe("errosVerbas — correção e juros são opcionais e independentes", () => {
  it("verba sem correção e sem juros → válida", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: false,
      jurosInicio: "",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("verba somente com correção → válida", () => {
    const verba = verbaSimples({
      correcaoAplicar: true,
      correcaoInicio: "2022-08-30",
      jurosAplicar: false,
      jurosInicio: "",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("verba somente com juros → válida", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: true,
      jurosInicio: "2026-04-24",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("verba com ambos → válida", () => {
    const verba = verbaSimples({
      correcaoAplicar: true,
      correcaoInicio: "2022-08-30",
      jurosAplicar: true,
      jurosInicio: "2026-04-24",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("juros ativados sem data → erro", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: true,
      jurosInicio: "",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toContain(
      "Lançamento 1: informe a data de início dos juros.",
    );
  });

  it("juros desativados sem data → sem erro", () => {
    const verba = verbaSimples({
      correcaoAplicar: true,
      correcaoInicio: "2022-08-30",
      jurosAplicar: false,
      jurosInicio: "",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("correção desativada sem data → sem erro", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: true,
      jurosInicio: "2026-04-24",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });
});

describe("payload Cível — Taxa Legal explícita nos juros", () => {
  it("juros ativos enviam modalidade taxa_legal e a própria data", () => {
    const verba = verbaSimples({
      correcaoAplicar: true,
      correcaoInicio: "2022-08-30",
      jurosAplicar: true,
      jurosInicio: "2026-04-24",
    });
    const payload = montarVerbaPayload(verba, DATA_FINAL_VALIDA);
    expect(payload.juros?.aplicar).toBe(true);
    expect(payload.juros?.modalidade).toBe("taxa_legal");
    expect(payload.juros?.inicio).toBe("2026-04-24");
  });

  it("verba sem nenhuma atualização continua calculável", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: false,
      jurosInicio: "",
    });
    const payload = montarVerbaPayload(verba, DATA_FINAL_VALIDA);
    expect(payload.correcao?.aplicar).toBe(false);
    expect(payload.juros?.aplicar).toBe(false);
    expect(payload.valor).toBe("1000,00");
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("data_base acompanha a data da atualização ativa (juros sem correção)", () => {
    const verba = verbaSimples({
      correcaoAplicar: false,
      correcaoInicio: "",
      jurosAplicar: true,
      jurosInicio: "2026-04-24",
    });
    const payload = montarVerbaPayload(verba, DATA_FINAL_VALIDA);
    expect(payload.data_base).toBe("2026-04-24");
    expect(payload.correcao?.aplicar).toBe(false);
  });
});

describe("regras de atualização (regimes)", () => {
  it("payload envia dois regimes consecutivos com critério combinado SELIC", () => {
    const regimes = [
      novaRegime({
        dataFim: "2024-08-27",
        correcao: "tjsp_tabela_pratica",
        juros: "fixa",
      }),
      novaRegime({
        dataInicio: "2024-08-28",
        correcao: "selic",
        juros: "selic",
      }),
    ];
    const payload = montarRegimesPayload(regimes);

    expect(payload).toHaveLength(2);
    expect(payload[0].data_inicio).toBeNull();
    expect(payload[0].data_fim).toBe("2024-08-27");
    expect(payload[0].correcao).toBe("tjsp_tabela_pratica");
    expect(payload[0].juros?.modalidade).toBe("fixa");
    expect(payload[0].juros?.taxa).toBe("0.01");
    expect(payload[0].criterio).toBeNull();

    expect(payload[1].data_inicio).toBe("2024-08-28");
    expect(payload[1].data_fim).toBeNull();
    expect(payload[1].correcao).toBe("selic");
    expect(payload[1].juros?.modalidade).toBe("selic");
    expect(payload[1].criterio).toBe("selic");
  });

  it("segundo regime exige data inicial", () => {
    const regimes = [novaRegime({ correcao: "selic", juros: "selic" })];
    expect(errosRegimes(regimes)).toEqual([]);

    regimes.push(novaRegime({ correcao: "selic", juros: "selic" }));
    expect(errosRegimes(regimes)).toEqual([
      "Regra de atualização 2: informe a data inicial.",
    ]);
  });

  it("regime sem correção e sem juros é inválido", () => {
    expect(errosRegimes([novaRegime({ dataFim: "2024-08-27" })])).toEqual([
      "Regra de atualização 1: informe a correção ou os juros do período.",
    ]);
  });

  it("data final anterior à inicial é inválida", () => {
    expect(
      errosRegimes([
        novaRegime({
          dataInicio: "2024-08-28",
          dataFim: "2024-08-27",
          correcao: "selic",
        }),
      ]),
    ).toEqual(["Regra de atualização 1: a data final é anterior à data inicial."]);
  });

  it("verba sem regimes não exige nenhuma regra", () => {
    const verba = novaVerba({
      nome: "X",
      valor: "1000,00",
      correcaoAplicar: false,
      jurosAplicar: false,
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toEqual([]);
  });

  it("a ação da interface abre o editor de regras", () => {
    renderizar();
    expect(screen.queryByText(/Regras de atualização/i)).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: /\+ adicionar regra de atualização/i }),
    );

    expect(screen.getByText(/Regras de atualização/i)).toBeTruthy();
    expect(screen.getByLabelText(/^correção do período$/i)).toBeTruthy();
    expect(screen.getByLabelText(/^juros do período$/i)).toBeTruthy();
    expect(screen.getByText(/1 período com critério próprio/i)).toBeTruthy();
  });

  it("envia os dois regimes preenchidos na interface", async () => {
    renderizar();
    digitar(/^nome \/ descrição/i, "Caso com regimes");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    await preencherLinha(0, {
      correcao: "2022-06-15",
      juros: "2022-09-10",
      valor: "30018,44",
      descricao: "Condenação",
    });

    fireEvent.click(
      screen.getByRole("button", { name: /\+ adicionar regra de atualização/i }),
    );
    fireEvent.change(screen.getByLabelText(/^até$/i), {
      target: { value: "2024-08-27" },
    });
    fireEvent.change(screen.getByLabelText(/^correção do período$/i), {
      target: { value: "tjsp_tabela_pratica" },
    });
    fireEvent.change(screen.getByLabelText(/^juros do período$/i), {
      target: { value: "fixa" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: /\+ adicionar regra de atualização/i }),
    );
    fireEvent.change(screen.getAllByLabelText(/^de$/i)[1], {
      target: { value: "2024-08-28" },
    });
    fireEvent.change(screen.getAllByLabelText(/^correção do período$/i)[1], {
      target: { value: "selic" },
    });
    fireEvent.change(screen.getAllByLabelText(/^juros do período$/i)[1], {
      target: { value: "selic" },
    });

    fireEvent.click(botao(/gerar cálculo/i));
    await waitFor(() => {
      expect(screen.getByText(/resultado vec-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    const regimes = payload.verbas[0].regimes ?? [];
    expect(regimes).toHaveLength(2);
    expect(regimes[0].data_inicio).toBeNull();
    expect(regimes[0].data_fim).toBe("2024-08-27");
    expect(regimes[0].correcao).toBe("tjsp_tabela_pratica");
    expect(regimes[0].juros?.modalidade).toBe("fixa");
    expect(regimes[1].data_inicio).toBe("2024-08-28");
    expect(regimes[1].data_fim).toBeNull();
    expect(regimes[1].criterio).toBe("selic");
    expect(regimes[1].juros?.modalidade).toBe("selic");
  });
});

describe("juros opcionais — nova verba começa desligada", () => {
  it("1. nova verba começa com juros desmarcado e correção marcada", () => {
    const verba = novaVerba();
    expect(verba.jurosAplicar).toBe(false);
    expect(verba.correcaoAplicar).toBe(true);

    renderizar();

    expect(
      (
        screen.getByRole("checkbox", {
          name: /aplicar juros no lançamento 1/i,
        }) as HTMLInputElement
      ).checked,
    ).toBe(false);
    expect(
      (
        screen.getByRole("checkbox", {
          name: /aplicar correção monetária no lançamento 1/i,
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(screen.queryByLabelText(/^juros desde/i)).toBeNull();
    expect(screen.getByText(/juros desativados/i)).toBeTruthy();
  });

  it("2. sem juros não exige data de juros", () => {
    const verba = novaVerba({
      nome: "Condenação",
      valor: "30018,44",
      correcaoInicio: "2025-02-12",
      jurosAplicar: false,
      jurosInicio: "",
    });
    expect(errosVerbas([verba], "2026-09-30")).toEqual([]);

    renderizar();
    digitar(/^nome \/ descrição/i, "Caso sem juros");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    digitar(/^correção desde/i, "2025-02-12");
    digitar(/^valor/i, "30018,44");
    digitar(/^descrição/i, "Condenação");

    fireEvent.click(botao(/gerar cálculo/i));

    expect(screen.queryByText(/informe a data de início dos juros/i)).toBeNull();
    expect(screen.queryByText(/Corrija antes de gerar/i)).toBeNull();
  });

  it("3. gera o cálculo sem juros e envia juros como não aplicados", async () => {
    renderizar();
    digitar(/^nome \/ descrição/i, "Condenação sem juros");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    digitar(/^correção desde/i, "2025-02-12");
    digitar(/^valor/i, "30018,44");
    digitar(/^descrição/i, "Condenação");

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas).toHaveLength(1);
    const [verba] = payload.verbas;
    expect(verba.valor).toBe("30018,44");
    expect(verba.correcao?.aplicar).toBe(true);
    expect(verba.correcao?.termo_inicial).toBe("2025-02-12");
    expect(verba.juros?.aplicar).toBe(false);
    expect(verba.juros?.inicio).toBeNull();
  });
});

describe("rascunhos", () => {
  it("6. salva rascunho incompleto sem data de juros e sem validação", () => {
    renderizar();
    digitar(/^nome \/ descrição/i, "Rascunho parcial");
    digitar(/^valor/i, "30018,44");
    digitar(/^descrição/i, "Condenação");

    fireEvent.click(botao(/salvar rascunho/i));

    expect(screen.queryByText(/Corrija antes de gerar/i)).toBeNull();
    expect(screen.queryByText(/informe a data de início dos juros/i)).toBeNull();
    expect(screen.getAllByText(/Rascunho parcial.*salvo/i).length).toBeGreaterThan(0);
    expect(api.criarCalculo).not.toHaveBeenCalled();

    const rascunhos = listarRascunhos();
    expect(rascunhos).toHaveLength(1);
    expect(rascunhos[0].titulo).toBe("Rascunho parcial");
    expect(rascunhos[0].estado.identificacao.titulo).toBe("Rascunho parcial");
    expect(rascunhos[0].estado.dataBaseCalculo).toBe("");
    expect(rascunhos[0].estado.verbas).toHaveLength(1);
    expect(rascunhos[0].estado.verbas[0].valor).toBe("30018,44");
    expect(rascunhos[0].estado.verbas[0].jurosAplicar).toBe(false);
    expect(rascunhos[0].estado.verbas[0].correcaoInicio).toBe("");
  });

  it("7. reabrir rascunho preserva os dados exatamente como estavam", () => {
    const salvo = salvarRascunho({
      identificacao: {
        titulo: "Rascunho aberto",
        processo: "0001234-56.2021.8.26.0100",
        parte: "Autor",
      },
      dataBaseCalculo: "2026-09-30",
      indexador: "tjsp_tabela_pratica",
      verbas: [
        novaVerba({
          nome: "Condenação",
          valor: "30018,44",
          correcaoInicio: "2025-02-12",
          jurosAplicar: false,
          jurosInicio: "",
        }),
      ],
    });

    renderizar(
      `/novo-calculo?tipo=parcelas&modo=detalhado&rascunho=${encodeURIComponent(salvo.id)}`,
    );

    expect((screen.getByLabelText(/^nome \/ descrição/i) as HTMLInputElement).value).toBe(
      "Rascunho aberto",
    );
    expect((screen.getByLabelText(/^processo/i) as HTMLInputElement).value).toBe(
      "0001234-56.2021.8.26.0100",
    );
    expect((screen.getByLabelText(/^atualizar cálculo até/i) as HTMLInputElement).value).toBe(
      "2026-09-30",
    );
    expect((screen.getByLabelText(/^correção desde/i) as HTMLInputElement).value).toBe(
      "2025-02-12",
    );
    expect((screen.getByLabelText(/^valor/i) as HTMLInputElement).value).toBe("30018,44");
    expect((screen.getByLabelText(/^descrição/i) as HTMLInputElement).value).toBe(
      "Condenação",
    );
    expect(
      (
        screen.getByRole("checkbox", {
          name: /aplicar juros no lançamento 1/i,
        }) as HTMLInputElement
      ).checked,
    ).toBe(false);
    expect(screen.queryByLabelText(/^juros desde/i)).toBeNull();
    expect(screen.getByText(/rascunho reaberto com os dados como estavam/i)).toBeTruthy();
  });
});

describe("composição no total (entra_no_total)", () => {
  it("nova verba começa em Padrão e envia null — o backend decide", () => {
    const verba = novaVerba({
      id: "causa",
      nome: "Valor da causa",
      valor: "44000,00",
      correcaoInicio: "2022-08-30",
    });
    expect(verba.entraNoTotal).toBeNull();
    expect(montarVerbaPayload(verba, "2026-09-30").entra_no_total).toBeNull();
  });

  it("marcação explícita vira booleano no payload", () => {
    const base = {
      id: "causa",
      nome: "Valor da causa",
      valor: "44000,00",
      correcaoInicio: "2022-08-30",
    };
    expect(
      montarVerbaPayload(novaVerba({ ...base, entraNoTotal: true }), "2026-09-30")
        .entra_no_total,
    ).toBe(true);
    expect(
      montarVerbaPayload(novaVerba({ ...base, entraNoTotal: false }), "2026-09-30")
        .entra_no_total,
    ).toBe(false);
  });

  it("rascunho antigo sem o campo continua enviando null (compatibilidade)", () => {
    const antiga = novaVerba({
      id: "causa",
      nome: "Valor da causa",
      valor: "44000,00",
      correcaoInicio: "2022-08-30",
    });
    delete antiga.entraNoTotal;
    expect(montarVerbaPayload(antiga, "2026-09-30").entra_no_total).toBeNull();
  });

  it("a interface oferece Padrão / Sim / Não e envia a escolha no payload", async () => {
    await preencherCasoDerivado();

    const selects = screen.getAllByLabelText(
      /compõe o total da execução/i,
    ) as HTMLSelectElement[];
    expect(selects).toHaveLength(2);
    expect(selects[0].value).toBe("");
    expect(Array.from(selects[0].options).map((o) => o.textContent)).toEqual([
      "Padrão",
      "Sim — soma no total",
      "Não — fica fora do total",
    ]);

    fireEvent.change(selects[0], { target: { value: "false" } });

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas[0].entra_no_total).toBe(false);
    expect(payload.verbas[1].entra_no_total).toBeNull();
  });
});

const URL_SIMPLES = "/novo-calculo?tipo=parcelas";

describe("estadoVerba — encargos de multa e honorários", () => {
  it("montarVerbaPayload converte percentual de multa em fração do backend", () => {
    const verba = novaVerba({
      nome: "Principal",
      valor: "1000,00",
      correcaoInicio: "2022-01-01",
      multaAplicar: true,
      multaPercentual: "10",
      multaBase: "corrigido",
    });
    const payload = montarVerbaPayload(verba, "2026-09-30");
    expect(payload.multa?.aplicar).toBe(true);
    expect(payload.multa?.percentual).toBe("0.1");
    expect(payload.multa?.valor_fixo).toBeNull();
    expect(payload.multa?.base).toBe("corrigido");
  });

  it("valor fixo tem precedência e o percentual vai nulo (o motor rejeita ambos)", () => {
    const verba = novaVerba({
      nome: "Principal",
      valor: "1000,00",
      correcaoInicio: "2022-01-01",
      honorariosAplicar: true,
      honorariosPercentual: "10",
      honorariosValorFixo: "500,00",
      honorariosBase: "principal",
    });
    const payload = montarVerbaPayload(verba, "2026-09-30");
    expect(payload.honorarios?.valor_fixo).toBe("500,00");
    expect(payload.honorarios?.percentual).toBeNull();
  });

  it("descrição digitada no campoDescrição vai ao payload como descricao", () => {
    const verba = novaVerba({
      nome: "Valor da causa",
      valor: "100,00",
      correcaoInicio: "2022-01-01",
    });
    expect(montarVerbaPayload(verba, "2026-09-30").descricao).toBe(
      "Valor da causa",
    );
  });

  it("errosVerbas exige percentual OU valor fixo quando o encargo está aplicado", () => {
    const verba = novaVerba({
      nome: "Principal",
      valor: "100,00",
      correcaoInicio: "2022-01-01",
      multaAplicar: true,
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toContain(
      "Lançamento 1: informe o percentual da multa (ex.: 10) ou o valor fixo.",
    );

    const hon = novaVerba({
      nome: "Principal",
      valor: "100,00",
      correcaoInicio: "2022-01-01",
      honorariosAplicar: true,
    });
    expect(errosVerbas([hon], DATA_FINAL_VALIDA)).toContain(
      "Lançamento 1: informe o percentual dos honorários (ex.: 10) ou o valor fixo.",
    );
  });

  it("errosVerbas recusa percentual e valor fixo preenchidos juntos", () => {
    const verba = novaVerba({
      nome: "Principal",
      valor: "100,00",
      correcaoInicio: "2022-01-01",
      multaAplicar: true,
      multaPercentual: "10",
      multaValorFixo: "500,00",
    });
    expect(errosVerbas([verba], DATA_FINAL_VALIDA)).toContain(
      "Lançamento 1: informe o percentual ou o valor fixo da multa, não ambos.",
    );
  });

  it("aplicarEncargoGeral: percentual replica em todas as verbas", () => {
    const verbas = [
      novaVerba({ id: "a", nome: "A", valor: "100,00" }),
      novaVerba({ id: "b", nome: "B", valor: "200,00" }),
    ];
    const resultado = aplicarEncargoGeral(verbas, "multa", {
      aplicar: true,
      percentual: "10",
      valorFixo: "",
      base: "corrigido",
    });
    expect(
      resultado.every((v) => v.multaAplicar && v.multaPercentual === "10"),
    ).toBe(true);
  });

  it("aplicarEncargoGeral: valor fixo entra só na primeira verba somável", () => {
    const base = novaVerba({ id: "a", nome: "A", valor: "100,00" });
    const derivada = novaVerba({
      id: "b",
      tipo: "percentual",
      nome: "B",
      percentual: "10",
      baseVerbaId: "a",
    });
    const resultado = aplicarEncargoGeral([base, derivada], "honorarios", {
      aplicar: true,
      percentual: "",
      valorFixo: "500,00",
      base: "corrigido",
    });
    // "a" é base de "b" → fora do total; o fixo vai para "b", que soma
    expect(resultado[0].honorariosAplicar).toBe(false);
    expect(resultado[1].honorariosAplicar).toBe(true);
    expect(resultado[1].honorariosValorFixo).toBe("500,00");
    expect(resultado[1].honorariosPercentual).toBe("");
  });

  it("anexarPagamentosGlobais anexa uma única vez na verba somável", () => {
    const base = novaVerba({ id: "a", nome: "A", valor: "100,00" });
    const derivada = novaVerba({
      id: "b",
      tipo: "percentual",
      nome: "B",
      percentual: "10",
      baseVerbaId: "a",
    });
    const pagamentos = [novaPagamento({ data: "2026-01-01", valor: "50,00" })];
    const resultado = anexarPagamentosGlobais([base, derivada], pagamentos);
    expect(resultado[0].pagamentos).toHaveLength(0);
    expect(resultado[1].pagamentos).toHaveLength(1);
  });

  it("errosPagamentos valida data, valor ausente e valor não positivo", () => {
    expect(errosPagamentos([novaPagamento()])).toEqual([
      "Pagamento 1: informe a data.",
      "Pagamento 1: informe o valor.",
    ]);
    expect(
      errosPagamentos([novaPagamento({ data: "2026-01-01", valor: "-5" })]),
    ).toEqual(["Pagamento 1: valor inválido (ex.: 500,00)."]);
    expect(
      errosPagamentos([novaPagamento({ data: "2026-01-01", valor: "50,00" })]),
    ).toEqual([]);
  });
});

describe("FormCivel — modo simples (padrão)", () => {
  it("pede confirmação antes de calcular com juros desativados e respeita a escolha", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Custas sem juros");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({ descricao: "Custas processuais", data: "2025-01-10", valor: "100,00" });

    fireEvent.click(botao(/gerar cálculo/i));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.getByText(/custas processuais: juros desativados/i)).toBeTruthy();
    expect(api.criarCalculo).not.toHaveBeenCalled();

    fireEvent.click(botao(/voltar e revisar/i));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByDisplayValue("100,00")).toBeTruthy();

    fireEvent.click(botao(/gerar cálculo/i));
    fireEvent.click(botao(/manter configurações e calcular/i));
    await waitFor(() => expect(api.criarCalculo).toHaveBeenCalledTimes(1));
    const payload = vi.mocked(api.criarCalculo).mock.calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas[0].juros?.aplicar).toBe(false);
  });

  it("confirma também correção desativada e não avisa quando todos os critérios estão ativos", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Critérios ativos");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({ descricao: "Principal", data: "2025-01-10", valor: "100,00" });

    fireEvent.click(screen.getByRole("switch", { name: /^correção monetária$/i }));
    fireEvent.click(botao(/gerar cálculo/i));
    expect(screen.getByText(/principal: correção monetária desativada/i)).toBeTruthy();
    fireEvent.click(botao(/voltar e revisar/i));

    fireEvent.click(screen.getByRole("switch", { name: /^correção monetária$/i }));
    fireEvent.click(screen.getByRole("switch", { name: /^juros$/i }));
    fireEvent.click(botao(/gerar cálculo/i));
    await waitFor(() => expect(api.criarCalculo).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("reabre cálculo salvo como revisão, preservando pagamento e encargo consolidado", async () => {
    vi.mocked(api.obterCalculo).mockResolvedValue({
      codigo: "VEC-2026-000001",
      payload: {
        tipo: "parcelas", titulo: "Cálculo recuperado", processo: "123", parte: "Autora",
        data_base: "2026-09-30", pagamentos: [], correcao: { aplicar: false },
        juros: { aplicar: false }, multa: { aplicar: false }, honorarios: { aplicar: false },
        verbas: [{
          id: "v1", nome: "parcelas fls. 3", descricao: "parcelas fls. 3", valor: "14689.70",
          data_base: "2022-02-06", entra_no_total: true,
          correcao: { aplicar: true, indexador: "tjsp_tabela_pratica", termo_inicial: "2022-02-06" },
          juros: { aplicar: false, modalidade: "taxa_legal", base: "corrigido" },
          multa: { aplicar: false }, honorarios: { aplicar: false },
          pagamentos: [{ data: "2025-07-29", valor: "1881.86", descricao: "penhoras online" }],
          parcelas: [], regimes: [],
        }],
        encargos_consolidados: [{ id: "ec1", tipo: "multa", ordem: 1, componentes: ["principal_corrigido"], percentual: "0.10", entra_no_total: true }],
      },
    } as unknown as CalculoCriado);
    renderizar("/novo-calculo?tipo=parcelas&revisar=VEC-2026-000001");

    await waitFor(() => expect(screen.getByDisplayValue("Cálculo recuperado")).toBeTruthy());
    expect(screen.getByDisplayValue("2025-07-29")).toBeTruthy();
    expect(screen.getByDisplayValue("penhoras online")).toBeTruthy();
    expect(screen.getByRole("switch", { name: /encargo único sobre o total/i })
      .getAttribute("aria-checked")).toBe("true");

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => expect(api.criarCalculo).toHaveBeenCalled());
    const payload = vi.mocked(api.criarCalculo).mock.calls[0][0] as CalculoCivelPayload;
    expect(payload.revisao_de).toBe("VEC-2026-000001");
    expect(payload.verbas[0].juros?.aplicar).toBe(false);
    expect(payload.verbas[0].pagamentos).toHaveLength(1);
    expect(payload.encargos_consolidados).toHaveLength(1);
  });

  function preencherLinhaSimples(dados: {
    descricao: string;
    data: string;
    valor: string;
    indice?: number;
  }) {
    const i = dados.indice ?? 0;
    digitar(/^descrição$/i, dados.descricao, i);
    digitar(new RegExp(`^data do lançamento ${i + 1}$`, "i"), dados.data);
    digitar(/^valor$/i, dados.valor, i);
  }

  it("abre com a tabela Descrição/Data/Valor/Ações, sem campos técnicos do detalhado", () => {
    renderizar(URL_SIMPLES);

    expect(screen.getAllByText(/^descrição$/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^data$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/^ações$/i)).toBeTruthy();
    expect(screen.getByLabelText(/atualizar cálculo até/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /\+ adicionar valor/i })).toBeTruthy();

    expect(screen.queryByLabelText(/^correção desde/i)).toBeNull();
    expect(screen.queryByLabelText(/^juros desde/i)).toBeNull();
    expect(screen.queryByLabelText(/usar percentual de outra verba/i)).toBeNull();
    expect(screen.queryByLabelText(/compõe o total da execução/i)).toBeNull();
    expect(screen.queryByLabelText(/adicionar regra de atualização/i)).toBeNull();

    expect(screen.getByRole("switch", { name: /correção monetária/i })).toBeTruthy();
    expect(screen.getByRole("switch", { name: /^juros$/i })).toBeTruthy();
    expect(screen.getByRole("switch", { name: /^multa$/i })).toBeTruthy();
    expect(screen.getByRole("switch", { name: /^honorários$/i })).toBeTruthy();
    expect(screen.getByText(/pagamentos e abatimentos/i)).toBeTruthy();
  });

  it("preenche a linha, liga multa percentual e honorários fixos e envia o payload", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Caso com encargos");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({
      descricao: "Valor da causa",
      data: "2022-08-30",
      valor: "44000,00",
    });

    fireEvent.click(screen.getByRole("switch", { name: /^multa$/i }));
    digitar(/^multa \(%\)$/i, "10");

    fireEvent.click(screen.getByRole("switch", { name: /^honorários$/i }));
    digitar(/^honorários \(valor fixo\)$/i, "500,00");

    fireEvent.click(botao(/\+ adicionar pagamento/i));
    digitar(/^data\*?$/i, "2026-01-15", 1);
    digitar(/^valor\*?$/i, "1000,00", 1);

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas).toHaveLength(1);
    const [verba] = payload.verbas;
    expect(verba.descricao).toBe("Valor da causa");
    expect(verba.nome).toBe("Valor da causa");
    expect(verba.correcao?.aplicar).toBe(true);
    expect(verba.correcao?.termo_inicial).toBe("2022-08-30");
    expect(verba.juros?.aplicar).toBe(false);
    expect(verba.multa?.aplicar).toBe(true);
    expect(verba.multa?.percentual).toBe("0.1");
    expect(verba.multa?.valor_fixo).toBeNull();
    expect(verba.honorarios?.aplicar).toBe(true);
    expect(verba.honorarios?.valor_fixo).toBe("500,00");
    expect(verba.honorarios?.percentual).toBeNull();
    expect(verba.pagamentos).toHaveLength(1);
    expect(verba.pagamentos?.[0]).toMatchObject({
      data: "2026-01-15",
      valor: "1000,00",
    });
  });

  it("desligar a correção global desliga em todas as verbas", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Sem correção");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({
      descricao: "Principal",
      data: "2022-08-30",
      valor: "1000,00",
    });

    fireEvent.click(screen.getByRole("switch", { name: /correção monetária/i }));
    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas[0].correcao?.aplicar).toBe(false);
    expect(payload.verbas[0].juros?.aplicar).toBe(false);
  });

  it("ligar juros aplica a todas as verbas, com taxa_legal e a base escolhida", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Duas linhas");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({
      descricao: "Principal",
      data: "2022-08-30",
      valor: "1000,00",
    });

    fireEvent.click(botao(/\+ adicionar valor/i));
    preencherLinhaSimples({
      descricao: "Multa contratual",
      data: "2023-01-01",
      valor: "500,00",
      indice: 1,
    });

    fireEvent.click(screen.getByRole("switch", { name: /^juros$/i }));
    fireEvent.change(screen.getByLabelText(/juros sobre/i), {
      target: { value: "principal" },
    });

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas).toHaveLength(2);
    for (const verba of payload.verbas) {
      expect(verba.juros?.aplicar).toBe(true);
      expect(verba.juros?.modalidade).toBe("taxa_legal");
      expect(verba.juros?.base).toBe("principal");
      expect(verba.juros?.inicio).toBeTruthy();
    }
    expect(payload.verbas[0].juros?.inicio).toBe("2022-08-30");
    expect(payload.verbas[1].juros?.inicio).toBe("2023-01-01");
  });

  it("nova verba herda juros quando o controle simples já estava ligado", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Juros em todas as linhas");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({ descricao: "Principal", data: "2022-08-30", valor: "1000,00" });

    fireEvent.click(screen.getByRole("switch", { name: /^juros$/i }));
    fireEvent.click(botao(/\+ adicionar valor/i));
    preencherLinhaSimples({
      descricao: "Segunda verba", data: "2023-01-01", valor: "500,00", indice: 1,
    });
    fireEvent.click(botao(/gerar cálculo/i));

    await waitFor(() => expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy());
    const payload = vi.mocked(api.criarCalculo).mock.calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas[1].juros?.aplicar).toBe(true);
    expect(payload.verbas[1].juros?.inicio).toBe("2023-01-01");
  });

  it("multa em valor fixo entra uma única vez, no primeiro valor do total", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Duas linhas");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({
      descricao: "Principal",
      data: "2022-08-30",
      valor: "1000,00",
    });

    fireEvent.click(botao(/\+ adicionar valor/i));
    preencherLinhaSimples({
      descricao: "Juros de mora",
      data: "2023-01-01",
      valor: "500,00",
      indice: 1,
    });

    fireEvent.click(screen.getByRole("switch", { name: /^multa$/i }));
    digitar(/^multa \(valor fixo\)$/i, "500,00");

    expect(screen.getByText(/valor fixo lançado uma única vez/i)).toBeTruthy();

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    expect(payload.verbas[0].multa?.aplicar).toBe(true);
    expect(payload.verbas[0].multa?.valor_fixo).toBe("500,00");
    expect(payload.verbas[0].multa?.percentual).toBeNull();
    expect(payload.verbas[1].multa?.aplicar).toBe(false);
  });

  it("multa ligada sem percentual nem fixo exige preenchimento", () => {
    renderizar(URL_SIMPLES);
    fireEvent.click(screen.getByRole("switch", { name: /^multa$/i }));
    fireEvent.click(botao(/gerar cálculo/i));

    expect(
      screen.getByText(/informe o percentual da multa/i),
    ).toBeTruthy();
  });

  it("pagamento é anexado uma única vez mesmo com duas verbas", async () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Duas linhas com pagamento");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    preencherLinhaSimples({
      descricao: "Principal",
      data: "2022-08-30",
      valor: "1000,00",
    });

    fireEvent.click(botao(/\+ adicionar valor/i));
    preencherLinhaSimples({
      descricao: "Acréscimos",
      data: "2023-01-01",
      valor: "200,00",
      indice: 1,
    });

    fireEvent.click(botao(/\+ adicionar pagamento/i));
    digitar(/^data\*?$/i, "2025-06-01", 2);
    digitar(/^valor\*?$/i, "300,00", 2);

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    const totalPagamentos = payload.verbas.reduce(
      (acc, v) => acc + (v.pagamentos?.length ?? 0),
      0,
    );
    expect(totalPagamentos).toBe(1);
    expect(payload.verbas[0].pagamentos).toHaveLength(1);
    expect(payload.verbas[1].pagamentos).toHaveLength(0);
  });

  it("linha abre em edição, salva com Concluir e mostra os dados formatados", () => {
    renderizar(URL_SIMPLES);
    preencherLinhaSimples({
      descricao: "Valor da causa",
      data: "2022-08-30",
      valor: "44000,00",
    });

    fireEvent.click(botao(/concluir edição do lançamento 1/i));

    expect(screen.getByText("Valor da causa")).toBeTruthy();
    expect(screen.getByText("30/08/2022")).toBeTruthy();
    expect(screen.getByText("R$ 44.000,00")).toBeTruthy();

    fireEvent.click(botao(/editar lançamento 1/i));
    expect(
      (screen.getByLabelText(/^descrição$/i) as HTMLInputElement).value,
    ).toBe("Valor da causa");
    expect(
      (screen.getByLabelText(/^data do lançamento 1$/i) as HTMLInputElement)
        .value,
    ).toBe("2022-08-30");
  });

  it("remover pede confirmação e só apaga no segundo clique", () => {
    renderizar(URL_SIMPLES);
    preencherLinhaSimples({
      descricao: "Linha descartável",
      data: "2022-08-30",
      valor: "100,00",
    });

    fireEvent.click(botao(/remover lançamento 1/i));
    expect(
      screen.getByRole("button", { name: /confirmar remoção do lançamento 1/i }),
    ).toBeTruthy();
    expect(
      (screen.getByLabelText(/^descrição$/i) as HTMLInputElement).value,
    ).toBe("Linha descartável");

    fireEvent.click(botao(/confirmar remoção do lançamento 1/i));
    expect(screen.getByText(/nenhum valor lançado/i)).toBeTruthy();
    expect(screen.queryByLabelText(/^descrição$/i)).toBeNull();
  });

  it("verba derivada vira configuração avançada e edita no modo detalhado", async () => {
    await preencherCasoDerivado();

    fireEvent.click(botao(/^simples$/i));

    expect(screen.getAllByText(/configuração avançada/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/12% de Valor da causa/)).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", { name: /editar no modo detalhado o lançamento 2/i }),
    );

    expect(screen.queryByText(/configuração avançada/i)).toBeNull();
    expect(screen.getByLabelText(/^percentual$/i)).toBeTruthy();
    expect(
      screen.getAllByLabelText(/compõe o total da execução/i),
    ).toHaveLength(2);
  });

  it("trocar para o modo detalhado preserva os lançamentos e volta ao simples", () => {
    renderizar(URL_SIMPLES);
    preencherLinhaSimples({
      descricao: "Valor da causa",
      data: "2022-08-30",
      valor: "44000,00",
    });

    fireEvent.click(botao(/^detalhado$/i));
    expect(
      (screen.getByLabelText(/^descrição$/i) as HTMLInputElement).value,
    ).toBe("Valor da causa");
    expect(
      (screen.getByLabelText(/^correção desde/i) as HTMLInputElement).value,
    ).toBe("2022-08-30");

    fireEvent.click(botao(/^simples$/i));
    fireEvent.click(botao(/concluir edição do lançamento 1/i));
    expect(screen.getByText("R$ 44.000,00")).toBeTruthy();
  });

  it("rascunho do modo simples guarda pagamentos e modo", () => {
    renderizar(URL_SIMPLES);
    digitar(/^nome \/ descrição/i, "Rascunho com pagamento");
    preencherLinhaSimples({
      descricao: "Principal",
      data: "2022-08-30",
      valor: "1000,00",
    });
    fireEvent.click(botao(/\+ adicionar pagamento/i));
    digitar(/^data\*?$/i, "2025-06-01", 1);
    digitar(/^valor\*?$/i, "100,00", 1);

    fireEvent.click(botao(/salvar rascunho/i));

    const rascunhos = listarRascunhos();
    expect(rascunhos).toHaveLength(1);
    expect(rascunhos[0].estado.modo).toBe("simples");
    expect(rascunhos[0].estado.pagamentos).toHaveLength(1);
    expect(rascunhos[0].estado.pagamentos?.[0]).toMatchObject({
      data: "2025-06-01",
      valor: "100,00",
    });
  });
});

describe("FormCivel — modo detalhado com multa e honorários por lançamento", () => {
  it("grava multa percentual e honorários fixos na própria verba e envia o payload", async () => {
    renderizar();
    digitar(/^nome \/ descrição/i, "Detalhado com encargos");
    digitar(/^atualizar cálculo até/i, "2026-09-30");
    await preencherLinha(0, {
      correcao: "2022-08-30",
      valor: "44000,00",
      descricao: "Valor da causa",
    });

    fireEvent.click(
      screen.getByRole("checkbox", { name: /aplicar multa no lançamento 1/i }),
    );
    digitar(/^multa \(%\)$/i, "2");

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /aplicar honorários no lançamento 1/i,
      }),
    );
    digitar(/^honorários \(valor fixo\)$/i, "800,00");

    fireEvent.click(botao(/gerar cálculo/i));
    confirmarCriteriosSeNecessario();
    await waitFor(() => {
      expect(screen.getByText(/resultado VEC-2026-000010/i)).toBeTruthy();
    });

    const payload = vi.mocked(api.criarCalculo).mock
      .calls[0][0] as CalculoCivelPayload;
    const [verba] = payload.verbas;
    expect(verba.multa?.aplicar).toBe(true);
    expect(verba.multa?.percentual).toBe("0.02");
    expect(verba.multa?.valor_fixo).toBeNull();
    expect(verba.honorarios?.aplicar).toBe(true);
    expect(verba.honorarios?.valor_fixo).toBe("800,00");
    expect(verba.honorarios?.percentual).toBeNull();
  });
});
