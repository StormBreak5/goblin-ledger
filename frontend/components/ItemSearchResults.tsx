"use client";

import Image from "next/image";
import Link from "next/link";
import { Package } from "lucide-react";
import type { SearchResult } from "@/lib/itemSearch";

interface ItemSearchResultsProps {
  isLoading: boolean;
  result: SearchResult | null;
  onPageChange: (page: number) => void;
}

const panelClass =
  "rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-solid)]/90 backdrop-blur-md shadow-xl";

export default function ItemSearchResults({ isLoading, result, onPageChange }: ItemSearchResultsProps) {
  if (isLoading) {
    return (
      <div role="status" className={`${panelClass} p-4 text-center text-sm text-[var(--color-text-secondary)]`}>
        Buscando...
      </div>
    );
  }

  if (!result) return null;

  // CU03-C1-FA1 / C1-FE1 / C2-FE1: o texto vem pronto do backend (ou do cliente, se a API não respondeu).
  if (!result.ok) {
    return (
      <div role="alert" className={`${panelClass} border-[var(--color-negative)]/50 p-4 text-center text-sm text-[var(--color-negative)]`}>
        {result.message}
      </div>
    );
  }

  const { data } = result;

  // CU03-C1-FA2 / C2-FA1: nenhum item localizado.
  if (data.items.length === 0 && data.message) {
    return (
      <div role="status" className={`${panelClass} p-4 text-center text-sm text-[var(--color-text-secondary)]`}>
        {data.message}
      </div>
    );
  }

  return (
    <section aria-label="Itens encontrados" className={`${panelClass} overflow-hidden`}>
      <ul>
        {data.items.map((item) => (
          <li key={item.id} className="border-b border-[var(--color-border)] last:border-0">
            {/* CU03-C3: o clique no nome ou no ícone abre a tela de detalhes do item. */}
            <Link
              href={`/item/${item.id}`}
              className="flex items-center gap-3 px-4 py-3 text-[var(--color-text-main)] transition-colors hover:bg-[var(--color-surface-translucent)]"
            >
              {item.icon_url ? (
                <Image
                  unoptimized
                  src={item.icon_url}
                  alt=""
                  width={40}
                  height={40}
                  className="h-10 w-10 rounded border border-[var(--color-border)]"
                />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded border border-[var(--color-border)] text-[var(--color-text-secondary)]">
                  <Package className="h-5 w-5" aria-hidden="true" />
                </div>
              )}
              <span>{item.name}</span>
            </Link>
          </li>
        ))}
      </ul>

      {data.total_pages > 1 && (
        <nav
          aria-label="Paginação dos resultados"
          className="flex items-center justify-between gap-4 border-t border-[var(--color-border)] px-4 py-3 text-sm"
        >
          <button
            type="button"
            onClick={() => onPageChange(Math.min(data.page - 1, data.total_pages))}
            disabled={data.page <= 1}
            className="rounded border border-[var(--color-border)] px-3 py-1 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-main)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Anterior
          </button>
          <span className="text-[var(--color-text-secondary)]">
            Página {data.page} de {data.total_pages}
          </span>
          <button
            type="button"
            onClick={() => onPageChange(data.page + 1)}
            disabled={data.page >= data.total_pages}
            className="rounded border border-[var(--color-border)] px-3 py-1 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-main)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Próxima
          </button>
        </nav>
      )}
    </section>
  );
}
