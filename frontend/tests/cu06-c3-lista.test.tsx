import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A página /favoritos (CU06-C3), com o backend substituído por respostas fixas. A ordem, os valores e os textos vêm dele.
const { roteador } = vi.hoisted(() => ({ roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import FavoritosPage from "@/app/favoritos/page";
import type { ItemFavorito } from "@/lib/favoritosApi";
import { entrar, responder, rota, sair } from "./apoioDosFavoritos";

const VAZIA = "Você ainda não tem itens favoritos. Use a busca para encontrar itens e favoritá-los";
const FE1 = "Não foi possível carregar os seus favoritos no momento. Tente novamente mais tarde";

function item(alteracoes: Partial<ItemFavorito>): ItemFavorito {
  return { item_id: 1, name: "Item", icon_url: null, market_value: 10_000, variacao_pct: null, alertas_ativos: 0, desatualizado: false,
    aviso: null, ...alteracoes };
}

const LISTA = [
  item({ item_id: 1002, name: "Algari Healing Potion", market_value: 1_245_000, variacao_pct: 1.8, alertas_ativos: 1 }),
  item({ item_id: 1003, name: "Bismuth", market_value: 132_000, variacao_pct: -2.4 }),
  item({ item_id: 1001, name: "Mycobloom", market_value: 179_500, variacao_pct: null }),
];

beforeEach(() => {
  entrar();
  roteador.push.mockClear();
  roteador.replace.mockClear();
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  sair();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const linhas = async () => (await screen.findAllByRole("row")).slice(1);

describe("CU06-C3 – Visualizar lista de favoritos", () => {
  it("test_cu06_c3_fluxo_principal_lista_favoritos", async () => {
    responder([rota("GET", "/favorites", { status: 200, corpo: { itens: LISTA, mensagem: null } })]);
    render(<FavoritosPage />);

    const [pocao, bismuto, mycobloom] = await linhas(); // passo 4: na ordem do backend (alfabética)
    expect(pocao).toHaveTextContent("Algari Healing Potion");
    expect(pocao).toHaveTextContent("124g 50s"); // Ouro, Prata e Cobre (RN01)
    expect(within(pocao).getByTestId("variacao")).toHaveTextContent("+1,8%");
    expect(within(pocao).getByTestId("variacao").className).toContain("positive"); // sobe: verde
    expect(within(pocao).getByTestId("alertas-ativos")).toHaveTextContent("1");
    expect(within(bismuto).getByTestId("variacao")).toHaveTextContent("-2,4%");
    expect(within(bismuto).getByTestId("variacao").className).toContain("negative"); // cai: vermelho
    expect(mycobloom).toHaveTextContent("—"); // sem o ponto do dia anterior
    expect(screen.getByText("3 itens")).toBeInTheDocument();

    fireEvent.click(within(bismuto).getByText("Bismuth")); // passo 5
    expect(roteador.push).toHaveBeenCalledWith("/item/1003");
  });

  it("test_cu06_c3_fa1_lista_vazia", async () => {
    responder([rota("GET", "/favorites", { status: 200, corpo: { itens: [], mensagem: VAZIA } })]);
    render(<FavoritosPage />);

    expect(await screen.findByRole("status")).toHaveTextContent(VAZIA); // 1.2
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("test_cu06_c3_fa2_dados_desatualizados_rn09", async () => {
    responder([rota("GET", "/favorites", { status: 200, corpo: { itens: [
      item({ item_id: 1004, name: "Orbinid", desatualizado: true, aviso: "Dados Desatualizados", variacao_pct: -0.9 }),
      item({ item_id: 1001, name: "Mycobloom" }),
    ], mensagem: null } })]);
    render(<FavoritosPage />);

    const [orbinid, mycobloom] = await linhas();
    expect(within(orbinid).getByText("Dados Desatualizados")).toBeInTheDocument(); // 2.2: o selo
    expect(orbinid).toHaveTextContent("1g"); // e o item exibido normalmente
    expect(within(mycobloom).queryByText("Dados Desatualizados")).not.toBeInTheDocument();
  });

  it("test_cu06_c3_fe1_falha_no_banco", async () => {
    responder([rota("GET", "/favorites", { status: 503, corpo: { detail: FE1 } })]);
    const { unmount } = render(<FavoritosPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(FE1); // 1.2
    unmount();

    responder([rota("GET", "/favorites", "rede")]); // backend fora do ar: a mesma mensagem
    render(<FavoritosPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(FE1));
  });
});
