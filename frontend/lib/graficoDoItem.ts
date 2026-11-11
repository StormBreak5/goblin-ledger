import type { PontoDoHistorico } from "@/lib/historicoDoItem";
import { instanteDoDia, type ProjecaoExibida } from "@/lib/projecaoDoItem";

/**
 * Uma linha dos dados do gráfico do item: um ponto do histórico (CU04), o ponto de partida da projeção ou um dia previsto
 * (CU05). Os pontos do histórico carregam `goldPrice` (linha do histórico) e os da projeção, `projecaoGold` (linha
 * tracejada); `price` continua em Cobre para as dicas (RN01).
 */
export interface LinhaDoGrafico extends PontoDoHistorico {
  ts: number;
  tipo: "historico" | "partida" | "projecao";
  goldPrice?: number;
  projecaoGold?: number;
  dia?: string; // dia previsto (AAAA-MM-DD), só na projeção
  variacao_pct?: number; // só na projeção
  precoReferencia?: number; // preço diário de D, em Cobre: a base da variação
}

const emOuro = (cobre: number) => cobre / 10000; // só a escala do gráfico

/**
 * CU04-C1 e CU05-C1 passo 5: o histórico e, se houver, a projeção. A linha da projeção começa no preço diário do dia de
 * referência (D), marcado no ponto diário de D do histórico ou acrescentado, e segue pelos dias previstos (00:00 UTC, o dia
 * inteiro). Sem projeção (ou com ela oculta, CU05-C3), são só os pontos do histórico: o eixo do tempo e a escala voltam a
 * considerar somente o histórico.
 */
export function montarDadosDoGrafico(pontos: PontoDoHistorico[], projecao: ProjecaoExibida | null): LinhaDoGrafico[] {
  const linhas: LinhaDoGrafico[] = pontos.map((ponto) => ({
    ...ponto,
    ts: new Date(ponto.timestamp).getTime(),
    tipo: "historico",
    goldPrice: emOuro(ponto.price),
  }));
  if (!projecao) return linhas;

  const tsDaPartida = new Date(instanteDoDia(projecao.dataReferencia)).getTime();
  const partida = linhas.find((linha) => linha.ts === tsDaPartida && linha.granularity === "DIARIA");
  if (partida) {
    partida.tipo = "partida";
    partida.projecaoGold = emOuro(projecao.precoReferencia);
  } else {
    linhas.push({
      timestamp: instanteDoDia(projecao.dataReferencia), price: projecao.precoReferencia, quantity: null, granularity: "DIARIA",
      ts: tsDaPartida, tipo: "partida", projecaoGold: emOuro(projecao.precoReferencia),
    });
  }
  for (const predicao of projecao.predicoes) {
    linhas.push({
      timestamp: instanteDoDia(predicao.data_prevista), price: predicao.preco_previsto, quantity: null, granularity: "DIARIA",
      ts: new Date(instanteDoDia(predicao.data_prevista)).getTime(), tipo: "projecao", projecaoGold: emOuro(predicao.preco_previsto),
      dia: predicao.data_prevista, variacao_pct: predicao.variacao_pct, precoReferencia: projecao.precoReferencia,
    });
  }
  return linhas.sort((a, b) => a.ts - b.ts);
}

/** O intervalo do eixo do tempo (do primeiro ao último ponto desenhado). */
export function dominioDoTempo(linhas: LinhaDoGrafico[]): [number, number] | null {
  if (linhas.length === 0) return null;
  return [linhas[0].ts, linhas[linhas.length - 1].ts];
}
