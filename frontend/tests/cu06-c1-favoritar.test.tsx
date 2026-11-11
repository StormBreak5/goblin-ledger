import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A tela do item com o controle "Favoritar"/"Favoritado" (CU06-C1), no jsdom, com o backend substituído por respostas fixas.
const { params, roteador, busca } = vi.hoisted(() => ({
  params: { id: "1001" },
  roteador: { replace: vi.fn(), push: vi.fn() },
  busca: { valor: "" },
}));
vi.mock("next/navigation", () => ({
  useParams: () => params,
  useRouter: () => roteador,
  useSearchParams: () => new URLSearchParams(busca.valor),
}));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import LoginPage from "@/app/login/page";
import { entrar, responder, rota, sair } from "./apoioDosFavoritos";

const ADICIONADO = "Item adicionado aos favoritos";
const FE1 = "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde";
const controle = () => screen.findByRole("button", { name: /Favorit/ });

beforeEach(() => {
  roteador.push.mockClear();
  roteador.replace.mockClear();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  sair();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU06-C1 – Adicionar item aos favoritos", () => {
  it("test_cu06_c1_fluxo_principal_adiciona_favorito", async () => {
    entrar();
    const chamadas = responder([rota("POST", "/favorites/1001", { status: 200, corpo: { item_id: 1001, favorito: true, message: ADICIONADO } })],
      { favorito: false });
    render(<ItemDetailsPage />);

    expect(await controle()).toHaveTextContent("Favoritar");
    fireEvent.click(await controle()); // passo 1

    await waitFor(() => expect(screen.getByRole("button", { name: /Favoritado/ })).toHaveAttribute("aria-pressed", "true")); // passo 5
    expect(screen.getByText(ADICIONADO)).toBeInTheDocument();
    expect(chamadas.filter((c) => c.metodo === "POST").map((c) => c.caminho)).toEqual(["/favorites/1001"]);
  });

  it("test_cu06_c1_fa1_usuario_nao_autenticado", async () => {
    const chamadas = responder();
    render(<ItemDetailsPage />);

    fireEvent.click(await controle()); // sem sessão

    expect(roteador.push).toHaveBeenCalledWith("/login?aviso=favoritar"); // 1.2
    expect(chamadas.some((c) => c.metodo === "POST")).toBe(false);

    // A tela de login mostra a mensagem do cenário.
    busca.valor = "aviso=favoritar";
    render(<LoginPage />);
    expect(screen.getByRole("alert")).toHaveTextContent("Entre na sua conta para favoritar itens");
    busca.valor = "";
  });

  it("test_cu06_c1_fa2_item_ja_favoritado", async () => {
    entrar();
    // O item já é favorito (2.1): o controle aparece como "Favoritado". Com a tela desatualizada, o backend mantém o
    // registro e responde sem mensagem (2.2).
    responder([], { favorito: true });
    const { unmount } = render(<ItemDetailsPage />);
    expect(await screen.findByRole("button", { name: /Favoritado/ })).toHaveAttribute("aria-pressed", "true");
    unmount();

    responder([rota("POST", "/favorites/1001", { status: 200, corpo: { item_id: 1001, favorito: true, message: null } })], { favorito: false });
    render(<ItemDetailsPage />);
    fireEvent.click(await controle());

    expect(await screen.findByRole("button", { name: /Favoritado/ })).toBeInTheDocument();
    expect(screen.queryByText(ADICIONADO)).not.toBeInTheDocument();
  });

  it("test_cu06_c1_fe1_falha_no_banco", async () => {
    entrar();
    responder([rota("POST", "/favorites/1001", { status: 503, corpo: { detail: FE1 } })], { favorito: false });
    render(<ItemDetailsPage />);

    fireEvent.click(await controle());

    expect(await screen.findByText(FE1)).toBeInTheDocument(); // 1.2
    expect(screen.getByRole("button", { name: /Favoritar/ })).toHaveAttribute("aria-pressed", "false");
  });
});
