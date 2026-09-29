import { describe, expect, it } from "vitest";
import { ConversaoDeMoedaError, formatarMoeda, partesDaMoeda } from "@/lib/moeda";

// RN01: 1 Prata = 100 Cobre; 1 Ouro = 10.000 Cobre. A conversão é só da exibição.
describe("moeda (RN01)", () => {
  it("test_moeda_converte_cobre_em_ouro_prata_e_cobre", () => {
    expect(partesDaMoeda(124_930)).toEqual({ ouro: 12, prata: 49, cobre: 30 });
    expect(formatarMoeda(124_930)).toBe("12g 49s 30c");
  });

  it("test_moeda_omite_as_partes_zeradas", () => {
    expect(formatarMoeda(120_000)).toBe("12g");
    expect(formatarMoeda(4_500)).toBe("45s");
    expect(formatarMoeda(10_005)).toBe("1g 5c");
    expect(formatarMoeda(7)).toBe("7c");
    expect(formatarMoeda(0)).toBe("0c");
  });

  it("test_moeda_separa_milhares_do_ouro", () => {
    expect(formatarMoeda(2_865_410_000)).toBe("286.541g");
    expect(formatarMoeda(1_234_567_891)).toBe("123.456g 78s 91c");
  });

  it("test_moeda_arredonda_fracao_de_cobre", () => {
    expect(formatarMoeda(99.6)).toBe("1s");
  });

  it("test_moeda_valor_atipico_levanta_erro_de_conversao", () => {
    for (const invalido of [NaN, Infinity, -1, "12" as unknown as number, null as unknown as number, undefined as unknown as number]) {
      expect(() => formatarMoeda(invalido)).toThrow(ConversaoDeMoedaError);
    }
  });
});
