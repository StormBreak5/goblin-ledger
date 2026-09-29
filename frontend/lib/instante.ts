import type { Granularidade } from "@/lib/historicoDoItem";

/**
 * CU04-C3 passo 3: data e hora exata de um ponto. O ponto horário é um instante e aparece no fuso de quem vê (GMT-3 no
 * Brasil). O ponto diário é o dia inteiro em UTC (00:00 UTC): convertido para GMT-3 cairia no dia anterior às 21:00, então
 * mostra a data em UTC e "dia inteiro". Levanta erro se o instante não for uma data válida (CU04-C3-FE1).
 */
export function descreverInstante(timestamp: string, granularidade?: Granularidade): { data: string; hora: string } {
  const instante = new Date(timestamp);
  if (Number.isNaN(instante.getTime())) throw new RangeError(`Instante inválido: ${timestamp}`);
  const diario = granularidade === "DIARIA";
  const data = instante.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", ...(diario ? { timeZone: "UTC" } : {}) });
  const hora = diario ? "dia inteiro" : instante.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
  return { data, hora };
}
