import { API_BASE_URL } from "@/lib/api";

// CU04 – Visualizar Histórico. Os avisos e as regras (frescor, janela, valor de mercado) vêm do backend; aqui ficam só os
// textos usados quando o backend não chegou a responder (rede fora do ar).
export const MSG_FALHA_NO_HISTORICO = "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde"; // C1-FE1
export const MSG_FALHA_NA_NOVA_JANELA = "Erro ao carregar novos dados. Mantendo a visualização atual."; // C2-FE1

export type Granularidade = "DIARIA" | "HORARIA"; // RN16

export interface PontoDoHistorico {
  timestamp: string; // instante em UTC, com o fuso explícito
  price: number; // Cobre (RN01)
  quantity: number | null; // a fonte pode não informar o volume (C3-FA1)
  granularity: Granularidade;
}

export interface AvisoDoHistorico {
  codigo: "SEM_HISTORICO" | "DADOS_DESATUALIZADOS" | "DADOS_LIMITADOS";
  texto: string;
}

export interface HistoricoDoItem {
  janela: string;
  pontos: PontoDoHistorico[];
  dados_limitados: boolean; // C2-FA1: o histórico não cobre a janela pedida
  desatualizado: boolean;
  ultima_atualizacao_em: string | null;
  avisos: AvisoDoHistorico[];
}

export interface PrecoAtual {
  min_price: number; // menor preço de compra (Cobre)
  total_quantity: number | null; // a Ficha do WoW não tem leilões
  market_value: number | null; // 1º quartil dos leilões ativos (RN06)
}

export type Consulta<T> = { ok: true; data: T } | { ok: false; message: string };

function detalhe(corpo: unknown): string | null {
  if (typeof corpo === "object" && corpo !== null) {
    const valor = (corpo as Record<string, unknown>).detail;
    if (typeof valor === "string") return valor;
  }
  return null;
}

/** CU04-C1 / C2: a série do item na janela pedida ("14D", "30D", "90D", "365D" ou "ALL"). */
export async function carregarHistorico(id: string, janela: string, signal?: AbortSignal): Promise<Consulta<HistoricoDoItem>> {
  try {
    const resposta = await fetch(`${API_BASE_URL}/items/${encodeURIComponent(id)}/history?window=${encodeURIComponent(janela)}`, { signal });
    if (resposta.ok) return { ok: true, data: (await resposta.json()) as HistoricoDoItem };
    const corpo: unknown = await resposta.json().catch(() => null);
    return { ok: false, message: detalhe(corpo) ?? MSG_FALHA_NO_HISTORICO };
  } catch {
    return { ok: false, message: MSG_FALHA_NO_HISTORICO };
  }
}

/** CU04-C1 passo 3: menor preço e valor de mercado (RN06) do item no último ciclo de ingestão. */
export async function carregarPrecoAtual(id: string, signal?: AbortSignal): Promise<Consulta<PrecoAtual>> {
  try {
    const resposta = await fetch(`${API_BASE_URL}/items/${encodeURIComponent(id)}/current-auctions`, { signal });
    if (resposta.ok) return { ok: true, data: (await resposta.json()) as PrecoAtual };
    const corpo: unknown = await resposta.json().catch(() => null);
    return { ok: false, message: detalhe(corpo) ?? MSG_FALHA_NO_HISTORICO };
  } catch {
    return { ok: false, message: MSG_FALHA_NO_HISTORICO };
  }
}
