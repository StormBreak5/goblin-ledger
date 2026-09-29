"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/Header";
import PriceChart from "@/components/PriceChart";
import { fetchItem, type ItemDetail } from "@/lib/itemSearch";

interface HistoricalDataPoint {
  timestamp: string;
  price: number;
  quantity: number;
  granularity?: "DIARIA" | "HORARIA";
}

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

  const [data, setData] = useState<HistoricalDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [windowPeriod, setWindowPeriod] = useState("14D");
  const [currentAuctions, setCurrentAuctions] = useState<{min_price: number, total_quantity: number} | null>(null);
  const [loadingCurrent, setLoadingCurrent] = useState(false);

  useEffect(() => {
    // Busca dados reais da API do Backend Python (FastAPI que será configurado na porta 8000)
    const fetchHistory = async () => {
      try {
        setLoading(true);
        // Exemplo: o backend local rodará na porta 8000
        const response = await fetch(`http://127.0.0.1:8000/api/items/${id}/history?window=${windowPeriod}`);
        
        if (!response.ok) {
          throw new Error("Falha ao carregar histórico do item.");
        }
        
        const historyData = await response.json();
        setData(historyData);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    const fetchCurrentAuctions = async () => {
      try {
        setLoadingCurrent(true);
        const response = await fetch(`http://127.0.0.1:8000/api/items/${id}/current-auctions`);
        if (response.ok) {
          const data = await response.json();
          if (data.min_price > 0 || data.total_quantity > 0) {
            setCurrentAuctions(data);
          }
        }
      } catch (err) {
        console.error("Erro ao buscar leilões atuais", err);
      } finally {
        setLoadingCurrent(false);
      }
    };

    if (id) {
      fetchHistory();
      fetchCurrentAuctions();
    }
  }, [id, windowPeriod]);

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

          <div className="text-right">
            {loadingCurrent ? (
              <p className="text-[var(--color-text-secondary)] text-sm animate-pulse">Consultando Casa de Leilões...</p>
            ) : currentAuctions ? (
              <>
                <p className="text-[var(--color-text-secondary)] font-medium mb-1">
                  {currentAuctions.total_quantity.toLocaleString('pt-BR')} leilões ativos
                </p>
                <p className="text-2xl font-bold text-[var(--color-cta)]">
                  {(currentAuctions.min_price / 10000).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ouro
                </p>
              </>
            ) : null}
          </div>
        </div>

        <div className="flex justify-end gap-2 mb-4">
          {[
            { value: '14D', label: '14 Dias' },
            { value: '30D', label: '1 Mês' },
            { value: '90D', label: '3 Meses' },
            { value: '365D', label: '1 Ano' },
            { value: 'ALL', label: 'Tudo' }
          ].map(w => (
            <button
              key={w.value}
              onClick={() => setWindowPeriod(w.value)}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                windowPeriod === w.value 
                  ? 'bg-[var(--color-cta)] text-[#161124] font-bold' 
                  : 'bg-[var(--color-surface-solid)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)] border border-[var(--color-border)]'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>

        <div className="h-[500px] w-full">
          {loading ? (
            <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)]">
              <div className="animate-pulse flex flex-col items-center">
                <div className="h-8 w-8 rounded-full border-4 border-[var(--color-cta)] border-t-transparent animate-spin mb-4"></div>
                <p className="text-[var(--color-text-secondary)]">Carregando dados da Auction House...</p>
              </div>
            </div>
          ) : error ? (
            <div className="w-full h-full flex flex-col items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-negative)]/50 p-6 text-center">
              <p className="text-[var(--color-negative)] font-medium mb-2">Erro de Conexão</p>
              <p className="text-[var(--color-text-secondary)] text-sm">{error}</p>
              <p className="text-[var(--color-text-secondary)] text-xs mt-4">Verifique se o servidor do Backend (FastAPI) está rodando na porta 8000.</p>
            </div>
          ) : (
            <PriceChart data={data} />
          )}
        </div>
      </main>
    </div>
  );
}
