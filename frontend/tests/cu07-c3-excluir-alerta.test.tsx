import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// CU07-C3 (excluir um alerta) na tela do item, no jsdom, com o backend substituído por respostas fixas.
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { entrar, responder, rota, sair, type Resposta } from "./apoioDosFavoritos";

const EXCLUIDO = "Alerta excluído com sucesso";
const CONFIRMACAO = "Deseja excluir este alerta?";
const FE1 = "Não foi possível excluir o alerta no momento. Tente novamente mais tarde";
const ALERTA = { id_alerta: 7, item_id: 1001, tipo: "COMPRA", preco_alvo: 175_000, canal: "AMBOS", situacao: "ATIVO", disparado_em: null };

const secao = () => screen.findByRole("region", { name: "Alertas de preço" });

/** A lista do item com um alerta, que sai dela quando o DELETE responde 200. */
function backend(remover: Resposta) {
  let alertas = [ALERTA];
  return responder([
    rota("GET", "/items/1001/alerts", () => ({ status: 200, corpo: { alertas, ativos_do_usuario: alertas.length, limite: 20 } })),
    rota("DELETE", "/alerts/7", () => {
      if (remover !== "rede" && remover.status === 200) alertas = [];
      return remover;
    }),
  ], { favorito: true });
}

async function pedirExclusao(): Promise<HTMLElement> {
  const linha = await waitFor(async () => {
    const encontrada = (await secao()).querySelector<HTMLElement>('tr[data-alerta="7"]');
    expect(encontrada).not.toBeNull();
    return encontrada as HTMLElement;
  });
  fireEvent.click(within(linha).getByRole("button", { name: "Excluir" })); // passo 1
  const dialogo = await screen.findByRole("dialog", { name: "Excluir alerta" }); // passo 2
  expect(dialogo).toHaveTextContent(CONFIRMACAO);
  return dialogo;
}

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

describe("CU07-C3 – Excluir alerta de preço", () => {
  it("test_cu07_c3_fluxo_principal_exclui_alerta", async () => {
    const chamadas = backend({ status: 200, corpo: { message: EXCLUIDO } });
    render(<ItemDetailsPage />);

    const dialogo = await pedirExclusao();
    fireEvent.click(within(dialogo).getByRole("button", { name: "Excluir" })); // passo 3

    expect(await screen.findByText(EXCLUIDO)).toBeInTheDocument(); // passo 5
    await waitFor(async () => expect(within(await secao()).queryByRole("table")).not.toBeInTheDocument()); // a seção atualizada
    expect(screen.getByTestId("cota")).toHaveTextContent("Você tem 0 de 20 alertas ativos em todos os seus itens");
    expect(chamadas.filter((c) => c.metodo === "DELETE").map((c) => c.caminho)).toEqual(["/alerts/7"]); // passo 4
  });

  it("test_cu07_c3_fa1_exclusao_cancelada", async () => {
    const chamadas = backend({ status: 200, corpo: { message: EXCLUIDO } });
    render(<ItemDetailsPage />);

    const dialogo = await pedirExclusao();
    fireEvent.click(within(dialogo).getByRole("button", { name: "Cancelar" })); // 1.1

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect((await secao()).querySelector('tr[data-alerta="7"]')).not.toBeNull(); // 1.2: o alerta é mantido
    expect(chamadas.some((c) => c.metodo === "DELETE")).toBe(false);
    expect(screen.queryByText(EXCLUIDO)).not.toBeInTheDocument();
  });

  it("test_cu07_c3_fe1_falha_mantem_alerta", async () => {
    backend({ status: 503, corpo: { detail: FE1 } });
    render(<ItemDetailsPage />);

    const dialogo = await pedirExclusao();
    fireEvent.click(within(dialogo).getByRole("button", { name: "Excluir" }));

    expect(await screen.findByText(FE1)).toBeInTheDocument(); // 1.2
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect((await secao()).querySelector('tr[data-alerta="7"]')).not.toBeNull(); // o alerta é mantido
  });
});
