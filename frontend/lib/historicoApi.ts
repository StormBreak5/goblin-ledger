import { request, type ApiResult } from "@/lib/authApi";

// CU10 – Cadastrar Dados Passados (Admin): importação do histórico de preços (C1), eventos de atualização do jogo (C2)
// e validação da cobertura histórica (C3). Os textos dos cenários vêm do backend; aqui ficam só os de "rede fora do ar".
export const MSG_FALHA_NA_IMPORTACAO = "Não foi possível concluir a importação no momento. Tente novamente mais tarde"; // CU10-C1-FE2

export type StatusImportacao = "EM_ANDAMENTO" | "CONCLUIDA" | "FALHA";

export interface ResumoImportacao {
  id_execucao: number;
  status: StatusImportacao;
  disparo: string | null;
  regiao: string | null;
  itens_solicitados: number | null;
  itens_processados: number;
  itens_cadastrados: number; // CU10-C1-FA2
  itens_sem_dados: number;
  itens_com_erro: number;
  registros_importados: number;
  registros_descartados: number;
  registros_duplicados: number;
  iniciada_em: string;
  concluida_em: string | null;
  etapa_da_falha: string | null; // FONTE (FE1), BANCO (FE2), FORMATO (FE3) ou INTERNA
  mensagem: string | null;
  erro: string | null;
}

/** CU10-C1 passo 1: região, reino conectado (opcional) e itens (vazio = todos os ativos). A validação é do backend (FA1). */
export const solicitarImportacao = (
  token: string,
  dados: { regiao: string; reino: string; itens: string[] },
): Promise<ApiResult<ResumoImportacao>> => {
  const corpo: Record<string, unknown> = { regiao: dados.regiao };
  if (dados.reino.trim() !== "") corpo.reino = /^\d+$/.test(dados.reino.trim()) ? Number(dados.reino.trim()) : dados.reino.trim();
  if (dados.itens.length > 0) corpo.itens = dados.itens.map((item) => (/^\d+$/.test(item) ? Number(item) : item));
  return request<ResumoImportacao>("/admin/history-import", { method: "POST", body: corpo, token, fallbackMessage: MSG_FALHA_NA_IMPORTACAO });
};

export const consultarImportacao = (token: string, id: number): Promise<ApiResult<ResumoImportacao>> =>
  request<ResumoImportacao>(`/admin/history-import/${id}`, { token, fallbackMessage: MSG_FALHA_NA_IMPORTACAO });

export const listarImportacoes = (token: string): Promise<ApiResult<ResumoImportacao[]>> =>
  request<ResumoImportacao[]>("/admin/history-import", { token, fallbackMessage: MSG_FALHA_NA_IMPORTACAO });

// ---------------------------------------------------------------- CU10-C2 – eventos de atualização do jogo

export const MSG_FALHA_NO_REGISTRO_DE_EVENTOS = "Não foi possível registrar os eventos no momento. Tente novamente mais tarde";

export type FonteDeEventos = "EXPANSOES" | "PATCHES" | "SAZONAIS" | "TEMPORADAS" | "RECORRENTES";
export type TipoDeEvento = "EXPANSAO" | "PATCH" | "TEMPORADA" | "EVENTO_SAZONAL" | "RECORRENTE" | "OUTRO";

export const FONTES_DE_EVENTOS: { valor: FonteDeEventos; rotulo: string; pagina: boolean }[] = [
  { valor: "EXPANSOES", rotulo: "Expansões (Wikipedia)", pagina: true },
  { valor: "PATCHES", rotulo: "Patches e pré-patches (Warcraft Wiki)", pagina: true },
  { valor: "TEMPORADAS", rotulo: "Temporadas de Mythic+ e PvP (API da Blizzard)", pagina: false },
  { valor: "SAZONAIS", rotulo: "Eventos sazonais (Warcraft Wiki)", pagina: true },
  { valor: "RECORRENTES", rotulo: "Recorrentes: reinício semanal, Feira de Negrilua e Posto de Troca", pagina: false },
];

export const TIPOS_DE_EVENTO: { valor: TipoDeEvento; rotulo: string }[] = [
  { valor: "EXPANSAO", rotulo: "Expansão" },
  { valor: "PATCH", rotulo: "Patch" },
  { valor: "TEMPORADA", rotulo: "Temporada" },
  { valor: "EVENTO_SAZONAL", rotulo: "Evento sazonal" },
  { valor: "RECORRENTE", rotulo: "Recorrente" },
  { valor: "OUTRO", rotulo: "Outro" },
];

export interface EventoJogo {
  id_evento: number;
  tipo: TipoDeEvento;
  nome: string;
  versao: string | null;
  data_inicio: string; // DD/MM/AAAA
  data_fim: string | null;
  regiao: string;
  origem: string;
  fonte: string | null;
}

export interface ResumoExtracao {
  fonte: string;
  eventos_encontrados: number;
  eventos_registrados: number;
  eventos_ignorados: number;
  eventos: EventoJogo[];
}

export interface ListaDeEventos {
  total: number;
  eventos: EventoJogo[];
}

/** CU10-C2 passos 1 e 2: extrai os eventos da fonte (e do endereço, nas páginas de referência) e registra os novos. */
export const extrairEventos = (token: string, fonte: FonteDeEventos, url: string): Promise<ApiResult<ResumoExtracao>> =>
  request<ResumoExtracao>("/admin/events/extract", {
    method: "POST",
    body: url.trim() === "" ? { fonte } : { fonte, url: url.trim() },
    token,
    fallbackMessage: MSG_FALHA_NO_REGISTRO_DE_EVENTOS,
  });

/** CU10-C2-FA2: cadastro manual (a data em DD/MM/AAAA). Os campos inválidos voltam em `fields`. */
export const cadastrarEvento = (
  token: string,
  dados: { nome: string; versao: string; tipo: string; data_inicio: string; data_fim: string; regiao: string },
): Promise<ApiResult<ResumoExtracao>> =>
  request<ResumoExtracao>("/admin/events", {
    method: "POST",
    body: { ...dados, versao: dados.versao.trim() === "" ? null : dados.versao, data_fim: dados.data_fim.trim() === "" ? null : dados.data_fim },
    token,
    fallbackMessage: MSG_FALHA_NO_REGISTRO_DE_EVENTOS,
  });

export const listarEventos = (token: string, tipo: string, deslocamento: number): Promise<ApiResult<ListaDeEventos>> =>
  request<ListaDeEventos>(
    `/admin/events?limite=100&deslocamento=${deslocamento}${tipo ? `&tipo=${encodeURIComponent(tipo)}` : ""}`,
    { token, fallbackMessage: MSG_FALHA_NO_REGISTRO_DE_EVENTOS },
  );
