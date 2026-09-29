"use client";

import Image from "next/image";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, HelpCircle } from "lucide-react";
import AuthNav from "@/components/AuthNav";
import ItemSearchResults from "@/components/ItemSearchResults";
import { MSG_ITEM_INDISPONIVEL, searchItems, type SearchResult } from "@/lib/itemSearch";

const SEARCH_MAX_LENGTH = 100; // RF02: termo de busca de até 100 caracteres

function parsePage(value: string | null): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // O estado da busca vive na URL (/?q=...&page=n) para que "voltar" da tela de detalhes reencontre a lista.
  const submittedQuery = searchParams.get("q");
  const page = parsePage(searchParams.get("page"));
  const itemUnavailable = searchParams.get("aviso") === "item-indisponivel"; // CU03-C3-FE1

  const [inputValue, setInputValue] = useState(submittedQuery ?? "");
  const [previousQuery, setPreviousQuery] = useState(submittedQuery);
  const [attempt, setAttempt] = useState(0);
  const [response, setResponse] = useState<{ key: string; result: SearchResult } | null>(null);

  // Mantém a barra de pesquisa alinhada à URL quando ela muda por navegação (ex.: voltar).
  if (submittedQuery !== previousQuery) {
    setPreviousQuery(submittedQuery);
    setInputValue(submittedQuery ?? "");
  }

  const requestKey = submittedQuery === null ? null : `${attempt}:${page}:${submittedQuery}`;

  useEffect(() => {
    if (requestKey === null || submittedQuery === null) return;
    const controller = new AbortController();
    searchItems(submittedQuery, page, controller.signal).then((result) => {
      if (!controller.signal.aborted) setResponse({ key: requestKey, result });
    });
    return () => controller.abort();
  }, [requestKey, submittedQuery, page]);

  const isLoading = requestKey !== null && response?.key !== requestKey;
  const result = requestKey !== null && response?.key === requestKey ? response.result : null;
  const hasSearch = submittedQuery !== null;

  const goToPage = (nextPage: number) => {
    router.push(`/?${new URLSearchParams({ q: submittedQuery ?? "", page: String(nextPage) }).toString()}`);
  };

  // CU03-C1 / C2: a busca é feita ao confirmar. A validação do termo (FA1) é do backend.
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue === submittedQuery && page === 1) {
      setAttempt((current) => current + 1); // repete a mesma busca (ex.: após uma falha)
      return;
    }
    router.push(`/?${new URLSearchParams({ q: inputValue, page: "1" }).toString()}`);
  };

  return (
    <div
      className={`relative min-h-screen w-full overflow-hidden bg-[var(--color-background)] flex flex-col items-center ${
        hasSearch ? "justify-start pt-12 pb-24" : "justify-center"
      }`}
    >
      {/* Background Image */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/Background_goblin_ledger.png"
          alt="Background"
          fill
          className="object-cover opacity-80"
        />
        {/* Gradient overlay to ensure text readability */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#161124]/40 via-[#161124]/20 to-[#161124]/90" />
      </div>

      {/* CU01/CU02: acesso à conta */}
      <div className="absolute right-6 top-6 z-20 flex items-center gap-4 text-sm">
        <AuthNav />
      </div>

      {/* Main Content */}
      <main className="relative z-10 flex w-full max-w-3xl flex-col items-center justify-center px-6">
        <div className="mb-6 flex flex-col items-center">
          <div className={`relative mb-2 ${hasSearch ? "h-20 w-20" : "h-32 w-32"}`}>
            <Image
              src="/logo.png"
              alt="Goblin Ledger Logo"
              fill
              className="object-contain"
              priority
            />
          </div>
          <h1 className="text-3xl font-bold tracking-[0.2em] text-[var(--color-text-title)]">
            GOBLIN LEDGER
          </h1>
          <div className="mt-4 flex items-center justify-center gap-4">
            <div className="h-px w-12 bg-gradient-to-r from-transparent to-[var(--color-cta)]" />
            <p className="text-sm font-medium italic text-[var(--color-text-secondary)]">
              Inteligência de Mercado e Previsão de Preços para o seu MMO
            </p>
            <div className="h-px w-12 bg-gradient-to-l from-transparent to-[var(--color-cta)]" />
          </div>
        </div>

        {itemUnavailable && (
          <div
            role="alert"
            className="mt-4 w-full max-w-2xl rounded-lg border border-[var(--color-negative)]/50 bg-[var(--color-surface-solid)]/90 p-4 text-center text-sm text-[var(--color-negative)]"
          >
            {MSG_ITEM_INDISPONIVEL}
          </div>
        )}

        {/* Search Form */}
        <form
          onSubmit={handleSearch}
          className="mt-8 flex w-full max-w-2xl flex-col shadow-2xl rounded-lg border border-[var(--color-border)] relative"
        >
          <div className="flex flex-col sm:flex-row w-full bg-[#1A1525]/90 backdrop-blur-md rounded-lg overflow-hidden">
            <div className="relative flex-grow">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
                <Search className="h-5 w-5 text-[var(--color-text-secondary)]" />
              </div>
              <input
                type="text"
                name="q"
                aria-label="Termo de busca"
                value={inputValue}
                maxLength={SEARCH_MAX_LENGTH}
                onChange={(e) => setInputValue(e.target.value)}
                className="block w-full border-none bg-transparent py-4 pl-12 pr-4 text-base text-[var(--color-text-main)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-0"
                placeholder="Nome do item ou ID (ex: Flask of Supreme Power, 7972)..."
              />
            </div>
            <button
              type="submit"
              className="flex items-center justify-center bg-[var(--color-cta)] px-8 py-4 font-bold text-[#161124] transition-colors hover:bg-[var(--color-cta-hover)] sm:w-auto"
            >
              PESQUISAR
            </button>
          </div>
        </form>

        {hasSearch && (
          <div className="mt-4 w-full max-w-2xl">
            <ItemSearchResults isLoading={isLoading} result={result} onPageChange={goToPage} />
          </div>
        )}
      </main>

      {/* Footer Text */}
      <footer className="absolute bottom-6 z-10 text-center text-xs text-[var(--color-text-secondary)]/60">
        <p>Goblin Ledger • 2026</p>
      </footer>

      {/* Help Button */}
      <button className="absolute bottom-6 right-6 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-surface-solid)] border border-[var(--color-border)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-translucent)] hover:text-[var(--color-text-main)]">
        <HelpCircle className="h-5 w-5" />
      </button>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
