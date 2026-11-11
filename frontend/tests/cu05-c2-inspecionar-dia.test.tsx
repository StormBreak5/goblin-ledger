import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: () => {} } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import TooltipDoGrafico from "@/components/TooltipDaProjecao";
import { montarDadosDoGrafico, type LinhaDoGrafico } from "@/lib/graficoDoItem";
import { projecaoExibida } from "@/lib/projecaoDoItem";
import { PONTOS, projecao, responder } from "./apoioDaProjecao";

// O Recharts não desenha no jsdom (sem tamanho de tela): a dica é testada como no CU04-C3, com o ponto que o gráfico
// entrega a ela; o destaque conjunto, pela tabela da tela.
const LINHAS = montarDadosDoGrafico(PONTOS, projecaoExibida(projecao()));
const dia = (data: string) => LINHAS.find((linha) => linha.tipo === "projecao" && linha.dia === data) as LinhaDoGrafico;
const dica = (linha: LinhaDoGrafico) => render(<TooltipDoGrafico active payload={[{ payload: linha }]} serieTemVolume />);

beforeEach(() => {
  window.sessionStorage.clear();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU05-C2 – Inspecionar um dia da projeção", () => {
  it("test_cu05_c2_fluxo_principal_tooltip_do_dia_previsto", async () => {
    // Passo 4: data com "dia inteiro" (em UTC, como o ponto diário do histórico), preço previsto em Ouro/Prata/Cobre,
    // variação sobre o último preço diário e a indicação "Projeção".
    dica(dia("2026-10-01"));
    expect(screen.getByText("PROJEÇÃO")).toBeInTheDocument();
    expect(screen.getByTestId("dica-instante")).toHaveTextContent("01/10/2026 · dia inteiro");
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço previsto: 17g 85s");
    expect(screen.getByTestId("dica-variacao")).toHaveTextContent("Variação: +3,8% sobre 17g 20s");

    // Passos 1 a 3 pela tabela: a linha focada fica em destaque (e o mesmo dia é destacado no gráfico).
    responder();
    render(<ItemDetailsPage />);
    const secao = await screen.findByRole("region", { name: "Projeção" });
    const linha = within(secao).getAllByRole("row")[4]; // 01/10/2026
    fireEvent.mouseEnter(linha);
    expect(linha).toHaveAttribute("data-destacado", "true");
    expect(within(secao).getAllByRole("row").filter((l) => l.dataset.destacado === "true")).toHaveLength(1);
    fireEvent.mouseLeave(linha);
    expect(linha).not.toHaveAttribute("data-destacado");
  });

  it("test_cu05_c2_fa1_ponto_de_partida_usa_o_tooltip_do_historico", () => {
    // 1.1: o ponto de partida é o último preço diário observado (27/09); 1.2: a dica do histórico (CU04-C3).
    const partida = LINHAS.find((linha) => linha.tipo === "partida") as LinhaDoGrafico;
    expect(partida.timestamp).toBe("2026-09-27T00:00:00Z");
    dica(partida);

    expect(screen.queryByText("PROJEÇÃO")).not.toBeInTheDocument();
    expect(screen.getByTestId("dica-instante")).toHaveTextContent("27/09/2026 dia inteiro");
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 17g 20s");
    expect(screen.getByTestId("dica-volume")).toHaveTextContent("Volume: 46");
  });

  it("test_cu05_c2_fe1_falha_na_conversao_omite_o_tooltip", () => {
    // 1.1 e 1.2: valor atípico, sem quebrar a tela; 1.3: registrado no console, e outro dia pode ser inspecionado.
    const { container, unmount } = dica({ ...dia("2026-09-30"), price: Number.NaN });
    expect(container).toBeEmptyDOMElement();
    expect(console.error).toHaveBeenCalledWith(expect.stringContaining("CU05-C2-FE1"), expect.anything(), expect.anything());
    unmount();

    dica(dia("2026-09-29"));
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço previsto: 17g 55s");
  });
});
