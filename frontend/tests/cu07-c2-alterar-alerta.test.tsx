import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// CU07-C2 (alterar ou reativar um alerta) na tela do item, no jsdom, com o backend substituído por respostas fixas. A
// cota da reativação (RN08), a validação (FA3) e a conversão para Cobre (RN01) são do backend; aqui, como a tela as mostra.
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { entrar, responder, rota, sair, type Resposta } from "./apoioDosFavoritos";

const ATUALIZADO = "Alerta atualizado com sucesso";
const LIMITE = "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para reativar este";
const INVALIDOS = "Informe o tipo de gatilho, um preço-alvo maior que zero e o canal de notificação";
const FE1 = "Não foi possível salvar o alerta no momento. Tente novamente mais tarde";
const ATIVO = { id_alerta: 7, item_id: 1001, tipo: "COMPRA", preco_alvo: 175_000, canal: "AMBOS", situacao: "ATIVO", disparado_em: null };
const DISPARADO = { ...ATIVO, tipo: "VENDA", preco_alvo: 200_000, canal: "WEB", situacao: "DISPARADO", disparado_em: "2026-11-10T15:30:00Z" };

type AlertaDeTeste = typeof ATIVO | typeof DISPARADO;

const secao = () => screen.findByRole("region", { name: "Alertas de preço" });
const linhaDoAlerta = async () => (await secao()).querySelector<HTMLElement>('tr[data-alerta="7"]');

