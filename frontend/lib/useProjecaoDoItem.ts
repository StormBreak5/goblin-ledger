"use client";

import { useCallback, useEffect, useState } from "react";
import { carregarProjecao, type ProjecaoDoItem } from "@/lib/projecaoDoItem";

export interface EstadoDaProjecao {
  projecao: ProjecaoDoItem | null;
  carregando: boolean;
  erro: string | null; // C1-FE1
}

/**
 * CU05-C1: carrega a projeção do item uma vez por item. Ela não depende da janela de tempo do histórico (CU04-C2): ao
 * trocar a janela, continua presa ao fim do histórico.
 */
export function useProjecaoDoItem(id: string): EstadoDaProjecao {
  const [estado, setEstado] = useState<EstadoDaProjecao>({ projecao: null, carregando: true, erro: null });

  useEffect(() => {
    const controller = new AbortController();
    const buscar = async () => {
      const resultado = await carregarProjecao(id, controller.signal);
      if (controller.signal.aborted) return;
      setEstado(resultado.ok
        ? { projecao: resultado.data, carregando: false, erro: null }
        : { projecao: null, carregando: false, erro: resultado.message });
    };
    if (id) buscar();
    return () => controller.abort();
  }, [id]);

  return estado;
}

// CU05-C3 passo 4: a escolha vale enquanto o usuário navega pelas telas de itens, na mesma sessão do navegador.
const CHAVE_DA_ESCOLHA = "goblin-ledger:projecao-visivel";

/** Sem a escolha gravada (ou sem acesso ao sessionStorage), a projeção aparece. */
export function lerProjecaoVisivel(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.sessionStorage.getItem(CHAVE_DA_ESCOLHA) !== "false";
  } catch {
    return true;
  }
}

function gravarProjecaoVisivel(visivel: boolean): void {
  try {
    window.sessionStorage.setItem(CHAVE_DA_ESCOLHA, String(visivel));
  } catch {
    // Navegador sem sessionStorage (modo privado restrito): a escolha vale só nesta tela.
  }
}

/** CU05-C3: o controle "Projeção" oculta ou volta a exibir a linha e a tabela da projeção. */
export function useProjecaoVisivel(): [boolean, () => void] {
  const [visivel, setVisivel] = useState<boolean>(lerProjecaoVisivel);
  const alternar = useCallback(() => {
    gravarProjecaoVisivel(!visivel);
    setVisivel(!visivel);
  }, [visivel]);
  return [visivel, alternar];
}
