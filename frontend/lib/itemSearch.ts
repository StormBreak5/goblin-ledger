const API_BASE_URL = "http://127.0.0.1:8000/api";

// Textos dos cenários do CU03 usados quando o backend não chega a responder (rede fora do ar, resposta ilegível).
// Nos demais casos, o texto exibido é o devolvido pelo backend.
export const MSG_FALHA_NA_BUSCA = "Não foi possível realizar a busca no momento. Tente novamente mais tarde"; // C1-FE1 / C2-FE1
export const MSG_ITEM_INDISPONIVEL = "Item indisponível. Realize uma nova busca"; // C3-FE1

export interface ItemSummary {
  id: number;
  name: string;
  icon_url: string | null;
  last_auction_update: string | null;
}

export interface ItemSearchResponse {
  items: ItemSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  search_type: "name" | "id";
  message: string | null;
}

export interface ItemDetail {
  id: number;
  name: string;
  icon_url: string | null;
}

export type SearchResult = { ok: true; data: ItemSearchResponse } | { ok: false; message: string };

export type ItemLookupResult =
  | { status: "found"; item: ItemDetail }
  | { status: "unavailable" }
  | { status: "error"; message: string };

function extractDetail(body: unknown): string | null {
  if (typeof body === "object" && body !== null) {
    const detail = (body as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

async function readDetail(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  return extractDetail(body) ?? MSG_FALHA_NA_BUSCA;
}

/** CU03-C1 / CU03-C2: busca por nome ou identificador. A validação do termo é do backend. */
export async function searchItems(term: string, page: number, signal?: AbortSignal): Promise<SearchResult> {
  try {
    const params = new URLSearchParams({ q: term, page: String(page) });
    const response = await fetch(`${API_BASE_URL}/items/search?${params.toString()}`, { signal });
    if (response.ok) {
      return { ok: true, data: (await response.json()) as ItemSearchResponse };
    }
    return { ok: false, message: await readDetail(response) };
  } catch {
    return { ok: false, message: MSG_FALHA_NA_BUSCA };
  }
}

/** CU03-C3: confirma que o item selecionado ainda existe e devolve nome e ícone. */
export async function fetchItem(itemId: string, signal?: AbortSignal): Promise<ItemLookupResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/items/${encodeURIComponent(itemId)}`, { signal });
    if (response.ok) {
      return { status: "found", item: (await response.json()) as ItemDetail };
    }
    if (response.status === 404 || response.status === 422) {
      return { status: "unavailable" };
    }
    return { status: "error", message: await readDetail(response) };
  } catch {
    return { status: "error", message: MSG_FALHA_NA_BUSCA };
  }
}
