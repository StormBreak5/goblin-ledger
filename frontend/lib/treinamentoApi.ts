import { request, type ApiResult } from "@/lib/authApi";

// CU11 – Treinar Modelo (Admin), Cenário 01: treinamento inicial do modelo preditivo global. O pedido entra numa fila e é
// executado pelo serviço `modelo`; a tela acompanha o andamento. Os textos dos cenários vêm do backend; aqui fica só o
// de "rede fora do ar".
export const MSG_FALHA_NO_TREINAMENTO = "Não foi possível concluir o treinamento no momento. Tente novamente mais tarde"; // CU11-C1-FE2

export type StatusTreinamento = "AGUARDANDO" | "EXECUTANDO" | "SUCESSO" | "FALHA";

export interface ModeloTreinado {
  versao: number;
  treinado_em: string;
  vigente: boolean;
  data_inicio: string; // AAAA-MM-DD
  corte_validacao: string;
  corte_teste: string;
  data_fim: string;
  itens_avaliados: number;
  amostras_treino: number;
  amostras_validacao: number;
  amostras_teste: number;
  epocas: number;
  melhor_epoca: number;
  segundos_por_epoca: number;
  duracao_segundos: number;
  mediana_mdape: number | null; // fração (0,2062 = 20,62%)
  mediana_mdape_ingenuo: number | null;
  mediana_mape: number | null;
  mediana_mape_ingenuo: number | null;
  itens_supera_ingenuo: number | null;
}

export interface ResumoTreinamento {
  id_execucao: number;
  tipo: string; // INICIAL (C1) ou RETREINAMENTO (C2)
  disparo: string;
  regiao: string;
  status: StatusTreinamento;
  solicitado_em: string;
  iniciado_em: string | null;
  concluido_em: string | null;
  andamento: string | null;
  itens_elegiveis: number | null;
  itens_treino: number | null;
  itens_liberados: number | null;
  itens_bloqueados: number | null;
  bloqueados_acima_do_limiar: number | null;
  bloqueados_nao_supera_ingenuo: number | null;
  bloqueados_avaliacao_insuficiente: number | null; // CU11-C1-FA5
  itens_ignorados: number | null; // CU11-C1-FA3
  liberados_fora_do_treino: number | null;
  avisos: string | null;
  etapa_da_falha: string | null; // SELECAO (FA1), TREINO (FE1), BANCO (FE2) ou INTERNA
  mensagem: string | null;
  erro: string | null;
  modelo: ModeloTreinado | null;
}

export const emAndamento = (resumo: ResumoTreinamento | null): boolean =>
  resumo !== null && (resumo.status === "AGUARDANDO" || resumo.status === "EXECUTANDO");

/** CU11-C1 passo 1: o Admin solicita o treinamento inicial, informando a região. FA2 volta como erro 409. */
export const solicitarTreinamento = (token: string, regiao: string): Promise<ApiResult<ResumoTreinamento>> =>
  request<ResumoTreinamento>("/admin/model-training", {
    method: "POST",
    body: { regiao },
    token,
    fallbackMessage: MSG_FALHA_NO_TREINAMENTO,
  });

export const consultarTreinamento = (token: string, id: number): Promise<ApiResult<ResumoTreinamento>> =>
  request<ResumoTreinamento>(`/admin/model-training/${id}`, { token, fallbackMessage: MSG_FALHA_NO_TREINAMENTO });

export const listarTreinamentos = (token: string): Promise<ApiResult<ResumoTreinamento[]>> =>
  request<ResumoTreinamento[]>("/admin/model-training", { token, fallbackMessage: MSG_FALHA_NO_TREINAMENTO });
