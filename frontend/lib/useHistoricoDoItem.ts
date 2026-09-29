"use client";

import { useEffect, useState } from "react";
import {
  carregarHistorico,
  carregarPrecoAtual,
  type HistoricoDoItem,
  type PrecoAtual,
} from "@/lib/historicoDoItem";

interface EstadoDoHistorico {
  dados: HistoricoDoItem | null;
  carregando: boolean;
  erro: string | null; // C1-FE1: mensagem do cenário quando o histórico não pôde ser carregado
}

/** CU04-C1: carrega a série do item na janela pedida. A regra (frescor, avisos) é do backend. */
export function useHistoricoDoItem(id: string, janela: string): EstadoDoHistorico {
  const [estado, setEstado] = useState<EstadoDoHistorico>({ dados: null, carregando: true, erro: null });

  useEffect(() => {
    const controller = new AbortController();
    const buscar = async () => {
      setEstado({ dados: null, carregando: true, erro: null });
      const resultado = await carregarHistorico(id, janela, controller.signal);
      if (controller.signal.aborted) return;
      setEstado(resultado.ok ? { dados: resultado.data, carregando: false, erro: null } : { dados: null, carregando: false, erro: resultado.message });
    };
    if (id) buscar();
    return () => controller.abort();
  }, [id, janela]);

  return estado;
}

/** CU04-C1 passo 3: menor preço e valor de mercado atuais do item (nulos enquanto carrega ou se não houver leilões). */
export function usePrecoAtual(id: string): { preco: PrecoAtual | null; carregando: boolean } {
  const [estado, setEstado] = useState<{ preco: PrecoAtual | null; carregando: boolean }>({ preco: null, carregando: true });

  useEffect(() => {
    const controller = new AbortController();
    const buscar = async () => {
      const resultado = await carregarPrecoAtual(id, controller.signal);
      if (controller.signal.aborted) return;
      const comLeiloes = resultado.ok && (resultado.data.min_price > 0 || (resultado.data.total_quantity ?? 0) > 0);
      setEstado({ preco: resultado.ok && comLeiloes ? resultado.data : null, carregando: false });
    };
    if (id) buscar();
    return () => controller.abort();
  }, [id]);

  return estado;
}
