import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// O setup é explícito porque a auto-limpeza do Testing Library não é
// registrada neste ambiente Vitest. Sem ela, uma renderização deixava inputs
// e efeitos pendentes para o teste seguinte.
afterEach(() => cleanup());

const reserva: Record<string, string> = {};

const storageMemoria: Storage = {
  get length() {
    return Object.keys(reserva).length;
  },
  clear() {
    for (const chave of Object.keys(reserva)) delete reserva[chave];
  },
  getItem(chave: string) {
    return chave in reserva ? reserva[chave] : null;
  },
  key(indice: number) {
    return Object.keys(reserva)[indice] ?? null;
  },
  removeItem(chave: string) {
    delete reserva[chave];
  },
  setItem(chave: string, valor: string) {
    reserva[chave] = String(valor);
  },
};

const alvo = globalThis as { localStorage?: Storage };

if (!alvo.localStorage) {
  Object.defineProperty(globalThis, "localStorage", {
    value: storageMemoria,
    configurable: true,
    writable: true,
  });
}
