"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, useAuthToken } from "@/lib/auth";
import { adicionarFavorito, LOGIN_PARA_FAVORITAR, removerFavorito } from "@/lib/favoritosApi";

export interface AvisoDaTela {
  texto: string;
  tom: "erro" | "sucesso";
}

/**
 * CU06-C1 e C2 na tela: adicionar e remover um favorito, com as mensagens que vêm do backend.
 * - C1-FA1: sem sessão (ou com ela expirada), leva à tela de login com o aviso do cenário.
 * - C2-FA1: o backend responde 409 com o aviso dos alertas; a tela pede a confirmação e só então reenvia com `confirmar`.
 *   C2-FA2: cancelar fecha o diálogo e não envia nada.
 * - FE1: a mensagem do cenário num aviso passageiro, sem mudar o estado do item.
 */
export function useAcoesDeFavorito(aoMudar: (itemId: number, favorito: boolean) => void) {
  const token = useAuthToken();
  const router = useRouter();
  const [aviso, setAviso] = useState<AvisoDaTela | null>(null);
  const [confirmacao, setConfirmacao] = useState<{ itemId: number; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const adicionar = useCallback(async (itemId: number) => {
    if (!token) {
      router.push(LOGIN_PARA_FAVORITAR); // C1-FA1
      return;
    }
    setOcupado(true);
    const resultado = await adicionarFavorito(token, itemId);
    setOcupado(false);
    if (resultado.ok) {
      aoMudar(itemId, true);
      if (resultado.data.message) setAviso({ texto: resultado.data.message, tom: "sucesso" }); // FA2: sem mensagem
    } else if (resultado.status === 401) {
      clearToken();
      router.push(LOGIN_PARA_FAVORITAR);
    } else {
      setAviso({ texto: resultado.message, tom: "erro" }); // FE1
    }
  }, [token, router, aoMudar]);

  const remover = useCallback(async (itemId: number, confirmar = false) => {
    if (!token) {
      router.push("/login?aviso=sessao-expirada");
      return;
    }
    setOcupado(true);
    const resultado = await removerFavorito(token, itemId, confirmar);
    setOcupado(false);
    if (resultado.ok) {
      setConfirmacao(null);
      aoMudar(itemId, false);
      if (resultado.data.message) setAviso({ texto: resultado.data.message, tom: "sucesso" });
    } else if (resultado.status === 409) {
      setConfirmacao({ itemId, texto: resultado.message }); // FA1: o aviso dos alertas do item
    } else if (resultado.status === 401) {
      clearToken();
      router.replace("/login?aviso=sessao-expirada");
    } else {
      setConfirmacao(null);
      setAviso({ texto: resultado.message, tom: "erro" }); // FE1
    }
  }, [token, router, aoMudar]);

  const confirmar = useCallback(() => {
    if (confirmacao) remover(confirmacao.itemId, true); // FA1, passo 1.3
  }, [confirmacao, remover]);
  const cancelar = useCallback(() => setConfirmacao(null), []); // FA2
  const fecharAviso = useCallback(() => setAviso(null), []);

  return { adicionar, remover, confirmacao, confirmar, cancelar, aviso, fecharAviso, ocupado };
}
