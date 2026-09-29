import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A tela do item, de ponta a ponta no jsdom: o backend é substituído por respostas fixas (nenhum teste acessa a rede).
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1001" }),
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import type { HistoricoDoItem } from "@/lib/historicoDoItem";

const FE1 = "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde";
const FA1 = "Dados Desatualizados";
const FA2 = "Ainda não há dados históricos coletados suficientes para este item";

const PONTOS = [
  { timestamp: "2026-09-27T12:00:00Z", price: 120_000, quantity: 5, granularity: "HORARIA" as const },
  { timestamp: "2026-09-28T09:00:00Z", price: 124_900, quantity: 8, granularity: "HORARIA" as const },
];

function historico(alteracoes: Partial<HistoricoDoItem> = {}): HistoricoDoItem {
  return { janela: "14D", pontos: PONTOS, desatualizado: false, ultima_atualizacao_em: "2026-09-28T11:30:00Z", avisos: [], ...alteracoes };
}

interface Respostas {
  historico?: { status: number; corpo: unknown } | "rede";
  precoAtual?: { status: number; corpo: unknown };
}

function responder(respostas: Respostas) {
  const json = (status: number, corpo: unknown) => new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/history")) {
        if (respostas.historico === "rede") throw new TypeError("Failed to fetch");
        return json(respostas.historico?.status ?? 200, respostas.historico?.corpo ?? historico());
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
