import { request, type ApiResult } from "@/lib/authApi";

// CU06 – Manter Favoritos. As mensagens dos fluxos vêm do backend; aqui ficam só os textos usados quando o backend não
// chegou a responder (rede fora do ar) e o aviso mostrado na tela de login depois do redirecionamento (C1-FA1).
export const MSG_FALHA_NOS_FAVORITOS = "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde"; // C1/C2-FE1
export const MSG_FALHA_NA_LISTA = "Não foi possível carregar os seus favoritos no momento. Tente novamente mais tarde"; // C3-FE1
export const MSG_ENTRE_PARA_FAVORITAR = "Entre na sua conta para favoritar itens"; // C1-FA1

/** C1-FA1: a tela de login, com o aviso do cenário. */
export const LOGIN_PARA_FAVORITAR = "/login?aviso=favoritar";

export interface EstadoDoFavorito {
  item_id: number;
  favorito: boolean;
  message: string | null; // nula no C1-FA2 (o item já estava nos favoritos)
}

export interface ItemFavorito {
  item_id: number;
  name: string;
  icon_url: string | null;
  market_value: number | null; // Cobre (RN01), RN06
  variacao_pct: number | null; // em relação ao dia anterior
  alertas_ativos: number;
  desatualizado: boolean; // C3-FA2
  aviso: string | null; // o selo do FA2, com o texto do cenário
}

export interface ListaDeFavoritos {
  itens: ItemFavorito[];
  mensagem: string | null; // C3-FA1
}

/** CU06-C1: adiciona o item aos favoritos. */
export const adicionarFavorito = (token: string, itemId: number | string): Promise<ApiResult<EstadoDoFavorito>> =>
  request<EstadoDoFavorito>(`/favorites/${encodeURIComponent(String(itemId))}`, { method: "POST", token, fallbackMessage: MSG_FALHA_NOS_FAVORITOS });

/** CU06-C2: remove o item; sem `confirmar` e com alertas do item, o backend responde 409 com o aviso do FA1. */
export const removerFavorito = (token: string, itemId: number | string, confirmar = false): Promise<ApiResult<EstadoDoFavorito>> =>
  request<EstadoDoFavorito>(`/favorites/${encodeURIComponent(String(itemId))}${confirmar ? "?confirmar=true" : ""}`, {
    method: "DELETE", token, fallbackMessage: MSG_FALHA_NOS_FAVORITOS,
  });

/** CU06-C3: a lista de favoritos. */
export const listarFavoritos = (token: string): Promise<ApiResult<ListaDeFavoritos>> =>
  request<ListaDeFavoritos>("/favorites", { token, fallbackMessage: MSG_FALHA_NA_LISTA });
