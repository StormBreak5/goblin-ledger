"use client";

import { Star } from "lucide-react";

/** CU06: o controle abaixo do nome do item (Figura 15). "Favoritar" inicia o C1; "Favoritado", o C2. */
export default function ControleDeFavorito({ favorito, ocupado, aoAlternar }: {
  favorito: boolean;
  ocupado: boolean;
  aoAlternar: () => void;
}) {
  return (
    <button
      type="button"
      onClick={aoAlternar}
      disabled={ocupado}
      aria-pressed={favorito}
      className={`mt-2 inline-flex items-center gap-1.5 rounded-md border px-3 py-1 text-sm font-medium transition-colors disabled:opacity-60 ${
        favorito
          ? "border-[var(--color-cta)]/70 bg-[var(--color-cta)]/10 text-[var(--color-cta)]"
          : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]"
      }`}
    >
      <Star aria-hidden className={`h-4 w-4 ${favorito ? "fill-[var(--color-cta)]" : ""}`} />
      {favorito ? "Favoritado" : "Favoritar"}
    </button>
  );
}
