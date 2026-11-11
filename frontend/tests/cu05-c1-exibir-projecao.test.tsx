import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A tela do item com a projeção, de ponta a ponta no jsdom: o backend é substituído por respostas fixas. A situação e as
// mensagens vêm do backend (tests/integration/test_cu05_consultar_previsao.py); aqui, só como a tela as apresenta.
const { params, roteador } = vi.hoisted(() => ({ params: { id: "1001" }, roteador: { replace: () => {} } }));
vi.mock("next/navigation", () => ({ useParams: () => params, useRouter: () => roteador }));
vi.mock("@/components/Header", () => ({ default: () => null }));

import ItemDetailsPage from "@/app/item/[id]/page";
import { ESTIMATIVA, FE1, indisponivel, projecao, responder } from "./apoioDaProjecao";

const TITULO_DO_GRAFICO = { name: "Histórico de Preços (Ouro)" };

beforeEach(() => {
  window.sessionStorage.clear();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {}); // o Recharts avisa que o jsdom não tem tamanho de tela
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CU05-C1 – Exibir projeção de preços", () => {
  it("test_cu05_c1_fluxo_principal_exibe_a_projecao_dos_proximos_7_dias", async () => {
    responder();
    render(<ItemDetailsPage />);

    const secao = await screen.findByRole("region", { name: "Projeção" });
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // passo 1: o histórico continua
    expect(screen.getByText("Projeção (menor preço diário)")).toBeInTheDocument(); // passo 5: a legenda
    expect(screen.getByRole("button", { name: "Projeção" })).toHaveAttribute("aria-pressed", "true"); // controle do C3

    // Passo 6: a tabela, com a data, o preço previsto em Ouro/Prata/Cobre (passo 4, RN01) e a variação sobre o dia de D.
    expect(within(secao).getByRole("heading", { name: "Projeção para os próximos 7 dias" })).toBeInTheDocument();
    expect(within(secao).getByRole("columnheader", { name: "Variação sobre 27/09" })).toBeInTheDocument();
    const linhas = within(secao).getAllByRole("row").slice(1);
    expect(linhas).toHaveLength(7);
    expect(linhas[0]).toHaveTextContent("28/09/2026");
    expect(linhas[0]).toHaveTextContent("17g 35s");
    expect(linhas[0]).toHaveTextContent("+0,9%");
    expect(linhas[6]).toHaveTextContent("04/10/2026");

    // Passo 7: a data em que foi gerada, o erro típico e o aviso.
    expect(within(secao).getByText("Projeção gerada em 28/09/2026, a partir do menor preço diário de 27/09/2026")).toBeInTheDocument();
    expect(within(secao).getByText("Erro mediano de 8% nas previsões deste item")).toBeInTheDocument();
    expect(within(secao).getByText(ESTIMATIVA)).toBeInTheDocument();
    expect(screen.queryByText("Projeção desatualizada")).not.toBeInTheDocument();
  });

  it.each([
    ["test_cu05_c1_fa1_modelo_nao_treinado", "MODELO_NAO_TREINADO", "A projeção de preços ainda não está disponível"],
    ["test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27", "NAO_ELEGIVEL",
      "Projeção indisponível: este item tem pouca quantidade ofertada para uma previsão confiável"],
    ["test_cu05_c1_fa3_projecao_reprovada_rn10", "REPROVADA",
      "Projeção indisponível: as previsões deste item não atingiram a precisão mínima exigida"],
    ["test_cu05_c1_fa4_projecao_em_avaliacao", "EM_AVALIACAO",
      "A projeção deste item está em avaliação e será exibida quando houver dados suficientes para medir a sua precisão"],
    ["test_cu05_c1_fa5_projecao_suspensa_rn13", "SUSPENSA",
      "A projeção deste item está suspensa porque as previsões recentes ficaram abaixo da precisão mínima. Ela será reavaliada na próxima atualização do modelo"],
    ["test_cu05_c1_fa6_projecao_nao_disponivel", "NAO_DISPONIVEL", "A projeção deste item não está disponível no momento"],
  ] as const)("%s", async (_nome, situacao, mensagem) => {
    responder({ status: 200, corpo: indisponivel(situacao, mensagem) });
    render(<ItemDetailsPage />);

    expect(await screen.findByTestId("projecao-indisponivel")).toHaveTextContent(mensagem); // no lugar da projeção
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // o histórico continua
    expect(screen.queryByRole("region", { name: "Projeção" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Projeção" })).not.toBeInTheDocument(); // C3: só com a projeção disponível
    expect(screen.queryByText("Projeção (menor preço diário)")).not.toBeInTheDocument();
  });

  it("test_cu05_c1_fa7_projecao_desatualizada", async () => {
    const atrasada = projecao({
      data_referencia: "2026-09-23", desatualizada: true,
      predicoes: [["2026-09-28", 20_500, 2.5], ["2026-09-29", 20_600, 3.0], ["2026-09-30", 20_700, 3.5]].map(
        ([data_prevista, preco_previsto, variacao_pct]) => ({ data_prevista: String(data_prevista), preco_previsto: Number(preco_previsto), variacao_pct: Number(variacao_pct) })),
    });
    atrasada.avisos.push({ codigo: "DESATUALIZADA", texto: "Projeção desatualizada" });
    responder({ status: 200, corpo: atrasada });
    render(<ItemDetailsPage />);

    const secao = await screen.findByRole("region", { name: "Projeção" });
    expect(within(secao).getByText("Projeção desatualizada")).toBeInTheDocument(); // 7.2: o alerta
    expect(within(secao).getByRole("heading", { name: "Projeção para os próximos 3 dias" })).toBeInTheDocument();
    expect(within(secao).getAllByRole("row").slice(1)).toHaveLength(3); // só os dias a partir de hoje
    expect(within(secao).getByRole("columnheader", { name: "Variação sobre 23/09" })).toBeInTheDocument();
  });

  it("test_cu05_c1_fe1_falha_no_banco", async () => {
    responder({ status: 503, corpo: { detail: FE1 } });
    const { unmount } = render(<ItemDetailsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(FE1); // 1.2
    expect(screen.getByRole("heading", TITULO_DO_GRAFICO)).toBeInTheDocument(); // o histórico continua exibido
    expect(screen.queryByRole("button", { name: "Projeção" })).not.toBeInTheDocument();
    unmount();

    responder("rede"); // backend fora do ar: a mesma mensagem
    render(<ItemDetailsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(FE1);
  });
});
