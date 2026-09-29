import { request, type ApiResult } from "@/lib/authApi";

// CU09-C4 (ingestão manual pelo Admin) e RN09/RN14 (frescor dos dados de cada mercado).
export const MSG_FALHA_NA_INGESTAO_MANUAL = "Não foi possível executar a ingestão no momento. Tente novamente mais tarde";
export const MSG_ACESSO_RESTRITO_AO_ADMIN = "Acesso restrito ao administrador";

export interface ResultadoMercado {
  mercado: string;
  status: "SUCESSO" | "FALHA" | "CANCELADO";
  leiloes_coletados: number;
  leiloes_descartados: number;
  itens_atualizados: number;
  itens_anomalos: number;
  itens_cadastrados: number;
  proxima_permitida: string | null; // CU09-C4-FA1
  etapa_da_falha: string | null; // CU09-C4-FE1
  erro: string | null;
}

export interface ResumoIngestao {
  mercados: ResultadoMercado[];
  leiloes_coletados: number;
  leiloes_descartados: number;
  itens_atualizados: number;
}

export interface EstadoMercado {
  mercado: string;
  ultima_atualizacao_em: string | null;
  desatualizado: boolean;
  ultima_falha_em: string | null;
}

export const executarIngestao = (token: string, regiao: string, reino: number | null): Promise<ApiResult<ResumoIngestao>> =>
  request<ResumoIngestao>("/admin/ingestion", {
    method: "POST",
    body: reino === null ? { regiao } : { regiao, reino },
    token,
    fallbackMessage: MSG_FALHA_NA_INGESTAO_MANUAL,
  });

export const carregarEstadoDosMercados = (): Promise<ApiResult<EstadoMercado[]>> =>
  request<EstadoMercado[]>("/market/status", { fallbackMessage: MSG_FALHA_NA_INGESTAO_MANUAL });
