import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: () => {} } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { dominioDoTempo, montarDadosDoGrafico } from "@/lib/graficoDoItem";
import { projecaoExibida } from "@/lib/projecaoDoItem";
import { PONTOS, projecao, responder } from "./apoioDaProjecao";

const CHAVE = "goblin-ledger:projecao-visivel";
const ULTIMO_DO_HISTORICO = Date.parse("2026-09-27T00:00:00Z");
const ULTIMO_PREVISTO = Date.parse("2026-10-04T00:00:00Z");
const controle = () => screen.getByRole("button", { name: "Projeção" });

beforeEach(() => {
  window.sessionStorage.clear();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
  responder();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU05-C3 – Ocultar ou exibir a projeção", () => {
  it("test_cu05_c3_fluxo_principal_oculta_a_projecao", async () => {
    const { unmount } = render(<ItemDetailsPage />);
    await screen.findByRole("region", { name: "Projeção" });

    fireEvent.click(controle()); // passo 1

    expect(controle()).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("region", { name: "Projeção" })).not.toBeInTheDocument(); // passo 2: a tabela some
    expect(screen.queryByText("Projeção (menor preço diário)")).not.toBeInTheDocument(); // e a linha do gráfico
    expect(screen.getByRole("heading", { name: "Histórico de Preços (Ouro)" })).toBeInTheDocument();
    // Passo 3: sem a projeção, o eixo do tempo (e a escala) considera só o histórico.
    expect(dominioDoTempo(montarDadosDoGrafico(PONTOS, null))).toEqual([Date.parse("2026-09-21T00:00:00Z"), ULTIMO_DO_HISTORICO]);
    // Passo 4: a escolha fica na sessão do navegador e vale para as próximas telas de itens.
    expect(window.sessionStorage.getItem(CHAVE)).toBe("false");
    unmount();
    render(<ItemDetailsPage />);
    await waitFor(() => expect(controle()).toHaveAttribute("aria-pressed", "false"));
    expect(screen.queryByRole("region", { name: "Projeção" })).not.toBeInTheDocument();
  });

  it("test_cu05_c3_fa1_exibe_novamente_a_projecao", async () => {
    window.sessionStorage.setItem(CHAVE, "false"); // a projeção foi ocultada antes, na mesma sessão
    render(<ItemDetailsPage />);
    await waitFor(() => expect(controle()).toHaveAttribute("aria-pressed", "false"));

    fireEvent.click(controle()); // 1.1

    expect(controle()).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("region", { name: "Projeção" })).toBeInTheDocument(); // 1.2: a linha e a tabela
    expect(screen.getByText("Projeção (menor preço diário)")).toBeInTheDocument();
    // 1.3: a escala volta a incluir os 7 dias da projeção.
    expect(dominioDoTempo(montarDadosDoGrafico(PONTOS, projecaoExibida(projecao())))?.[1]).toBe(ULTIMO_PREVISTO);
    expect(window.sessionStorage.getItem(CHAVE)).toBe("true"); // 1.4

    // Sem acesso ao sessionStorage (modo privado restrito), a tela não quebra: a projeção aparece e o controle funciona.
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("SecurityError"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("SecurityError"); });
    fireEvent.click(controle());
    expect(controle()).toHaveAttribute("aria-pressed", "false");
  });
});
