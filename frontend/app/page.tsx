'use client';

import { AuctionItem } from "@/types/auction";
import { useEffect, useState } from "react";

export default function Home() {
  const [auctions, setAuctions] = useState<AuctionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch('http://localhost:8000/api/auctions');
        const data = await response.json();
        setAuctions(data);
      } catch (error) {
        console.error('Erro ao buscar dados:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-emerald-500 mb-2">
            👺 Goblin Ledger
          </h1>
          <p className="text-slate-400">
            Monitoramento de Mercado de WoW (Modo Dev)
          </p>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-amber-500 font-bold text-xl">
            {auctions.length}
          </span>
          <span className="text-sm text-slate-400 ml-2">Leilões Rastreados</span>
        </div>
      </header>

      <section className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700 shadow-xl">
        {loading ? (
          <div className="p-8 text-center text-slate-400 animate-pulse">
            Carregando...
          </div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-slate-900 text-slate-400 uppercase text-xs font-semibold">
              <tr>
                <th className="py-2 px-4">Item (ID Mock)</th>
                <th className="py-2 px-4">Preço (Gold)</th>
                <th className="py-2 px-4">Quantidade</th>
                <th className="py-2 px-4">Tempo Restante</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {auctions.map((auction) => (
                <tr key={auction.id} className="hover:bg-slate-700/50 transition-colors">
                  <td className="p-4 font-medium text-slate-200">
                    {auction.item.id_mock.replace(/_/g, " ").toUpperCase()}
                    <span className="block text-xs text-slate-500">ID: {auction.item.id}</span>
                  </td>
                  <td className="p-4 text-emerald-400 font-mono">
                    {(auction.buyout / 10000).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} g
                  </td>
                  <td className="p-4 text-slate-300">
                    {auction.quantity} un
                  </td>
                  <td className="p4">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${auction.time_left === 'SHORT' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>
                      {auction.time_left}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}