import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A tela do item, de ponta a ponta no jsdom: o backend é substituído por respostas fixas (nenhum teste acessa a rede).
// O useRouter do Next devolve sempre o mesmo objeto; um novo a cada renderização refaria a busca do item sem parar.
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: () => {} } }));
vi.mock("next/navigation", () => ({
  useParams: () => params,
  useRouter: () => roteador,
}));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import type { HistoricoDoItem } from "@/lib/historicoDoItem";
import Toast from "@/components/Toast";

const FE1 = "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde";
const FA1 = "Dados Desatualizados";
const FA2 = "Ainda não há dados históricos coletados suficientes para este item";
const C2_FA1 = "Dados limitados. Exibindo todo o histórico disponível para o período selecionado.";
const C2_FE1 = "Erro ao carregar novos dados. Mantendo a visualização atual.";

const PONTOS = [
  { timestamp: "2026-09-27T12:00:00Z", price: 120_000, quantity: 5, granularity: "HORARIA" as const },
  { timestamp: "2026-09-28T09:00:00Z", price: 124_900, quantity: 8, granularity: "HORARIA" as const },
];

function historico(alteracoes: Partial<HistoricoDoItem> = {}): HistoricoDoItem {
  return {
    janela: "14D", pontos: PONTOS, dados_limitados: false, desatualizado: false, ultima_atualizacao_em: "2026-09-28T11:30:00Z",
    avisos: [], ...alteracoes,
  };
}

type RespostaDoHistorico = { status: number; corpo: unknown } | "rede";

interface Respostas {
  /** Uma resposta fixa, ou uma função da janela pedida (para testar a troca de janela). */
  historico?: RespostaDoHistorico | ((janela: string) => RespostaDoHistorico);
  precoAtual?: { status: number; corpo: unknown };
}

