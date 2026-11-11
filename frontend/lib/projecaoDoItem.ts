import { API_BASE_URL } from "@/lib/api";
import type { Consulta } from "@/lib/historicoDoItem";

// CU05 – Consultar Previsão Preditiva. A situação, as mensagens dos fluxos e os textos junto à projeção vêm do backend;
// aqui fica só o texto usado quando o backend não chegou a responder (rede fora do ar).
export const MSG_FALHA_NA_PROJECAO = "Não foi possível carregar a projeção no momento. Tente novamente mais tarde"; // C1-FE1

export type SituacaoDaProjecao =
  | "DISPONIVEL" // fluxo principal (e FA7, com `desatualizada`)
  | "MODELO_NAO_TREINADO" // FA1
  | "NAO_ELEGIVEL" // FA2
  | "REPROVADA" // FA3
  | "EM_AVALIACAO" // FA4
  | "SUSPENSA" // FA5
  | "NAO_DISPONIVEL"; // FA6

const SITUACOES: readonly string[] = [
  "DISPONIVEL", "MODELO_NAO_TREINADO", "NAO_ELEGIVEL", "REPROVADA", "EM_AVALIACAO", "SUSPENSA", "NAO_DISPONIVEL",
];

export interface PredicaoDoDia {
  data_prevista: string; // AAAA-MM-DD: o dia inteiro, em UTC
  preco_previsto: number; // Cobre (RN01)
  variacao_pct: number; // sobre o preço diário do dia de referência
}

export interface AvisoDaProjecao {
  codigo: "ORIGEM" | "ERRO_TIPICO" | "ESTIMATIVA" | "DESATUALIZADA";
  texto: string;
}

export interface ProjecaoDoItem {
  situacao: SituacaoDaProjecao;
  mensagem: string | null; // FA1 a FA6: exibida no lugar da projeção
  data_referencia: string | null; // D: o último preço diário, ponto de partida da linha
  preco_referencia: number | null; // Cobre
  erro_tipico_pct: number | null;
  desatualizada: boolean; // FA7
  predicoes: PredicaoDoDia[];
  avisos: AvisoDaProjecao[];
}

/** A projeção pronta para o gráfico e a tabela (C1 fluxo principal e FA7). */
export interface ProjecaoExibida {
  dataReferencia: string;
  precoReferencia: number;
  predicoes: PredicaoDoDia[];
}

function ehProjecao(corpo: unknown): corpo is ProjecaoDoItem {
  if (typeof corpo !== "object" || corpo === null) return false;
  const valor = corpo as Record<string, unknown>;
  return typeof valor.situacao === "string" && SITUACOES.includes(valor.situacao)
    && Array.isArray(valor.predicoes) && Array.isArray(valor.avisos);
}

function detalhe(corpo: unknown): string | null {
  if (typeof corpo === "object" && corpo !== null) {
    const valor = (corpo as Record<string, unknown>).detail;
    if (typeof valor === "string") return valor;
  }
  return null;
}

/** CU05-C1 passos 2 e 3: a situação da projeção do item e as predições a exibir (regras no backend). */
export async function carregarProjecao(id: string, signal?: AbortSignal): Promise<Consulta<ProjecaoDoItem>> {
  try {
    const resposta = await fetch(`${API_BASE_URL}/items/${encodeURIComponent(id)}/projection`, { signal });
    const corpo: unknown = await resposta.json().catch(() => null);
    if (resposta.ok && ehProjecao(corpo)) return { ok: true, data: corpo };
    return { ok: false, message: detalhe(corpo) ?? MSG_FALHA_NA_PROJECAO };
  } catch {
    return { ok: false, message: MSG_FALHA_NA_PROJECAO };
  }
}

/** A projeção pode ser desenhada: disponível, com o ponto de partida e ao menos um dia previsto. */
export function projecaoExibida(projecao: ProjecaoDoItem | null): ProjecaoExibida | null {
  if (!projecao || projecao.situacao !== "DISPONIVEL") return null;
  if (projecao.data_referencia === null || projecao.preco_referencia === null || projecao.predicoes.length === 0) return null;
  return { dataReferencia: projecao.data_referencia, precoReferencia: projecao.preco_referencia, predicoes: projecao.predicoes };
}

/** Instante (00:00 UTC) de um dia AAAA-MM-DD: o ponto diário é o dia inteiro em UTC, como no histórico (RN16). */
export function instanteDoDia(dia: string): string {
  return `${dia}T00:00:00Z`;
}

/** Variação já calculada pelo backend, só formatada: `+3,5%`, `-1,2%`, `0,0%`. */
export function formatarVariacao(pct: number): string {
  if (!Number.isFinite(pct)) throw new RangeError(`Variação inválida: ${pct}`);
  const texto = pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${pct > 0 ? "+" : ""}${texto}%`;
}

/** DD/MM/AAAA de um dia AAAA-MM-DD (sem passar pelo fuso de quem vê). */
export function formatarDia(dia: string, comAno = true): string {
  const [ano, mes, d] = dia.split("-");
  return comAno ? `${d}/${mes}/${ano}` : `${d}/${mes}`;
}
