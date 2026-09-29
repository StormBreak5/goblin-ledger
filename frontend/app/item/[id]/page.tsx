"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import AvisosDoHistorico from "@/components/AvisosDoHistorico";
import Header from "@/components/Header";
import PrecoAtualDoItem from "@/components/PrecoAtualDoItem";
import PriceChart from "@/components/PriceChart";
import { fetchItem, type ItemDetail } from "@/lib/itemSearch";
import { useHistoricoDoItem, usePrecoAtual } from "@/lib/useHistoricoDoItem";

const JANELAS = [
  { value: "14D", label: "14 Dias" },
  { value: "30D", label: "1 Mês" },
  { value: "90D", label: "3 Meses" },
  { value: "365D", label: "1 Ano" },
  { value: "ALL", label: "Tudo" },
];

export default function ItemDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // CU03-C3: nome e ícone vêm do backend; item removido durante a navegação volta para a busca (C3-FE1).
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);
  const itemName = item?.name ?? `Item ${id}`;
  const iconUrl = item?.icon_url ?? null;

  useEffect(() => {
    const controller = new AbortController();
    fetchItem(id, controller.signal).then((lookup) => {
      if (controller.signal.aborted) return;
      if (lookup.status === "found") {
        setItem(lookup.item);
      } else if (lookup.status === "unavailable") {
        router.replace("/?aviso=item-indisponivel");
      } else {
        setItemError(lookup.message);
      }
    });
    return () => controller.abort();
  }, [id, router]);

  // CU04: a série, os avisos (Dados Desatualizados / sem histórico) e o preço atual vêm do backend.
  const [janela, setJanela] = useState("14D");
  const { dados, carregando, erro } = useHistoricoDoItem(id, janela);
  const { preco, carregando: carregandoPreco } = usePrecoAtual(id);
  const semHistorico = dados?.avisos.find((aviso) => aviso.codigo === "SEM_HISTORICO");

  return (
    <div className="min-h-screen bg-[var(--color-background)] flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {iconUrl && (
              <img src={iconUrl} alt={itemName} className="w-16 h-16 rounded-lg border border-[var(--color-border)] shadow-md" />
            )}
            <div>
              <h1 className="text-3xl font-bold text-[var(--color-text-title)] capitalize">
                {itemName}
              </h1>
              {itemError && (
                <p role="alert" className="mt-1 text-sm text-[var(--color-negative)]">{itemError}</p>
              )}
            </div>
          </div>

          {carregandoPreco ? (
            <p className="text-[var(--color-text-secondary)] text-sm animate-pulse">Consultando Casa de Leilões...</p>
          ) : preco ? (
            <PrecoAtualDoItem preco={preco} />
          ) : null}
        </div>

        <div className="flex justify-end gap-2 mb-4">
          {JANELAS.map((w) => (
            <button
              key={w.value}
              onClick={() => setJanela(w.value)}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                janela === w.value
                  ? 'bg-[var(--color-cta)] text-[#161124] font-bold'
                  : 'bg-[var(--color-surface-solid)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)] border border-[var(--color-border)]'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>

        {dados && <AvisosDoHistorico avisos={dados.avisos} />}

        <div className="h-[500px] w-full">
          {carregando ? (
            <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)]">
              <div className="animate-pulse flex flex-col items-center">
                <div className="h-8 w-8 rounded-full border-4 border-[var(--color-cta)] border-t-transparent animate-spin mb-4"></div>
                <p className="text-[var(--color-text-secondary)]">Carregando dados da Auction House...</p>
              </div>
            </div>
          ) : erro ? (
            <div role="alert" className="w-full h-full flex flex-col items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-negative)]/50 p-6 text-center">
              <p className="text-[var(--color-negative)] font-medium">{erro}</p>
            </div>
          ) : (
            <PriceChart data={dados?.pontos ?? []} mensagemVazia={semHistorico?.texto} />
          )}
        </div>
      </main>
    </div>
  );
}
