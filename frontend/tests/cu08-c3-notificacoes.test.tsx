import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// CU08-C3 (consultar notificações) no sino do cabeçalho, no jsdom, com o backend substituído por respostas fixas.
const { roteador } = vi.hoisted(() => ({ roteador: { replace: vi.fn(), push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => roteador }));

import SinoDeNotificacoes, { INTERVALO_DO_CONTADOR_MS } from "@/components/SinoDeNotificacoes";
import { entrar, responder, rota, sair, type Resposta } from "./apoioDosFavoritos";

const VAZIO = "Você não tem notificações";
const FE1 = "Não foi possível carregar as notificações no momento. Tente novamente mais tarde";
const NOTIFICACOES = [
  { id_notificacao: 3, item_id: 1001, name: "Mycobloom", icon_url: "https://icone.exemplo/mycobloom.jpg", tipo: "COMPRA",
    preco_alvo: 175_000, valor_mercado: 174_200, disparada_em: "2026-10-21T05:12:00Z", lida: false },
  { id_notificacao: 2, item_id: 1002, name: "Bismuth", icon_url: null, tipo: "VENDA",
    preco_alvo: 130_000, valor_mercado: 132_000, disparada_em: "2026-10-20T21:12:00Z", lida: false },
  { id_notificacao: 1, item_id: 1003, name: "Algari Healing Potion", icon_url: null, tipo: "COMPRA",
    preco_alvo: 1_200_000, valor_mercado: 1_198_000, disparada_em: "2026-10-18T12:12:00Z", lida: true },
];

function dataEHoraLocal(instante: string): string {
  const data = new Date(instante);
  return `${data.toLocaleDateString("pt-BR")} às ${data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

/** O backend do sino: o contador, a lista e a marcação como lidas (que zera o contador). */
function backend({ lista, marcar }: { lista?: Resposta; marcar?: Resposta } = {}) {
  let naoLidas = 2;
  return responder([
    rota("GET", "/notifications/unread-count", () => ({ status: 200, corpo: { nao_lidas: naoLidas } })),
    rota("GET", "/notifications", lista ?? { status: 200, corpo: { notificacoes: NOTIFICACOES, nao_lidas: 2, mensagem: null } }),
    rota("POST", "/notifications/read", () => {
      const resposta = marcar ?? { status: 200, corpo: { nao_lidas: 0 } };
      if (resposta !== "rede" && resposta.status === 200) naoLidas = 0;
      return resposta;
    }),
  ]);
}

const sino = () => screen.getByRole("button", { name: "Notificações" });

async function abrirPainel(): Promise<HTMLElement> {
  fireEvent.click(sino()); // passo 2
  return screen.findByRole("dialog", { name: "Notificações" });
}

beforeEach(() => {
  entrar();
  roteador.push.mockClear();
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  sair();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU08-C3 – Consultar notificações", () => {
  it("test_cu08_c3_fluxo_principal_lista_destaca_e_marca_como_lidas", async () => {
    const chamadas = backend();
    render(<SinoDeNotificacoes />);
    expect(await screen.findByTestId("contador")).toHaveTextContent("2"); // passo 1

    const painel = await abrirPainel();

    // Passos 3 e 4: da mais recente para a mais antiga, com o item, o tipo, o alvo, o valor e a data; não lidas destacadas.
    await within(painel).findByText("Mycobloom");
    expect(within(painel).getByTestId("nao-lidas-do-painel")).toHaveTextContent("2 não lidas");
    const linhas = Array.from(painel.querySelectorAll<HTMLElement>("[data-notificacao]"));
    expect(linhas.map((l) => l.dataset.notificacao)).toEqual(["3", "2", "1"]);
    expect(linhas.map((l) => l.dataset.lida)).toEqual(["nao", "nao", "sim"]);
    expect(linhas[0]).toHaveTextContent("Mycobloom atingiu o preço do seu alerta de compra");
    expect(linhas[0]).toHaveTextContent("Alvo: 17g 50s · Valor de mercado: 17g 42s");
    expect(linhas[0]).toHaveTextContent(dataEHoraLocal("2026-10-21T05:12:00Z"));
    expect(linhas[1]).toHaveTextContent("Bismuth atingiu o preço do seu alerta de venda");
    expect(linhas[1]).toHaveTextContent("Alvo: 13g · Valor de mercado: 13g 20s");
    expect(within(linhas[0]).getByLabelText("Não lida")).toBeInTheDocument();
    expect(within(linhas[2]).queryByLabelText("Não lida")).toBeNull();

    // Passo 5: as exibidas ficam lidas e o contador zera; o destaque continua enquanto o painel está aberto.
    await waitFor(() => expect(screen.queryByTestId("contador")).toBeNull());
    expect(chamadas.find((c) => c.metodo === "POST")).toEqual({ metodo: "POST", caminho: "/notifications/read", corpo: { ids: [3, 2] } });
    expect(linhas[0].dataset.lida).toBe("nao");

    // Passo 6: selecionar uma notificação abre a tela do item e fecha o painel.
    fireEvent.click(linhas[1]);
    expect(roteador.push).toHaveBeenCalledWith("/item/1002");
    expect(screen.queryByRole("dialog", { name: "Notificações" })).toBeNull();
  });

  it("test_cu08_c3_passo1_contador_ao_carregar_e_a_cada_5_minutos", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    let naoLidas = 1;
    const chamadas = responder([rota("GET", "/notifications/unread-count", () => ({ status: 200, corpo: { nao_lidas: naoLidas } }))]);
    const { unmount } = render(<SinoDeNotificacoes />);
    expect(await screen.findByTestId("contador")).toHaveTextContent("1");

    naoLidas = 3; // um ciclo de ingestão disparou mais dois alertas
    await act(async () => {
      vi.advanceTimersByTime(INTERVALO_DO_CONTADOR_MS);
    });

    await waitFor(() => expect(screen.getByTestId("contador")).toHaveTextContent("3"));
    expect(chamadas.filter((c) => c.caminho === "/notifications/unread-count")).toHaveLength(2);
    unmount();

    // Usuário anônimo: não há sino (pré-condição: autenticado).
    sair();
    render(<SinoDeNotificacoes />);
    expect(screen.queryByRole("button", { name: "Notificações" })).toBeNull();
  });

  it("test_cu08_c3_fa1_nenhuma_notificacao", async () => {
    const chamadas = backend({ lista: { status: 200, corpo: { notificacoes: [], nao_lidas: 0, mensagem: VAZIO } } });
    render(<SinoDeNotificacoes />);

    const painel = await abrirPainel();

    expect(await within(painel).findByText(VAZIO)).toBeInTheDocument();
    expect(painel.querySelectorAll("[data-notificacao]")).toHaveLength(0);
    expect(chamadas.some((c) => c.metodo === "POST")).toBe(false);
  });

  it("test_cu08_c3_fe1_falha_ao_carregar", async () => {
    backend({ lista: { status: 503, corpo: { detail: FE1 } } });
    render(<SinoDeNotificacoes />);
    await screen.findByTestId("contador");

    const painel = await abrirPainel();

    expect(await within(painel).findByRole("alert")).toHaveTextContent(FE1);
    expect(screen.getByTestId("contador")).toHaveTextContent("2"); // nada foi marcado
  });

  it("test_cu08_c3_fe1_falha_ao_marcar_como_lidas", async () => {
    backend({ marcar: { status: 503, corpo: { detail: FE1 } } });
    render(<SinoDeNotificacoes />);
    await screen.findByTestId("contador");

    const painel = await abrirPainel();

    expect(await within(painel).findByRole("alert")).toHaveTextContent(FE1);
    expect(within(painel).getByText("Mycobloom")).toBeInTheDocument(); // a lista exibida continua
    expect(screen.getByTestId("contador")).toHaveTextContent("2"); // o contador fica como estava
  });
});
