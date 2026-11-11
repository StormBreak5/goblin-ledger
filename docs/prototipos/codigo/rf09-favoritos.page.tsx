"use client";

import Link from "next/link";
import { Star, Trash2, Bell } from "lucide-react";
import Header from "@/components/Header";
import { formatarMoeda } from "@/lib/moeda";
import { FAVORITOS, icone } from "@/components/proto/dados";

/** CU06-C3 (protótipo): painel de acesso rápido com os itens favoritos do usuário. */
export default function FavoritosPage() {
  return (
    <div className="min-h-screen bg-[var(--color-background)] flex flex-col">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-3xl font-bold text-[var(--color-text-title)]">
              <Star className="h-7 w-7 fill-[var(--color-cta)] text-[var(--color-cta)]" aria-hidden="true" /> Meus favoritos
            </h1>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
              Itens que você acompanha. Selecione um item para ver o histórico, a projeção e os alertas de preço.
            </p>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)]">{FAVORITOS.length} itens</p>
        </div>
        <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-translucent)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
                <th className="px-4 py-3 font-medium">Item</th>
                <th className="px-4 py-3 text-right font-medium">Valor de mercado</th>
                <th className="px-4 py-3 text-right font-medium">Variação (dia anterior)</th>
                <th className="px-4 py-3 text-center font-medium">Alertas ativos</th>
                <th className="px-4 py-3 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {FAVORITOS.map((f) => (
                <tr key={f.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface-solid)]">
                  <td className="px-4 py-3">
                    <Link href={`/item/${f.id}`} className="flex items-center gap-3 text-[var(--color-text-title)]">
                      <img src={icone(f.icone)} alt="" className="h-10 w-10 rounded border border-[var(--color-border)]" />
                      <span className="font-medium">{f.nome}</span>
                      {f.desatualizado && (
                        <span className="rounded border border-[var(--color-cta)]/40 bg-[var(--color-cta)]/10 px-2 py-0.5 text-xs text-[var(--color-cta)]">
                          Dados Desatualizados
                        </span>
                      )}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-[var(--color-cta)]">{formatarMoeda(f.valor)}</td>
                  <td className={`px-4 py-3 text-right font-medium ${f.variacao >= 0 ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"}`}>
                    {f.variacao >= 0 ? "+" : "−"}{Math.abs(f.variacao).toLocaleString("pt-BR", { minimumFractionDigits: 1 })}%
                  </td>
                  <td className="px-4 py-3 text-center text-[var(--color-text-main)]">
                    {f.alertas > 0 ? (
                      <span className="inline-flex items-center gap-1"><Bell className="h-4 w-4 text-[var(--color-cta)]" aria-hidden="true" />{f.alertas}</span>
                    ) : (
                      <span className="text-[var(--color-text-secondary)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" className="inline-flex items-center gap-1 text-[var(--color-text-secondary)] hover:text-[var(--color-negative)]">
                      <Trash2 className="h-4 w-4" aria-hidden="true" /> Remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
