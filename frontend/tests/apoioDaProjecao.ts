import { vi } from "vitest";
import type { HistoricoDoItem, PontoDoHistorico } from "@/lib/historicoDoItem";
import type { ProjecaoDoItem } from "@/lib/projecaoDoItem";

// Dados e respostas fixas dos testes de tela do CU05 (nenhum teste acessa a rede). O fuso é o de Brasília (vitest.setup.ts).

export const ESTIMATIVA = "A projeção é uma estimativa estatística e não garante o preço futuro";
export const FE1 = "Não foi possível carregar a projeção no momento. Tente novamente mais tarde";

/** Série diária de 21 a 27/09 (00:00 UTC): o último preço diário, 17g 20s, é o ponto de partida da projeção. */
export const PONTOS: PontoDoHistorico[] = [21, 22, 23, 24, 25, 26, 27].map((dia, i) => ({
  timestamp: `2026-09-${dia}T00:00:00Z`, price: 170_000 + i * 333, quantity: 40 + i, granularity: "DIARIA",
}));
PONTOS[PONTOS.length - 1].price = 172_000;

export const PREVISTOS: [string, number, number][] = [
  ["2026-09-28", 173_500, 0.9], ["2026-09-29", 175_500, 2.0], ["2026-09-30", 177_000, 2.9], ["2026-10-01", 178_500, 3.8],
  ["2026-10-02", 178_000, 3.5], ["2026-10-03", 179_500, 4.4], ["2026-10-04", 181_000, 5.2],
];

export function projecao(alteracoes: Partial<ProjecaoDoItem> = {}): ProjecaoDoItem {
  return {
    situacao: "DISPONIVEL", mensagem: null, data_referencia: "2026-09-27", preco_referencia: 172_000, erro_tipico_pct: 8,
    desatualizada: false,
    predicoes: PREVISTOS.map(([data_prevista, preco_previsto, variacao_pct]) => ({ data_prevista, preco_previsto, variacao_pct })),
    avisos: [
      { codigo: "ORIGEM", texto: "Projeção gerada em 28/09/2026, a partir do menor preço diário de 27/09/2026" },
      { codigo: "ERRO_TIPICO", texto: "Erro mediano de 8% nas previsões deste item" },
      { codigo: "ESTIMATIVA", texto: ESTIMATIVA },
    ],
    ...alteracoes,
  };
}

export function indisponivel(situacao: ProjecaoDoItem["situacao"], mensagem: string): ProjecaoDoItem {
  return { situacao, mensagem, data_referencia: null, preco_referencia: null, erro_tipico_pct: null, desatualizada: false,
    predicoes: [], avisos: [] };
}

function historico(janela: string): HistoricoDoItem {
  return { janela, pontos: PONTOS, dados_limitados: false, desatualizado: false, ultima_atualizacao_em: "2026-09-28T11:30:00Z",
    avisos: [] };
}

/** Substitui o fetch: o item, o histórico, o preço atual e a projeção (uma resposta, `"rede"` ou um status de erro). */
export function responder(resposta: { status: number; corpo: unknown } | "rede" = { status: 200, corpo: projecao() }) {
  const json = (status: number, corpo: unknown) => new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/projection")) {
        if (resposta === "rede") throw new TypeError("Failed to fetch");
        return json(resposta.status, resposta.corpo);
      }
      if (url.includes("/history")) return json(200, historico(new URL(url).searchParams.get("window") ?? "14D"));
      if (url.includes("/current-auctions")) return json(200, { min_price: 172_000, total_quantity: 900, market_value: 179_500 });
      return json(200, { id: 1001, name: "Mycobloom", icon_url: null });
    }),
  );
}
