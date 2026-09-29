"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  carregarHistorico,
  carregarPrecoAtual,
  MSG_FALHA_NA_NOVA_JANELA,
  type HistoricoDoItem,
  type PrecoAtual,
} from "@/lib/historicoDoItem";

export const JANELA_INICIAL = "14D";

export interface EstadoDoHistorico {
  dados: HistoricoDoItem | null; // o que está na tela
  janela: string; // janela dos dados que estão na tela
  pendente: string | null; // janela pedida e ainda carregando
  carregando: boolean;
  erro: string | null; // C1-FE1: só quando nada chegou a ser exibido
  toast: string | null; // C2-FE1: falha ao trocar a janela, com a visualização anterior mantida
}

const ESTADO_INICIAL: EstadoDoHistorico = { dados: null, janela: JANELA_INICIAL, pendente: null, carregando: true, erro: null, toast: null };

/**
 * CU04-C1 / C2: carrega a série do item e troca a janela de tempo. A regra (recorte, frescor, avisos) é do backend.
 * Falha na primeira carga mostra a mensagem do C1-FE1; falha ao trocar a janela mantém o gráfico e a janela anteriores e
 * avisa com o toast do C2-FE1. Um pedido mais novo cancela o anterior.
 */
export function useHistoricoDoItem(id: string): EstadoDoHistorico & { mudarJanela: (nova: string) => void; fecharToast: () => void } {
  const [estado, setEstado] = useState<EstadoDoHistorico>(ESTADO_INICIAL);
  const controlador = useRef<AbortController | null>(null);

  const buscar = useCallback(
    async (janela: string) => {
      controlador.current?.abort();
      const controller = new AbortController();
      controlador.current = controller;
      setEstado((atual) => ({ ...atual, pendente: janela, carregando: true, erro: null }));
      const resultado = await carregarHistorico(id, janela, controller.signal);
      if (controller.signal.aborted) return;
      setEstado((atual) => {
        if (resultado.ok) return { ...atual, dados: resultado.data, janela, pendente: null, carregando: false, erro: null };
        if (atual.dados) return { ...atual, pendente: null, carregando: false, toast: MSG_FALHA_NA_NOVA_JANELA }; // C2-FE1
        return { ...atual, pendente: null, carregando: false, erro: resultado.message }; // C1-FE1
      });
    },
    [id],
  );

  useEffect(() => {
    const inicial = async () => {
      setEstado(ESTADO_INICIAL); // outro item: recomeça do zero
      await buscar(JANELA_INICIAL);
    };
    if (id) inicial();
    return () => controlador.current?.abort();
  }, [id, buscar]);

  const mudarJanela = useCallback(
    (nova: string) => {
      if (nova === (estado.pendente ?? estado.janela)) return; // já é a janela exibida (ou a que está sendo carregada)
      setEstado((atual) => ({ ...atual, toast: null }));
      buscar(nova);
    },
    [buscar, estado.janela, estado.pendente],
  );

  const fecharToast = useCallback(() => setEstado((atual) => ({ ...atual, toast: null })), []);

  return { ...estado, mudarJanela, fecharToast };
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
