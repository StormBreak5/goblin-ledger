"use client";

import { useEffect } from "react";

/** Aviso passageiro (CU04-C2-FE1): some sozinho depois de alguns segundos ou ao ser fechado. */
export default function Toast({ texto, onFechar, duracaoMs = 6000 }: { texto: string; onFechar: () => void; duracaoMs?: number }) {
  useEffect(() => {
    const temporizador = setTimeout(onFechar, duracaoMs);
    return () => clearTimeout(temporizador);
  }, [texto, onFechar, duracaoMs]);

  return (
    <div
      role="status"
      className="fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-3 rounded-lg border border-[var(--color-negative)]/60 bg-[var(--color-surface-solid)] px-4 py-3 text-sm text-[var(--color-text-main)] shadow-xl"
    >
      <span>{texto}</span>
      <button type="button" onClick={onFechar} aria-label="Fechar aviso" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]">
        ×
      </button>
    </div>
  );
}
