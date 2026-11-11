import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// CU06-C2 pela tela do item (o controle "Favoritado"). A lista de favoritos usa o mesmo fluxo (cu06-c3-lista).
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { entrar, responder, rota, sair, type Chamada } from "./apoioDosFavoritos";

const REMOVIDO = "Item removido dos favoritos";
const COM_ALERTAS = "Este item possui alertas de preço, que também serão excluídos. Deseja continuar?";
const FE1 = "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde";
const removido = { status: 200, corpo: { item_id: 1001, favorito: false, message: REMOVIDO } };
const remocoes = (chamadas: Chamada[]) => chamadas.filter((c) => c.metodo === "DELETE").map((c) => c.caminho);

beforeEach(() => {
  entrar();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  sair();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU06-C2 – Remover item dos favoritos", () => {
  it("test_cu06_c2_fluxo_principal_remove_favorito", async () => {
    const chamadas = responder([rota("DELETE", "/favorites/1001", removido)], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Favoritado/ })); // passo 1

    expect(await screen.findByRole("button", { name: /Favoritar/ })).toHaveAttribute("aria-pressed", "false"); // passo 4
    expect(screen.getByText(REMOVIDO)).toBeInTheDocument();
    expect(remocoes(chamadas)).toEqual(["/favorites/1001"]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // sem alertas, não há confirmação
  });

  it("test_cu06_c2_fa1_remove_os_alertas_do_item", async () => {
    const chamadas = responder([
      rota("DELETE", "/favorites/1001", { status: 409, corpo: { detail: COM_ALERTAS } }),
      rota("DELETE", "/favorites/1001?confirmar=true", removido),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Favoritado/ }));
    const dialogo = await screen.findByRole("dialog"); // 1.2: o aviso
    expect(dialogo).toHaveTextContent(COM_ALERTAS);
    fireEvent.click(within(dialogo).getByRole("button", { name: "Remover" })); // 1.3: confirma

    expect(await screen.findByRole("button", { name: /Favoritar/ })).toBeInTheDocument();
    expect(remocoes(chamadas)).toEqual(["/favorites/1001", "/favorites/1001?confirmar=true"]); // 1.4 e 1.5
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("test_cu06_c2_fa2_remocao_cancelada", async () => {
    const chamadas = responder([rota("DELETE", "/favorites/1001", { status: 409, corpo: { detail: COM_ALERTAS } })], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Favoritado/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancelar" })); // 2.1

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: /Favoritado/ })).toHaveAttribute("aria-pressed", "true"); // 2.2
    expect(remocoes(chamadas)).toEqual(["/favorites/1001"]); // nada confirmado
  });

  it("test_cu06_c2_fe1_falha_desfaz_remocoes", async () => {
    const chamadas = responder([
      rota("DELETE", "/favorites/1001", { status: 409, corpo: { detail: COM_ALERTAS } }),
      rota("DELETE", "/favorites/1001?confirmar=true", { status: 503, corpo: { detail: FE1 } }),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Favoritado/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remover" }));

    expect(await screen.findByText(FE1)).toBeInTheDocument(); // 1.2
    expect(screen.getByRole("button", { name: /Favoritado/ })).toBeInTheDocument(); // o item continua favorito
    expect(remocoes(chamadas)).toHaveLength(2);
  });
});
