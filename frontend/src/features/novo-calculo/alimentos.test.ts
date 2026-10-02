import { describe, expect, it } from "vitest";
import {
  estadoInicialAlimentos,
  fracaoDePercentual,
  montarPayloadAlimentos,
  novaRegra,
  novoPagamento,
  validarAlimentos,
  type EstadoAlimentos,
} from "./alimentos";

function cenario(estado: Partial<EstadoAlimentos> = {}): EstadoAlimentos {
  const base = estadoInicialAlimentos();
  return {
    ...base,
    identificacao: { titulo: "Alimentos", processo: "", parte: "" },
    atualizarAte: "2026-09-30",
    ...estado,
  };
}

function cenarioDoUsuario(): EstadoAlimentos {
  return cenario({
    regras: [
      novaRegra({ tipo: "percentual", percentual: "85", inicio: "04/2023" }),
    ],
    pagamentos: ["01", "02", "03"].map((mes) =>
      novoPagamento({
        competencia: `${mes}/2026`,
        data: `2026-${mes}-10`,
        valor: "200,00",
      }),
    ),
  });
}

describe("percentual digitado em % vira fração para o backend", () => {
  it.each([
    ["85", "0.85"],
    ["30", "0.3"],
    ["85,5", "0.855"],
    ["12,5", "0.125"],
    ["0,5", "0.005"],
  ])("%s%% → %s", (entrada, esperado) => {
    expect(fracaoDePercentual(entrada)).toBe(esperado);
  });
});

describe("validarAlimentos", () => {
  it("aceita o lançamento completo do usuário", () => {
    expect(validarAlimentos(cenarioDoUsuario())).toEqual([]);
  });

  it("sinaliza período fora do formato MM/AAAA em vez de falhar em silêncio", () => {
    const estado = cenario({
      regras: [novaRegra({ tipo: "percentual", percentual: "85", inicio: "30/09/2026" })],
    });
    expect(validarAlimentos(estado)).toEqual([
      "Regra 1: início inválido — use MM/AAAA (ex.: 04/2023).",
    ]);
  });

  it("exige nome, data da atualização e uma regra", () => {
    const estado = {
      ...cenario(),
      identificacao: { titulo: "  ", processo: "", parte: "" },
      atualizarAte: "",
      regras: [],
    };
    expect(validarAlimentos(estado)).toEqual([
      "Informe o nome/descrição do cálculo.",
      "Informe a data da atualização (até quando atualizar).",
      "Inclua ao menos uma regra de alimentos.",
    ]);
  });

  it("pede o fim da regra quando existe outra regra depois dela", () => {
    const estado = cenario({
      regras: [
        novaRegra({ tipo: "percentual", percentual: "85", inicio: "04/2023" }),
        novaRegra({ tipo: "fixo", valor: "1000,00", inicio: "01/2026" }),
      ],
    });
    expect(validarAlimentos(estado)).toEqual([
      "Regra 1: informe o mês/ano final — existe uma regra depois dela.",
    ]);
  });

  it("valida só os pagamentos lançados (linha vazia não trava o envio)", () => {
    const estado = cenarioDoUsuario();
    estado.pagamentos.push(novoPagamento());
    expect(validarAlimentos(estado)).toEqual([]);
  });

  it("cobra competência, data e valor do pagamento parcialmente preenchido", () => {
    const estado = cenarioDoUsuario();
    estado.pagamentos[0] = novoPagamento({ competencia: "01/2026" });
    expect(validarAlimentos(estado)).toEqual([
      "Pagamento 1: informe a data do pagamento.",
      "Pagamento 1: informe o valor pago.",
    ]);
  });
});

describe("montarPayloadAlimentos", () => {
  it("monta o lançamento padrão de alimentos (correção e juros automáticos)", () => {
    const payload = montarPayloadAlimentos(cenarioDoUsuario());

    expect(payload.tipo).toBe("alimentos");
    expect(payload.data_base).toBe("2026-09-30");
    expect(payload.alimentos.ate).toBe("09/2026");
    expect(payload.alimentos.dia_vencimento).toBe(10);

    expect(payload.alimentos.regras).toEqual([
      {
        inicio: "04/2023",
        fim: null,
        tipo: "salario_minimo",
        percentual: "0.85",
        valor: null,
        descricao: "",
      },
    ]);

    expect(payload.correcao).toEqual({
      aplicar: true,
      indexador: "tjsp_tabela_pratica",
      termo_inicial: null,
      termo_final: null,
    });
    expect(payload.juros).toEqual({
      aplicar: true,
      modalidade: "fixa",
      taxa: "0.01",
      unidade: "mensal",
      base: "corrigido",
      inicio: null,
      fim: null,
    });
    expect(payload.multa).toEqual({ aplicar: false });
    expect(payload.honorarios).toEqual({ aplicar: false });
  });

  it("vincula cada pagamento à sua competência", () => {
    const payload = montarPayloadAlimentos(cenarioDoUsuario());
    expect(payload.pagamentos).toEqual([
      { competencia: "01/2026", data: "2026-01-10", valor: "200,00", descricao: "" },
      { competencia: "02/2026", data: "2026-02-10", valor: "200,00", descricao: "" },
      { competencia: "03/2026", data: "2026-03-10", valor: "200,00", descricao: "" },
    ]);
  });

  it("descreve regra de valor fixo sem converter salário mínimo", () => {
    const payload = montarPayloadAlimentos(
      cenario({
        regras: [
          novaRegra({ tipo: "percentual", percentual: "85", inicio: "04/2023", fim: "12/2025" }),
          novaRegra({ tipo: "fixo", valor: "1000,00", inicio: "01/2026" }),
        ],
      }),
    );

    expect(payload.alimentos.regras).toEqual([
      {
        inicio: "04/2023",
        fim: "12/2025",
        tipo: "salario_minimo",
        percentual: "0.85",
        valor: null,
        descricao: "",
      },
      {
        inicio: "01/2026",
        fim: null,
        tipo: "fixo",
        percentual: null,
        valor: "1000,00",
        descricao: "",
      },
    ]);
  });
});
