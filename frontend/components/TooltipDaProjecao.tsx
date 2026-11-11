import TooltipDoPonto from "@/components/TooltipDoPonto";
import type { LinhaDoGrafico } from "@/lib/graficoDoItem";
import { descreverInstante } from "@/lib/instante";
import { formatarMoeda } from "@/lib/moeda";
import { formatarVariacao } from "@/lib/projecaoDoItem";

/**
 * CU05-C2 passo 4: a dica de um dia previsto, com a data e "dia inteiro", o preço previsto em Ouro/Prata/Cobre (RN01), a
 * variação sobre o preço diário do dia de referência e a indicação "Projeção". FE1: se o valor não puder ser convertido, a
 * dica daquele dia é omitida e a anomalia vai para o console, sem quebrar a tela.
 */
export function TooltipDaProjecao({ linha }: { linha: LinhaDoGrafico }) {
  let instante: { data: string; hora: string };
  let preco: string;
  let variacao: string;
  let base: string;
  try {
    instante = descreverInstante(linha.timestamp, "DIARIA");
    preco = formatarMoeda(linha.price);
    variacao = formatarVariacao(linha.variacao_pct ?? Number.NaN);
    base = formatarMoeda(linha.precoReferencia ?? Number.NaN);
  } catch (erro) {
    console.error("CU05-C2-FE1: dia previsto não pôde ser convertido; dica omitida.", erro, linha);
    return null;
  }

  const positiva = (linha.variacao_pct ?? 0) >= 0;
  return (
    <div data-testid="dica-projecao" className="bg-[var(--color-surface-solid)] border border-[var(--color-border)] p-3 rounded shadow-xl">
      <p className="text-xs font-bold tracking-wide text-[var(--color-projection)] mb-1">PROJEÇÃO</p>
      <p data-testid="dica-instante" className="text-[var(--color-text-title)] mb-2 font-medium">
        {instante.data} · {instante.hora}
      </p>
      <p data-testid="dica-preco" className="text-sm text-[var(--color-text-main)]">
        <span className="text-[var(--color-text-secondary)]">Preço previsto:</span>{" "}
        <span className="text-[var(--color-cta)]">{preco}</span>
      </p>
      <p data-testid="dica-variacao" className="text-sm text-[var(--color-text-main)] mt-1">
        <span className="text-[var(--color-text-secondary)]">Variação:</span>{" "}
        <span className={positiva ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"}>{variacao}</span> sobre {base}
      </p>
    </div>
  );
}

interface Props {
  // Injetados pelo Recharts ao clonar o elemento passado em <Tooltip content={...} />.
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: LinhaDoGrafico }>;
  serieTemVolume: boolean;
}

/**
 * Dica do gráfico do item: num dia previsto, a da projeção (CU05-C2); no histórico e no ponto de partida da projeção, que é
 * o último preço diário observado, a do histórico (CU04-C3; CU05-C2-FA1).
 */
export default function TooltipDoGrafico({ active, payload, serieTemVolume }: Props) {
  const linha = payload?.[0]?.payload;
  if (!active || !linha) return null;
  if (linha.tipo === "projecao") return <TooltipDaProjecao linha={linha} />;
  return <TooltipDoPonto active={active} payload={payload} serieTemVolume={serieTemVolume} />;
}
