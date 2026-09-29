import type { AvisoDoHistorico } from "@/lib/historicoDoItem";

/**
 * CU04: avisos do histórico, com o texto exato do cenário vindo do backend. "Dados Desatualizados" (C1-FA1) e
 * "Dados limitados..." (C2-FA1) aparecem acima do gráfico; a ausência de histórico (C1-FA2) ocupa o lugar do gráfico.
 */
export default function AvisosDoHistorico({ avisos }: { avisos: AvisoDoHistorico[] }) {
  const visiveis = avisos.filter((aviso) => aviso.codigo !== "SEM_HISTORICO");
  if (visiveis.length === 0) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-2" role="status">
      {visiveis.map((aviso) => (
        <span
          key={aviso.codigo}
          data-codigo={aviso.codigo}
          className="rounded-md border border-[var(--color-cta)]/60 bg-[var(--color-cta)]/10 px-3 py-1 text-sm font-medium text-[var(--color-cta)]"
        >
          {aviso.texto}
        </span>
      ))}
    </div>
  );
}
