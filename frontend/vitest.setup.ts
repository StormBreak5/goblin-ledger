import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// A tela mostra os horários no fuso de quem vê (GMT-3 no Brasil): os testes rodam sempre no de Brasília.
process.env.TZ = "America/Sao_Paulo";

// O Recharts observa o tamanho do contêiner; o jsdom não traz ResizeObserver.
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverFalso;

afterEach(cleanup);
