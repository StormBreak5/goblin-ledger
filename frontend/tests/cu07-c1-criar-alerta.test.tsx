import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A seção "Alertas de preço" da tela do item (CU07-C1), no jsdom, com o backend substituído por respostas fixas. A
// validação (FA3), a cota (RN08) e a conversão para Cobre (RN01) são do backend; aqui, como a tela as apresenta.
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { entrar, responder, rota, sair } from "./apoioDosFavoritos";

const CRIADO = "Alerta criado com sucesso";
const FORA_DOS_FAVORITOS = "Para criar um alerta, adicione o item aos favoritos";
const LIMITE = "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para criar outro";
const INVALIDOS = "Informe o tipo de gatilho, um preço-alvo maior que zero e o canal de notificação";
const FE1 = "Não foi possível salvar o alerta no momento. Tente novamente mais tarde";
const COMPRA = { id_alerta: 7, item_id: 1001, tipo: "COMPRA", preco_alvo: 175_000, canal: "AMBOS", situacao: "ATIVO", disparado_em: null };
const formularioAberto = { status: 200, corpo: { item_id: 1001, market_value: 179_500, alerta: null } };

const secao = () => screen.findByRole("region", { name: "Alertas de preço" });

async function preencher(dialogo: HTMLElement) {
  fireEvent.click(within(dialogo).getByRole("button", { name: /Compra/ }));
  fireEvent.change(within(dialogo).getByLabelText("Ouro"), { target: { value: "17" } });
  fireEvent.change(within(dialogo).getByLabelText("Prata"), { target: { value: "50" } });
  fireEvent.click(within(dialogo).getByLabelText("Ambos"));
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

describe("CU07-C1 – Criar alerta de preço", () => {
  it("test_cu07_c1_fluxo_principal_cria_alerta", async () => {
    let criado = false;
    const chamadas = responder([
      rota("GET", "/items/1001/alerts/new", formularioAberto),
      rota("POST", "/items/1001/alerts", () => {
        criado = true;
        return { status: 201, corpo: { alerta: COMPRA, message: CRIADO } };
      }),
      rota("GET", "/items/1001/alerts", () => ({ status: 200, corpo: { alertas: criado ? [COMPRA] : [], ativos_do_usuario: criado ? 1 : 0, limite: 20 } })),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(within(await secao()).getByRole("button", { name: /Criar alerta/ })); // passo 1
    const dialogo = await screen.findByRole("dialog", { name: "Criar alerta de preço" }); // passo 4
    expect(within(dialogo).getByTestId("valor-de-referencia")).toHaveTextContent("17g 95s"); // RN06, em Ouro e Prata
    await preencher(dialogo); // passo 5
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await screen.findByText(CRIADO)).toBeInTheDocument(); // passo 8
    const linha = await within(await secao()).findByText(/preço cair até o alvo/);
    expect(linha.closest("tr")).toHaveTextContent("17g 50s");
    expect(linha.closest("tr")).toHaveTextContent("Tela e e-mail");
    expect(screen.getByTestId("cota")).toHaveTextContent("Você tem 1 de 20 alertas ativos em todos os seus itens");
    expect(chamadas.find((c) => c.metodo === "POST")?.corpo).toEqual({ tipo: "COMPRA", canal: "AMBOS", ouro: 17, prata: 50, cobre: null });
  });

  it("test_cu07_c1_fa1_item_fora_dos_favoritos", async () => {
    let favorito = false;
    const chamadas = responder([
      rota("GET", "/items/1001/alerts/new", () => (favorito ? formularioAberto : { status: 409, corpo: { detail: FORA_DOS_FAVORITOS } })),
      rota("POST", "/favorites/1001", () => {
        favorito = true;
        return { status: 200, corpo: { item_id: 1001, favorito: true, message: "Item adicionado aos favoritos" } };
      }),
    ], { favorito: false });
    render(<ItemDetailsPage />);

    fireEvent.click(within(await secao()).getByRole("button", { name: /Criar alerta/ }));
    const mensagem = await within(await secao()).findByRole("alert"); // 1.2
    expect(mensagem).toHaveTextContent(FORA_DOS_FAVORITOS);
    fireEvent.click(within(mensagem).getByRole("button", { name: /Adicionar aos favoritos/ })); // 1.3: CU06-C1

    expect(await screen.findByRole("dialog", { name: "Criar alerta de preço" })).toBeInTheDocument(); // 1.4: passo 3 e o formulário
    expect(chamadas.filter((c) => c.caminho === "/items/1001/alerts/new")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Favoritado/ })).toBeInTheDocument();
  });

  it("test_cu07_c1_fa2_limite_de_alertas_rn08", async () => {
    responder([rota("GET", "/items/1001/alerts/new", { status: 409, corpo: { detail: LIMITE } })], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(within(await secao()).getByRole("button", { name: /Criar alerta/ }));

    const mensagem = await within(await secao()).findByRole("alert"); // 2.2
    expect(mensagem).toHaveTextContent(LIMITE);
    expect(within(mensagem).queryByRole("button")).not.toBeInTheDocument(); // o item já é favorito: só a mensagem
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("test_cu07_c1_fa3_dados_invalidos", async () => {
    const chamadas = responder([
      rota("GET", "/items/1001/alerts/new", formularioAberto),
      rota("POST", "/items/1001/alerts", { status: 422, corpo: { detail: INVALIDOS } }),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(within(await secao()).getByRole("button", { name: /Criar alerta/ }));
    const dialogo = await screen.findByRole("dialog", { name: "Criar alerta de preço" });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" })); // sem tipo, preço nem canal

    expect(await within(dialogo).findByRole("alert")).toHaveTextContent(INVALIDOS); // 3.2
    expect(screen.getByRole("dialog", { name: "Criar alerta de preço" })).toBeInTheDocument(); // 3.3: volta ao passo 5
    expect(chamadas.find((c) => c.metodo === "POST")?.corpo).toEqual({ tipo: null, canal: null, ouro: null, prata: null, cobre: null });
  });

  it("test_cu07_c1_fe1_falha_no_banco", async () => {
    responder([
      rota("GET", "/items/1001/alerts/new", formularioAberto),
      rota("POST", "/items/1001/alerts", { status: 503, corpo: { detail: FE1 } }),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    fireEvent.click(within(await secao()).getByRole("button", { name: /Criar alerta/ }));
    const dialogo = await screen.findByRole("dialog", { name: "Criar alerta de preço" });
    await preencher(dialogo);
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await screen.findByText(FE1)).toBeInTheDocument(); // 1.2
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(within(await secao()).queryByRole("table")).not.toBeInTheDocument();
  });
});
