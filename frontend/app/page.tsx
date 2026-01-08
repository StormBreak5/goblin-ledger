'use client';

import { AuctionItem } from "@/types/auction";
import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Coins, TrendingUp } from "lucide-react";

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
    <main className="min-h-screen p-8 max-w-7xl mx-auto">
      <header className="mb-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold text-emerald-500 mb-2 flex items-center gap-3">
            👺 Goblin Ledger
          </h1>
          <p className="text-slate-400 text-lg">
            Monitoramento de Mercado de WoW (Modo Dev)
          </p>
        </div>

        <Card className="bg-gradient-to-br from-amber-500/10 to-emerald-500/10 border-amber-500/20">
          <CardHeader className="pb-3">
            <CardDescription className="flex items-center gap-2 text-slate-300">
              <TrendingUp className="h-4 w-4" />
              Leilões Rastreados
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold text-amber-500">
                {auctions.length}
              </span>
              <span className="text-sm text-slate-400">itens</span>
            </div>
          </CardContent>
        </Card>
      </header>

      <Card className="shadow-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Coins className="h-5 w-5 text-emerald-500" />
            Leilões Ativos
          </CardTitle>
          <CardDescription>
            Visualize todos os leilões disponíveis no mercado
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
              <p className="mt-4 text-slate-400">Carregando leilões...</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[300px]">Item</TableHead>
                    <TableHead>Preço</TableHead>
                    <TableHead>Quantidade</TableHead>
                    <TableHead>Tempo Restante</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auctions.map((auction) => (
                    <TableRow key={auction.id}>
                      <TableCell className="font-medium">
                        <div>
                          <p className="font-semibold text-slate-100">
                            {auction.item.id_mock.replace(/_/g, " ").toUpperCase()}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            ID: {auction.item.id}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Coins className="h-4 w-4 text-amber-500" />
                          <span className="font-mono font-semibold text-emerald-400">
                            {(auction.buyout / 10000).toLocaleString('pt-BR', {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2
                            })}
                          </span>
                          <span className="text-xs text-slate-400">g</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="font-mono">
                          {auction.quantity} un
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={auction.time_left === 'SHORT' ? 'destructive' : 'default'}
                          className="font-semibold"
                        >
                          {auction.time_left}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}