"use client";

import { useEffect } from "react";

/**
 * Aviso passageiro: some sozinho depois de alguns segundos ou ao ser fechado. O tom "erro" é o do CU04-C2-FE1; o
 * "sucesso" é o das confirmações dos CU06 e CU07 ("Item adicionado aos favoritos", "Alerta criado com sucesso"...).
 */
export default function Toast({ texto, onFechar, duracaoMs = 6000, tom = "erro" }: {
  texto: string;
  onFechar: () => void;
  duracaoMs?: number;
  tom?: "erro" | "sucesso";
}) {
  useEffect(() => {
    const temporizador = setTimeout(onFechar, duracaoMs);
    return () => clearTimeout(temporizador);
  }, [texto, onFechar, duracaoMs]);

  const borda = tom === "sucesso" ? "border-[var(--color-positive)]/60" : "border-[var(--color-negative)]/60";
  return (
    <div
      role="status"
      data-tom={tom}
      className={`fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-3 rounded-lg border ${borda} bg-[var(--color-surface-solid)] px-4 py-3 text-sm text-[var(--color-text-main)] shadow-xl`}
    >
      <span>{texto}</span>
      <button type="button" onClick={onFechar} aria-label="Fechar aviso" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]">
        ×
      </button>
    </div>
  );
}