function responder(respostas: Respostas) {
  const json = (status: number, corpo: unknown) => new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/history")) {
        const janela = new URL(url).searchParams.get("window") ?? "14D";
        const resposta = typeof respostas.historico === "function" ? respostas.historico(janela) : respostas.historico;
        if (resposta === "rede") throw new TypeError("Failed to fetch");
        return json(resposta?.status ?? 200, resposta?.corpo ?? historico({ janela }));
      }
      if (url.includes("/current-auctions")) {
        const preco = respostas.precoAtual ?? { status: 200, corpo: { min_price: 100_000, total_quantity: 10, market_value: 124_900 } };
        return json(preco.status, preco.corpo);
      }
      return json(200, { id: 1001, name: "Nightshade", icon_url: null }); // CU03-C3: dados do item
    }),
  );
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {}); // o Recharts avisa que o jsdom não tem tamanho de tela
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU04-C1 – Renderizar histórico de preços", () => {
  it("test_cu04_c1_fluxo_principal_cabecalho_com_valor_de_mercado_e_menor_preco", async () => {
    responder({});

    render(<ItemDetailsPage />);

    expect(await screen.findByRole("heading", { name: "Histórico de Preços (Ouro)" })).toBeInTheDocument(); // passo 5
    expect(await screen.findByText("Valor de mercado")).toBeInTheDocument(); // passo 3 / RN06
    expect(screen.getByTestId("valor-em-destaque")).toHaveTextContent("12g 49s");
    expect(screen.getByTestId("menor-preco")).toHaveTextContent("Menor preço: 10g");
    expect(screen.getByText("10 leilões ativos")).toBeInTheDocument();
    expect(screen.queryByText(FA1)).not.toBeInTheDocument();
  });

  it("test_cu04_c1_fluxo_principal_sem_valor_de_mercado_o_menor_preco_e_o_destaque", async () => {
    responder({ precoAtual: { status: 200, corpo: { min_price: 100_000, total_quantity: 3, market_value: null } } });

    render(<ItemDetailsPage />);

    expect(await screen.findByTestId("valor-em-destaque")).toHaveTextContent("10g");
    expect(screen.getByText("Menor preço")).toBeInTheDocument();
    expect(screen.queryByTestId("menor-preco")).not.toBeInTheDocument();
  });

  it("test_cu04_c1_fluxo_principal_ficha_do_wow_mostra_o_preco_sem_contagem_de_leiloes", async () => {
    responder({ precoAtual: { status: 200, corpo: { min_price: 2_865_410_000, total_quantity: null, market_value: 2_865_410_000 } } });

    render(<ItemDetailsPage />);

    expect(await screen.findByTestId("valor-em-destaque")).toHaveTextContent("286.541g");
    expect(screen.queryByText(/leilões ativos/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("menor-preco")).not.toBeInTheDocument(); // igual ao valor de mercado: não repete
  });

  it("test_cu04_c1_fa1_dados_desatualizados_mostra_o_selo_e_desenha_o_grafico", async () => {
    responder({ historico: { status: 200, corpo: historico({ desatualizado: true, avisos: [{ codigo: "DADOS_DESATUALIZADOS", texto: FA1 }] }) } });

    render(<ItemDetailsPage />);

    expect(await screen.findByText(FA1)).toBeInTheDocument(); // 1.3
    expect(screen.getByRole("heading", { name: "Histórico de Preços (Ouro)" })).toBeInTheDocument(); // 1.2: o gráfico segue
  });

  it("test_cu04_c1_fa2_item_sem_historico_mostra_a_mensagem_do_cenario", async () => {
    responder({ historico: { status: 200, corpo: historico({ pontos: [], avisos: [{ codigo: "SEM_HISTORICO", texto: FA2 }] }) } });

    render(<ItemDetailsPage />);

    expect(await screen.findByText(FA2)).toBeInTheDocument(); // 2.2
    expect(screen.queryByRole("heading", { name: "Histórico de Preços (Ouro)" })).not.toBeInTheDocument();
    expect(screen.queryByText(FA1)).not.toBeInTheDocument();
  });

  it("test_cu04_c1_fe1_falha_ao_recuperar_o_historico_mostra_a_mensagem_do_cenario", async () => {
    responder({ historico: { status: 503, corpo: { detail: FE1 } } });

    render(<ItemDetailsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(FE1); // 1.2
    expect(screen.queryByRole("heading", { name: "Histórico de Preços (Ouro)" })).not.toBeInTheDocument();
  });

  it("test_cu04_c1_fe1_backend_fora_do_ar_usa_a_mesma_mensagem", async () => {
    responder({ historico: "rede" });

    render(<ItemDetailsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(FE1);
  });
});

const chamadasAoHistorico = () =>
  (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/history"));

const botao = (nome: string) => screen.getByRole("button", { name: nome });
const TITULO_DO_GRAFICO = { name: "Histórico de Preços (Ouro)" };

describe("CU04-C2 – Alterar janela de tempo do gráfico", () => {
  it("test_cu04_c2_fluxo_principal_troca_a_janela_e_pede_o_novo_recorte", async () => {
    responder({});
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);
    expect(botao("14 Dias")).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(botao("3 Meses"));

    await waitFor(() => expect(botao("3 Meses")).toHaveAttribute("aria-pressed", "true"));
    expect(botao("14 Dias")).toHaveAttribute("aria-pressed", "false");
    expect(chamadasAoHistorico().map((url) => new URL(url).searchParams.get("window"))).toEqual(["14D", "90D"]);
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // passo 4: re-renderizado
    expect(screen.queryByText(C2_FE1)).not.toBeInTheDocument();
  });

  it("test_cu04_c2_fluxo_principal_todas_as_janelas_do_documento", async () => {
    responder({});
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);

    for (const [nome, janela] of [["1 Mês", "30D"], ["1 Ano", "365D"], ["Tudo", "ALL"]] as const) {
      fireEvent.click(botao(nome));
      await waitFor(() => expect(botao(nome)).toHaveAttribute("aria-pressed", "true"));
      expect(chamadasAoHistorico().at(-1)).toContain(`window=${janela}`);
    }
  });

  it("test_cu04_c2_fluxo_principal_clicar_na_janela_ja_exibida_nao_pede_de_novo", async () => {
    responder({});
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);

    fireEvent.click(botao("14 Dias"));

    expect(chamadasAoHistorico()).toHaveLength(1);
  });

  it("test_cu04_c2_fa1_dados_limitados_mostra_o_aviso_do_cenario", async () => {
    responder({
      historico: (janela) => ({
        status: 200,
        corpo: janela === "365D" ? historico({ janela, dados_limitados: true, avisos: [{ codigo: "DADOS_LIMITADOS", texto: C2_FA1 }] }) : historico({ janela }),
      }),
    });
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);
    expect(screen.queryByText(C2_FA1)).not.toBeInTheDocument();

    fireEvent.click(botao("1 Ano"));

    expect(await screen.findByText(C2_FA1)).toBeInTheDocument(); // 1.3
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // 1.4: o gráfico segue, com o que há
  });

  it("test_cu04_c2_fe1_falha_ao_trocar_a_janela_mantem_a_visualizacao_atual", async () => {
    responder({ historico: (janela) => (janela === "14D" ? { status: 200, corpo: historico() } : { status: 503, corpo: { detail: FE1 } }) });
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);

    fireEvent.click(botao("1 Ano"));

    expect(await screen.findByText(C2_FE1)).toBeInTheDocument(); // 1.2: toast
    expect(botao("14 Dias")).toHaveAttribute("aria-pressed", "true"); // 1.3: a janela anterior continua
    expect(botao("1 Ano")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // o gráfico não sumiu
    expect(screen.queryByText(FE1)).not.toBeInTheDocument(); // e a tela de erro do C1-FE1 não o substitui
  });

  it("test_cu04_c2_fe1_backend_fora_do_ar_ao_trocar_a_janela_tem_o_mesmo_tratamento", async () => {
    responder({ historico: (janela) => (janela === "14D" ? { status: 200, corpo: historico() } : "rede") });
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);

    fireEvent.click(botao("Tudo"));

    expect(await screen.findByText(C2_FE1)).toBeInTheDocument();
    expect(botao("14 Dias")).toHaveAttribute("aria-pressed", "true");
  });

  it("test_cu04_c2_fe1_depois_da_falha_uma_nova_troca_funciona", async () => {
    let falhar = true;
    responder({ historico: (janela) => (janela !== "14D" && falhar ? { status: 503, corpo: { detail: FE1 } } : { status: 200, corpo: historico({ janela }) }) });
    render(<ItemDetailsPage />);
    await screen.findByRole("heading", TITULO_DO_GRAFICO);
    fireEvent.click(botao("1 Mês"));
    await screen.findByText(C2_FE1);

    falhar = false;
    fireEvent.click(botao("1 Mês"));

    await waitFor(() => expect(botao("1 Mês")).toHaveAttribute("aria-pressed", "true"));
    expect(screen.queryByText(C2_FE1)).not.toBeInTheDocument(); // um novo pedido limpa o aviso anterior
  });

  it("test_cu04_c2_o_pedido_mais_novo_cancela_o_anterior", async () => {
    const pendentes: Record<string, (resposta: Response) => void> = {};
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/history")) {
          const janela = new URL(url).searchParams.get("window") ?? "14D";
          return new Promise<Response>((resolver) => (pendentes[janela] = resolver));
        }
        if (url.includes("/current-auctions")) return Promise.resolve(new Response(JSON.stringify({ min_price: 0, total_quantity: 0, market_value: null })));
        return Promise.resolve(new Response(JSON.stringify({ id: 1001, name: "Nightshade", icon_url: null })));
      }),
    );
    const resposta = (janela: string) => new Response(JSON.stringify(historico({ janela })), { status: 200 });
    render(<ItemDetailsPage />);
    await waitFor(() => expect(pendentes["14D"]).toBeDefined());
    await act(async () => pendentes["14D"](resposta("14D")));
    await screen.findByRole("heading", TITULO_DO_GRAFICO);

    fireEvent.click(botao("1 Mês"));
    expect(botao("1 Mês")).toHaveAttribute("aria-pressed", "true"); // a janela pedida já aparece marcada enquanto carrega
    fireEvent.click(botao("1 Ano"));
    await waitFor(() => expect(pendentes["365D"]).toBeDefined());
    await act(async () => pendentes["365D"](resposta("365D")));
    await act(async () => pendentes["30D"](resposta("30D"))); // chega atrasado e é ignorado

    expect(botao("1 Ano")).toHaveAttribute("aria-pressed", "true");
    expect(botao("1 Mês")).toHaveAttribute("aria-pressed", "false");
  });
});

describe("CU04-C2-FE1 – toast", () => {
  it("test_cu04_c2_fe1_o_toast_some_sozinho_e_pode_ser_fechado", () => {
    vi.useFakeTimers();
    const aoFechar = vi.fn();
    const { rerender } = render(<Toast texto={C2_FE1} onFechar={aoFechar} duracaoMs={5000} />);

    expect(screen.getByRole("status")).toHaveTextContent(C2_FE1);
    act(() => vi.advanceTimersByTime(4999));
    expect(aoFechar).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(2));
    expect(aoFechar).toHaveBeenCalledTimes(1);

    rerender(<Toast texto={C2_FE1} onFechar={aoFechar} duracaoMs={5000} />);
    fireEvent.click(screen.getByRole("button", { name: "Fechar aviso" }));
    expect(aoFechar).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
