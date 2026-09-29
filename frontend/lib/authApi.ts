import { API_BASE_URL } from "@/lib/api";

// Textos dos cenários (CU01/CU02) que o cliente precisa exibir por conta própria: quando o backend não chegou a
// responder (rede fora do ar) e as mensagens de aviso mostradas após um redirecionamento.
export const MSG_FALHA_NO_CADASTRO = "Não foi possível concluir o cadastro no momento. Tente novamente mais tarde";
export const MSG_FALHA_NO_LOGIN = "Não foi possível realizar o login no momento. Tente novamente mais tarde";
export const MSG_FALHA_NA_RECUPERACAO = "Não foi possível processar a solicitação no momento. Tente novamente mais tarde";
export const MSG_FALHA_NA_REDEFINICAO = "Não foi possível redefinir a senha no momento. Tente novamente mais tarde";
export const MSG_FALHA_NA_ATUALIZACAO = "Não foi possível atualizar os dados no momento. Tente novamente mais tarde";
export const MSG_FALHA_NA_EXCLUSAO = "Não foi possível excluir a conta no momento. Tente novamente mais tarde";
export const MSG_LINK_INVALIDO = "Link de recuperação inválido ou expirado. Solicite uma nova recuperação de senha";
export const MSG_CONTA_CRIADA = "Conta criada com sucesso"; // CU01-C1 passo 8
export const MSG_SENHA_REDEFINIDA = "Senha redefinida com sucesso"; // CU02-C3 passo 8
export const MSG_SESSAO_EXPIRADA = "Sua sessão expirou. Faça login novamente"; // CU02-C4-FA1

export type Regiao = "US" | "EU";

export interface Perfil {
  email: string;
  regiao: Regiao;
  role: string;
}

export interface Sessao {
  access_token: string;
  token_type: string;
  expires_at: string;
  usuario: Perfil;
}

export interface Mensagem {
  message: string;
}

export interface ApiFailure {
  ok: false;
  status: number;
  message: string;
  fields: string[]; // campos a destacar (CU01-C1-FA1 / CU02-C1-FA1)
}

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: Record<string, unknown>;
  token?: string | null;
  fallbackMessage: string;
}

function parseDetail(payload: unknown, fallbackMessage: string): { message: string; fields: string[] } {
  if (typeof payload === "object" && payload !== null) {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string") return { message: detail, fields: [] };
    if (typeof detail === "object" && detail !== null) {
      const { message, fields } = detail as Record<string, unknown>;
      if (typeof message === "string") {
        return { message, fields: Array.isArray(fields) ? fields.filter((f): f is string => typeof f === "string") : [] };
      }
    }
  }
  return { message: fallbackMessage, fields: [] };
}

export async function request<T>(path: string, { method = "GET", body, token, fallbackMessage }: RequestOptions): Promise<ApiResult<T>> {
  try {
    const headers: Record<string, string> = {};
    if (body) headers["Content-Type"] = "application/json";
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (response.ok) {
      const data = response.status === 204 ? undefined : await response.json();
      return { ok: true, data: data as T };
    }
    const payload: unknown = await response.json().catch(() => null);
    return { ok: false, status: response.status, ...parseDetail(payload, fallbackMessage) };
  } catch {
    return { ok: false, status: 0, message: fallbackMessage, fields: [] };
  }
}

// ---------------------------------------------------------------- CU01 – Manter Usuário

export const cadastrar = (dados: { email: string; senha: string; confirmacao_senha: string; regiao: string }) =>
  request<Mensagem>("/users", { method: "POST", body: dados, fallbackMessage: MSG_FALHA_NO_CADASTRO });

export const carregarPerfil = (token: string) =>
  request<Perfil>("/users/me", { token, fallbackMessage: MSG_FALHA_NA_ATUALIZACAO });

export const alterarDados = (
  token: string,
  dados: { regiao: string; senha_atual: string; nova_senha: string; confirmacao_nova_senha: string },
) => request<Mensagem>("/users/me", { method: "PUT", body: dados, token, fallbackMessage: MSG_FALHA_NA_ATUALIZACAO });

export const excluirConta = (token: string, senha: string) =>
  request<void>("/users/me", { method: "DELETE", body: { senha }, token, fallbackMessage: MSG_FALHA_NA_EXCLUSAO });

// ---------------------------------------------------------------- CU02 – Realizar Login

export const entrar = (dados: { email: string; senha: string }) =>
  request<Sessao>("/auth/login", { method: "POST", body: dados, fallbackMessage: MSG_FALHA_NO_LOGIN });

export const sair = (token: string) =>
  request<void>("/auth/logout", { method: "POST", token, fallbackMessage: MSG_FALHA_NO_LOGIN });

export const pedirRecuperacao = (email: string) =>
  request<Mensagem>("/auth/password-recovery", { method: "POST", body: { email }, fallbackMessage: MSG_FALHA_NA_RECUPERACAO });

export const validarLinkDeRedefinicao = (token: string) =>
  request<void>("/auth/password-reset/validate", { method: "POST", body: { token }, fallbackMessage: MSG_FALHA_NA_REDEFINICAO });

export const redefinirSenha = (dados: { token: string; nova_senha: string; confirmacao_nova_senha: string }) =>
  request<Mensagem>("/auth/password-reset", { method: "POST", body: dados, fallbackMessage: MSG_FALHA_NA_REDEFINICAO });
