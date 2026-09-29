// RN01: todo valor monetário é guardado em Cobre (1 Prata = 100 Cobre; 1 Ouro = 10.000 Cobre). A conversão para Ouro, Prata e
// Cobre acontece só na exibição, aqui.
const COBRE_POR_PRATA = 100;
const COBRE_POR_OURO = 10_000;

/** CU04-C3-FE1: o valor não pôde ser convertido (não é número, não é finito ou é negativo). */
export class ConversaoDeMoedaError extends Error {
  constructor(valor: unknown) {
    super(`Valor monetário atípico, não convertido para Ouro/Prata/Cobre: ${String(valor)}`);
    this.name = "ConversaoDeMoedaError";
  }
}

/** Separa um valor em Cobre em ouro, prata e cobre. Frações de cobre são arredondadas. */
export function partesDaMoeda(cobre: number): { ouro: number; prata: number; cobre: number } {
  if (typeof cobre !== "number" || !Number.isFinite(cobre) || cobre < 0) throw new ConversaoDeMoedaError(cobre);
  const total = Math.round(cobre);
  return {
    ouro: Math.floor(total / COBRE_POR_OURO),
    prata: Math.floor((total % COBRE_POR_OURO) / COBRE_POR_PRATA),
    cobre: total % COBRE_POR_PRATA,
  };
}

/** Valor em Cobre no formato do jogo, sem as partes zeradas: `12g 49s 30c`, `286.541g`, `45s`, `0c`. */
export function formatarMoeda(cobre: number): string {
  const { ouro, prata, cobre: restante } = partesDaMoeda(cobre);
  const partes: string[] = [];
  if (ouro > 0) partes.push(`${ouro.toLocaleString("pt-BR")}g`);
  if (prata > 0) partes.push(`${prata}s`);
  if (restante > 0) partes.push(`${restante}c`);
  return partes.length > 0 ? partes.join(" ") : "0c";
}
