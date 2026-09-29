import { descreverInstante } from "@/lib/instante";
import type { PontoDoHistorico } from "@/lib/historicoDoItem";
import { formatarMoeda } from "@/lib/moeda";

interface Props {
  // Injetados pelo Recharts ao clonar o elemento passado em <Tooltip content={...} />.
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: PontoDoHistorico }>;
  /** A série tem volume em algum ponto: um ponto sem volume mostra "N/D". Sem volume em nenhum (Ficha do WoW), a linha não aparece. */
  serieTemVolume: boolean;
}

/**
 * CU04-C3: dica do ponto sob o mouse, com data, hora exata e os valores em Ouro/Prata/Cobre (RN01).
 * FA1: métrica ausente vira "N/D". FE1: se o valor não puder ser convertido, a dica daquele ponto é omitida e a anomalia vai
 * para o console, sem quebrar a tela.
 */
export default function TooltipDoPonto({ active, payload, serieTemVolume }: Props) {
  const ponto = payload?.[0]?.payload;
  if (!active || !ponto) return null;

  let instante: { data: string; hora: string };
  let preco: string;
  try {
    instante = descreverInstante(ponto.timestamp, ponto.granularity);
    preco = formatarMoeda(ponto.price);
  } catch (erro) {
    console.error("CU04-C3-FE1: ponto do histórico não pôde ser convertido; dica omitida.", erro, ponto);
    return null;
  }

  const volume = ponto.quantity === null || ponto.quantity === undefined ? "N/D" : ponto.quantity.toLocaleString("pt-BR");
  return (
    <div className="bg-[var(--color-surface-solid)] border border-[var(--color-border)] p-3 rounded shadow-xl">
      <p data-testid="dica-instante" className="text-[var(--color-text-title)] mb-2 font-medium">
        {instante.data} {instante.hora}
      </p>
      <p data-testid="dica-preco" className="text-[var(--color-cta)] text-sm">
        <span className="text-[var(--color-text-secondary)]">Preço:</span> {preco}
      </p>
      {serieTemVolume && (
        <p data-testid="dica-volume" className="text-[var(--color-text-main)] text-sm mt-1">
          <span className="text-[var(--color-text-secondary)]">Volume:</span> {volume}
        </p>
      )}
    </div>
  );
}
