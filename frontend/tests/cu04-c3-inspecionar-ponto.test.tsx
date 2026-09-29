import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TooltipDoPonto from "@/components/TooltipDoPonto";
import type { PontoDoHistorico } from "@/lib/historicoDoItem";
import { descreverInstante } from "@/lib/instante";

// O fuso dos testes é o de Brasília (GMT-3): vitest.setup.ts.

function ponto(alteracoes: Partial<PontoDoHistorico> = {}): PontoDoHistorico {
  return { timestamp: "2026-09-28T09:30:00Z", price: 124_930, quantity: 8, granularity: "HORARIA", ...alteracoes };
}

function dica(pontoFocado: PontoDoHistorico, serieTemVolume = true) {
  return render(<TooltipDoPonto active payload={[{ payload: pontoFocado }]} serieTemVolume={serieTemVolume} />);
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("CU04-C3 – Inspecionar detalhes de um ponto temporal", () => {
  it("test_cu04_c3_fluxo_principal_dica_com_data_hora_e_valores_em_cobre_prata_ouro", () => {
    dica(ponto());

    expect(screen.getByTestId("dica-instante")).toHaveTextContent("28/09/2026 06:30"); // passo 3: 09:30 UTC = 06:30 em GMT-3
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 12g 49s 30c"); // RN01
    expect(screen.getByTestId("dica-volume")).toHaveTextContent("Volume: 8");
  });

  it("test_cu04_c3_fluxo_principal_o_ponto_diario_e_o_dia_inteiro_em_utc", () => {
    dica(ponto({ timestamp: "2026-09-28T00:00:00Z", granularity: "DIARIA" }));

    // Em GMT-3 seria 27/09 às 21:00: o ponto diário é o dia 28 inteiro.
    expect(screen.getByTestId("dica-instante")).toHaveTextContent("28/09/2026 dia inteiro");
  });

  it("test_cu04_c3_fluxo_principal_valores_grandes_e_pequenos", () => {
    const { unmount } = dica(ponto({ price: 2_865_410_000 }));
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 286.541g");
    unmount();
    dica(ponto({ price: 45 }));
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 45c");
  });

  it("test_cu04_c3_fa1_metrica_ausente_vira_nd_e_o_preco_continua", () => {
    dica(ponto({ quantity: null }));

    expect(screen.getByTestId("dica-volume")).toHaveTextContent("Volume: N/D"); // 1.3
    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 12g 49s 30c");
  });

  it("test_cu04_c3_fa1_volume_zero_nao_e_confundido_com_ausente", () => {
    dica(ponto({ quantity: 0 }));

    expect(screen.getByTestId("dica-volume")).toHaveTextContent("Volume: 0");
  });

  it("test_cu04_c3_fa1_serie_sem_volume_como_a_ficha_do_wow_nao_mostra_a_linha", () => {
    dica(ponto({ quantity: null }), false);

    expect(screen.queryByTestId("dica-volume")).not.toBeInTheDocument();
    expect(screen.getByTestId("dica-preco")).toBeInTheDocument();
  });

  it("test_cu04_c3_fe1_valor_atipico_omite_a_dica_e_registra_no_console", () => {
    for (const price of [Number.NaN, Number.POSITIVE_INFINITY, -1, "abc" as unknown as number]) {
      const { container, unmount } = dica(ponto({ price }));

      expect(container).toBeEmptyDOMElement(); // 1.2: a dica daquele ponto não aparece
      expect(console.error).toHaveBeenLastCalledWith(expect.stringContaining("CU04-C3-FE1"), expect.any(Error), expect.anything()); // 1.3
      unmount();
    }
  });

  it("test_cu04_c3_fe1_instante_invalido_tambem_omite_a_dica", () => {
    const { container } = dica(ponto({ timestamp: "não é uma data" }));

    expect(container).toBeEmptyDOMElement();
    expect(console.error).toHaveBeenCalledTimes(1);
  });

  it("test_cu04_c3_fe1_o_usuario_pode_inspecionar_outro_ponto_normalmente", () => {
    const { container, rerender } = dica(ponto({ price: -5 }));
    expect(container).toBeEmptyDOMElement();

    rerender(<TooltipDoPonto active payload={[{ payload: ponto() }]} serieTemVolume />); // 1.3: "outro ponto"

    expect(screen.getByTestId("dica-preco")).toHaveTextContent("Preço: 12g 49s 30c");
  });

  it("test_cu04_c3_sem_mouse_sobre_o_grafico_nao_ha_dica", () => {
    const { container, rerender } = render(<TooltipDoPonto active={false} payload={[{ payload: ponto() }]} serieTemVolume />);
    expect(container).toBeEmptyDOMElement();

    rerender(<TooltipDoPonto active payload={[]} serieTemVolume />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("descreverInstante (fuso de exibição)", () => {
  it("test_instante_horario_no_fuso_de_brasilia_e_diario_em_utc", () => {
    expect(descreverInstante("2026-09-28T09:30:00Z", "HORARIA").hora).toMatch(/^06:30/);
    expect(descreverInstante("2026-01-01T02:00:00Z", "HORARIA").data).toBe("31/12/2025"); // vira o dia em GMT-3
    expect(descreverInstante("2026-01-01T00:00:00Z", "DIARIA")).toEqual({ data: "01/01/2026", hora: "dia inteiro" });
  });
});
