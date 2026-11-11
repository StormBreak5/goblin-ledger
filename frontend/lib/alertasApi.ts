import { request, type ApiResult, type Mensagem } from "@/lib/authApi";

// CU07 – Manter Alerta. As mensagens dos fluxos (inclusive a do FA3) vêm do backend; aqui ficam só os textos usados
// quando o backend não chegou a responder (rede fora do ar) e os rótulos da tela.
export const MSG_FALHA_AO_SALVAR = "Não foi possível salvar o alerta no momento. Tente novamente mais tarde"; // C1/C2-FE1
export const MSG_FALHA_AO_EXCLUIR = "Não foi possível excluir o alerta no momento. Tente novamente mais tarde"; // C3-FE1
export const MSG_FALHA_AO_CARREGAR = "Não foi possível carregar os alertas no momento. Tente novamente mais tarde";
export const MSG_CONFIRMAR_EXCLUSAO = "Deseja excluir este alerta?"; // C3 passo 2

export type TipoDeAlerta = "COMPRA" | "VENDA";
export type CanalDeAlerta = "WEB" | "EMAIL" | "AMBOS";

export const ROTULO_DO_TIPO: Record<TipoDeAlerta, { nome: string; descricao: string; gatilho: string }> = {
  COMPRA: { nome: "Compra", descricao: "Avisar quando o preço cair até o alvo", gatilho: "preço cair até o alvo" },
  VENDA: { nome: "Venda", descricao: "Avisar quando o preço subir até o alvo", gatilho: "preço subir até o alvo" },
};
export const ROTULO_DO_CANAL: Record<CanalDeAlerta, string> = { WEB: "Tela", EMAIL: "E-mail", AMBOS: "Tela e e-mail" };
export const OPCOES_DE_CANAL: { valor: CanalDeAlerta; rotulo: string }[] = [
  { valor: "WEB", rotulo: "Tela" }, { valor: "EMAIL", rotulo: "E-mail" }, { valor: "AMBOS", rotulo: "Ambos" },
];

export interface Alerta {
  id_alerta: number;
  item_id: number;
  tipo: TipoDeAlerta;
  preco_alvo: number; // Cobre (RN01)
  canal: CanalDeAlerta;
  situacao: "ATIVO" | "DISPARADO";
  disparado_em: string | null;
}

export interface AlertasDoItem {
  alertas: Alerta[];
  ativos_do_usuario: number; // RN08, em todos os itens
  limite: number;
}

export interface FormularioDoAlerta {
  item_id: number;
  market_value: number | null; // RN06, em Cobre
  alerta: Alerta | null; // C2: os dados atuais
}

export interface AlertaSalvo {
  alerta: Alerta;
  message: string;
}

/** O que o usuário informa no formulário (C1 passo 5 / C2 passo 3). A validação e a conversão para Cobre são do backend. */
export interface DadosDoAlerta {
  tipo: TipoDeAlerta | null;
  canal: CanalDeAlerta | null;
  ouro: string;
  prata: string;
  cobre: string;
}

const parte = (valor: string): number | string | null => {
  const texto = valor.trim();
  if (texto === "") return null;
  return /^\d+$/.test(texto) ? Number(texto) : texto; // o backend responde com o FA3 ao que não for inteiro
};

const corpo = (dados: DadosDoAlerta): Record<string, unknown> => ({
  tipo: dados.tipo, canal: dados.canal, ouro: parte(dados.ouro), prata: parte(dados.prata), cobre: parte(dados.cobre),
});

export const listarAlertas = (token: string, itemId: number): Promise<ApiResult<AlertasDoItem>> =>
  request<AlertasDoItem>(`/items/${itemId}/alerts`, { token, fallbackMessage: MSG_FALHA_AO_CARREGAR });

/** C1 passos 2 a 4: 409 com o FA1 ou o FA2; senão, o valor de mercado atual como referência. */
export const novoAlerta = (token: string, itemId: number): Promise<ApiResult<FormularioDoAlerta>> =>
  request<FormularioDoAlerta>(`/items/${itemId}/alerts/new`, { token, fallbackMessage: MSG_FALHA_AO_CARREGAR });

export const criarAlerta = (token: string, itemId: number, dados: DadosDoAlerta): Promise<ApiResult<AlertaSalvo>> =>
  request<AlertaSalvo>(`/items/${itemId}/alerts`, { method: "POST", body: corpo(dados), token, fallbackMessage: MSG_FALHA_AO_SALVAR });

/** C2 passos 1 e 2: os dados atuais; o disparado só abre para reativar abaixo da cota (409 com o FA2). */
export const alertaParaEditar = (token: string, idAlerta: number): Promise<ApiResult<FormularioDoAlerta>> =>
  request<FormularioDoAlerta>(`/alerts/${idAlerta}/edit`, { token, fallbackMessage: MSG_FALHA_AO_CARREGAR });

export const alterarAlerta = (token: string, idAlerta: number, dados: DadosDoAlerta): Promise<ApiResult<AlertaSalvo>> =>
  request<AlertaSalvo>(`/alerts/${idAlerta}`, { method: "PUT", body: corpo(dados), token, fallbackMessage: MSG_FALHA_AO_SALVAR });

export const excluirAlerta = (token: string, idAlerta: number): Promise<ApiResult<Mensagem>> =>
  request<Mensagem>(`/alerts/${idAlerta}`, { method: "DELETE", token, fallbackMessage: MSG_FALHA_AO_EXCLUIR });
