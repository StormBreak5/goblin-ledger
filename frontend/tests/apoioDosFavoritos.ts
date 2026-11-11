import { vi } from "vitest";

// Respostas fixas dos testes de tela dos CU06 e CU07 (nenhum teste acessa a rede). Cada rota pode ser trocada; as que o
// teste não define respondem como um item sem projeção nem alertas.

export const TOKEN = "token-de-teste";
const CHAVE_DO_TOKEN = "goblin_ledger_token";

export type Resposta = { status: number; corpo?: unknown } | "rede";
export type Rota = (url: URL, metodo: string) => Resposta | undefined;

export interface Chamada {
  metodo: string;
  caminho: string; // com a query
  corpo: unknown;
}

export function entrar(): void {
  window.localStorage.setItem(CHAVE_DO_TOKEN, TOKEN);
}

export function sair(): void {
  window.localStorage.removeItem(CHAVE_DO_TOKEN);
}

const json = (status: number, corpo: unknown) =>
  new Response(corpo === undefined ? null : JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });

/** Substitui o fetch. `rotas` é consultada primeiro; devolve a lista das chamadas feitas, para o teste conferir. */
export function responder(rotas: Rota[] = [], item: { favorito?: boolean } = {}): Chamada[] {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (endereco: string, opcoes: RequestInit = {}) => {
      const url = new URL(endereco);
      const metodo = (opcoes.method ?? "GET").toUpperCase();
      chamadas.push({ metodo, caminho: url.pathname.replace("/api", "") + url.search, corpo: opcoes.body ? JSON.parse(String(opcoes.body)) : null });
      for (const rota of rotas) {
        const resposta = rota(url, metodo);
        if (resposta === "rede") throw new TypeError("Failed to fetch");
        if (resposta) return json(resposta.status, resposta.corpo);
      }
      const caminho = url.pathname;
      if (caminho.endsWith("/history")) {
        return json(200, {
          janela: "14D", dados_limitados: false, desatualizado: false, ultima_atualizacao_em: "2026-09-28T11:30:00Z", avisos: [],
          pontos: [{ timestamp: "2026-09-27T00:00:00Z", price: 172_000, quantity: 40, granularity: "DIARIA" }],
        });
      }
      if (caminho.endsWith("/current-auctions")) return json(200, { min_price: 172_000, total_quantity: 900, market_value: 179_500 });
      if (caminho.endsWith("/projection")) {
        return json(200, { situacao: "NAO_ELEGIVEL", mensagem: "Projeção indisponível", data_referencia: null, preco_referencia: null,
          erro_tipico_pct: null, desatualizada: false, predicoes: [], avisos: [] });
      }
      if (caminho.endsWith("/alerts") && metodo === "GET") return json(200, { alertas: [], ativos_do_usuario: 0, limite: 20 });
      if (/\/items\/\d+$/.test(caminho)) {
        const corpo: Record<string, unknown> = { id: 1001, name: "Mycobloom", icon_url: null };
        if (item.favorito !== undefined) corpo.favorito = item.favorito;
        return json(200, corpo);
      }
      return json(404, { detail: "rota não prevista no teste" });
    }),
  );
  return chamadas;
}

/** Uma rota fixa: o método e o caminho (sem `/api`, com a query, se houver) e a resposta. */
export function rota(metodo: string, caminho: string, resposta: Resposta | (() => Resposta)): Rota {
  return (url, m) => {
    if (m !== metodo || url.pathname.replace("/api", "") + url.search !== caminho) return undefined;
    return typeof resposta === "function" ? resposta() : resposta;
  };
}
