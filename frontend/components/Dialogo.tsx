"use client";

import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  titulo: string;
  children: ReactNode;
  /** Sem `aoConfirmar`, o diálogo só tem o conteúdo (o formulário do alerta traz os próprios botões). */
  aoConfirmar?: () => void;
  aoCancelar: () => void;
  textoConfirmar?: string;
  textoCancelar?: string;
  ocupado?: boolean;
  largura?: string;
}

/**
 * Diálogo modal dos CU06 e CU07: a confirmação da remoção do favorito com alertas (CU06-C2-FA1), a da exclusão do alerta
 * (CU07-C3 passo 2) e o formulário do alerta (CU07-C1/C2). Esc e o fundo cancelam; o foco vai para o diálogo.
 */
export default function Dialogo({
  titulo, children, aoConfirmar, aoCancelar, textoConfirmar = "Confirmar", textoCancelar = "Cancelar", ocupado = false,
  largura = "max-w-md",
}: Props) {
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    caixa.current?.focus();
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") aoCancelar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aoCancelar]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4" onClick={aoCancelar}>
      <div
        ref={caixa}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        onClick={(evento) => evento.stopPropagation()}
        className={`w-full ${largura} rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-solid)] p-6 shadow-2xl outline-none`}
      >
        <h2 className="mb-4 text-lg font-bold text-[var(--color-text-title)]">{titulo}</h2>
        {children}
        {aoConfirmar && (
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={aoCancelar} disabled={ocupado}
              className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-main)] hover:bg-white/5">
              {textoCancelar}
            </button>
            <button type="button" onClick={aoConfirmar} disabled={ocupado}
              className="rounded-md bg-[var(--color-cta)] px-4 py-2 text-sm font-semibold text-[#161124] hover:bg-[var(--color-cta-hover)] disabled:opacity-60">
              {textoConfirmar}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