/** A lista do item (com o alerta atual) e o formulário de edição; `put` decide a resposta da gravação. */
function backend(inicial: AlertaDeTeste, put: (corpo: unknown) => Resposta, ativos = 0) {
  let atual: AlertaDeTeste = inicial;
  const chamadas = responder([
    rota("GET", "/items/1001/alerts", () => ({ status: 200, corpo: { alertas: [atual], ativos_do_usuario: ativos, limite: 20 } })),
    rota("GET", "/alerts/7/edit", () => ({ status: 200, corpo: { item_id: 1001, market_value: 179_500, alerta: atual } })),
    rota("PUT", "/alerts/7", () => {
      const resposta = put(chamadas.at(-1)?.corpo);
      if (resposta !== "rede" && resposta.status === 200) {
        atual = (resposta.corpo as { alerta: AlertaDeTeste }).alerta;
        ativos = 1;
      }
      return resposta;
    }),
  ], { favorito: true });
  return chamadas;
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

describe("CU07-C2 – Alterar ou reativar alerta de preço", () => {
  it("test_cu07_c2_fluxo_principal_altera_alerta", async () => {
    const alterado = { ...ATIVO, preco_alvo: 185_000, canal: "EMAIL" };
    const chamadas = backend(ATIVO, () => ({ status: 200, corpo: { alerta: alterado, message: ATUALIZADO } }), 1);
    render(<ItemDetailsPage />);

    const linha = await waitFor(async () => {
      const encontrada = await linhaDoAlerta();
      expect(encontrada).not.toBeNull();
      return encontrada as HTMLElement;
    });
    fireEvent.click(within(linha).getByRole("button", { name: "Editar" })); // passo 1

    const dialogo = await screen.findByRole("dialog", { name: "Alterar alerta de preço" }); // passo 2: os dados atuais
    expect(within(dialogo).getByRole("button", { name: /Compra/ })).toHaveAttribute("aria-pressed", "true");
    expect(within(dialogo).getByLabelText("Ouro")).toHaveValue("17");
    expect(within(dialogo).getByLabelText("Prata")).toHaveValue("50");
    expect(within(dialogo).getByLabelText("Ambos")).toBeChecked();
    expect(within(dialogo).getByTestId("valor-de-referencia")).toHaveTextContent("17g 95s"); // RN06
    fireEvent.change(within(dialogo).getByLabelText("Ouro"), { target: { value: "18" } }); // passo 3
    fireEvent.click(within(dialogo).getByLabelText("E-mail"));
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await screen.findByText(ATUALIZADO)).toBeInTheDocument(); // passo 6
    await waitFor(async () => expect(await linhaDoAlerta()).toHaveTextContent("18g 50s"));
    expect(await linhaDoAlerta()).toHaveTextContent("E-mail");
    expect(within((await linhaDoAlerta()) as HTMLElement).getByTestId("situacao")).toHaveTextContent("Ativo"); // passo 5
    expect(chamadas.find((c) => c.metodo === "PUT")?.corpo).toEqual({ tipo: "COMPRA", canal: "EMAIL", ouro: 18, prata: 50, cobre: 0 });
  });

  it("test_cu07_c2_fa1_reativa_alerta_disparado", async () => {
    const reativado = { ...DISPARADO, situacao: "ATIVO", disparado_em: null };
    const chamadas = backend(DISPARADO, () => ({ status: 200, corpo: { alerta: reativado, message: ATUALIZADO } }));
    render(<ItemDetailsPage />);

    const linha = await waitFor(async () => {
      const encontrada = await linhaDoAlerta();
      expect(encontrada).not.toBeNull();
      return encontrada as HTMLElement;
    });
    expect(within(linha).getByTestId("situacao")).toHaveTextContent(/^Disparado em \d{2}\/\d{2}\/\d{4} às \d{2}:\d{2}$/);
    fireEvent.click(within(linha).getByRole("button", { name: "Editar e reativar" })); // 1.1

    // 1.2 (a cota) é do backend, no /edit; 1.3: volta ao passo 2, com o formulário de reativação.
    const dialogo = await screen.findByRole("dialog", { name: "Reativar alerta de preço" });
    expect(within(dialogo).getByRole("button", { name: /Venda/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await screen.findByText(ATUALIZADO)).toBeInTheDocument();
    await waitFor(async () => expect(within((await linhaDoAlerta()) as HTMLElement).getByTestId("situacao")).toHaveTextContent("Ativo"));
    expect(within((await linhaDoAlerta()) as HTMLElement).getByRole("button", { name: "Editar" })).toBeInTheDocument();
    expect(screen.getByTestId("cota")).toHaveTextContent("Você tem 1 de 20 alertas ativos em todos os seus itens");
    expect(chamadas.filter((c) => c.caminho === "/alerts/7/edit")).toHaveLength(1);
  });

  it("test_cu07_c2_fa2_limite_na_reativacao_rn08", async () => {
    responder([
      rota("GET", "/items/1001/alerts", { status: 200, corpo: { alertas: [DISPARADO], ativos_do_usuario: 20, limite: 20 } }),
      rota("GET", "/alerts/7/edit", { status: 409, corpo: { detail: LIMITE } }),
    ], { favorito: true });
    render(<ItemDetailsPage />);

    const linha = await waitFor(async () => {
      const encontrada = await linhaDoAlerta();
      expect(encontrada).not.toBeNull();
      return encontrada as HTMLElement;
    });
    fireEvent.click(within(linha).getByRole("button", { name: "Editar e reativar" }));

    const mensagem = await within(await secao()).findByRole("alert"); // 2.2
    expect(mensagem).toHaveTextContent(LIMITE);
    expect(within(mensagem).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // 2.3: fim, sem o formulário
    expect(within(linha).getByTestId("situacao")).toHaveTextContent("Disparado");
  });

  it("test_cu07_c2_fa3_dados_invalidos", async () => {
    const chamadas = backend(ATIVO, () => ({ status: 422, corpo: { detail: INVALIDOS } }), 1);
    render(<ItemDetailsPage />);

    const linha = await waitFor(async () => {
      const encontrada = await linhaDoAlerta();
      expect(encontrada).not.toBeNull();
      return encontrada as HTMLElement;
    });
    fireEvent.click(within(linha).getByRole("button", { name: "Editar" }));
    const dialogo = await screen.findByRole("dialog", { name: "Alterar alerta de preço" });
    for (const campo of ["Ouro", "Prata", "Cobre"]) fireEvent.change(within(dialogo).getByLabelText(campo), { target: { value: "0" } });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await within(dialogo).findByRole("alert")).toHaveTextContent(INVALIDOS); // 3.2
    expect(screen.getByRole("dialog", { name: "Alterar alerta de preço" })).toBeInTheDocument(); // 3.3: volta ao passo 3
    expect(within(dialogo).getByLabelText("Ouro")).toHaveValue("0"); // o que foi digitado continua no formulário
    expect(chamadas.find((c) => c.metodo === "PUT")?.corpo).toEqual({ tipo: "COMPRA", canal: "AMBOS", ouro: 0, prata: 0, cobre: 0 });
  });

  it("test_cu07_c2_fe1_falha_mantem_dados", async () => {
    backend(ATIVO, () => ({ status: 503, corpo: { detail: FE1 } }), 1);
    render(<ItemDetailsPage />);

    const linha = await waitFor(async () => {
      const encontrada = await linhaDoAlerta();
      expect(encontrada).not.toBeNull();
      return encontrada as HTMLElement;
    });
    fireEvent.click(within(linha).getByRole("button", { name: "Editar" }));
    const dialogo = await screen.findByRole("dialog", { name: "Alterar alerta de preço" });
    fireEvent.change(within(dialogo).getByLabelText("Ouro"), { target: { value: "30" } });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar alerta" }));

    expect(await screen.findByText(FE1)).toBeInTheDocument(); // 1.2
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await linhaDoAlerta()).toHaveTextContent("17g 50s"); // os dados anteriores do alerta
  });
});
