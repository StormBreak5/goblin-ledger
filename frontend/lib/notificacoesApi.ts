import { request, type ApiResult } from "@/lib/authApi";

// CU08-C3 – Consultar notificações. As mensagens dos fluxos vêm do backend; aqui fica só o texto usado quando o backend não
// chegou a responder (rede fora do ar).
export const MSG_FALHA_NAS_NOTIFICACOES = "Não foi possível carregar as notificações no momento. Tente novamente mais tarde"; // FE1

export interface Notificacao {
  id_notificacao: number;
  item_id: number;
  name: string;
  icon_url: string | null;
  tipo: "COMPRA" | "VENDA";
  preco_alvo: number; // Cobre (RN01)
  valor_mercado: number; // Cobre (RN01): o valor de mercado que atingiu o alvo
  disparada_em: string; // UTC
  lida: boolean;
}

export interface ListaDeNotificacoes {
  notificacoes: Notificacao[]; // da mais recente para a mais antiga
  nao_lidas: number;
  mensagem: string | null; // FA1
}

export interface NaoLidas {
  nao_lidas: number;
}

/** Passo 1: o contador do sino. */
export const contarNaoLidas = (token: string): Promise<ApiResult<NaoLidas>> =>
  request<NaoLidas>("/notifications/unread-count", { token, fallbackMessage: MSG_FALHA_NAS_NOTIFICACOES });

/** Passos 3 e 4: as notificações da tela. Não marca nada como lido. */
export const listarNotificacoes = (token: string): Promise<ApiResult<ListaDeNotificacoes>> =>
  request<ListaDeNotificacoes>("/notifications", { token, fallbackMessage: MSG_FALHA_NAS_NOTIFICACOES });

/** Passo 5: marca as notificações exibidas como lidas e devolve o contador. */
export const marcarComoLidas = (token: string, ids: number[]): Promise<ApiResult<NaoLidas>> =>
  request<NaoLidas>("/notifications/read", { method: "POST", token, body: { ids }, fallbackMessage: MSG_FALHA_NAS_NOTIFICACOES });
