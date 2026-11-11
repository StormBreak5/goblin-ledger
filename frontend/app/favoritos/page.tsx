"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Star, Trash2 } from "lucide-react";
import Dialogo from "@/components/Dialogo";
import Header from "@/components/Header";
import Toast from "@/components/Toast";
import { clearToken, useAuthReady, useAuthToken } from "@/lib/auth";
import { listarFavoritos, type ItemFavorito, type ListaDeFavoritos } from "@/lib/favoritosApi";
import { formatarMoeda } from "@/lib/moeda";
import { formatarVariacao } from "@/lib/projecaoDoItem";
import { useAcoesDeFavorito } from "@/lib/useAcoesDeFavorito";

interface Estado {
  lista: ListaDeFavoritos | null;
  carregando: boolean;
  erro: string | null; // C3-FE1
}

function valor(cobre: number | null): string {
  if (cobre === null) return "—";
  try {
    return formatarMoeda(cobre);
  } catch {
    return "—";
  }
}

function Variacao({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-[var(--color-text-secondary)]">—</span>;
  const cor = pct > 0 ? "text-[var(--color-positive)]" : pct < 0 ? "text-[var(--color-negative)]" : "text-[var(--color-text-main)]";
  return <span className={cor} data-testid="variacao">{formatarVariacao(pct)}</span>;
}

/**
 * CU06-C3 – Visualizar lista de favoritos (Figura 21): os itens em ordem alfabética, com o valor de mercado (RN06), a
 * variação em relação ao dia anterior, os alertas ativos e o selo "Dados Desatualizados" (FA2). Selecionar um item abre a
 * tela dele (passo 5); "Remover" segue o C2, com a confirmação do FA1. A ordem e os textos vêm do backend.
 */
export default function FavoritosPage() {
  const router = useRouter();
  const token = useAuthToken();
  const pronto = useAuthReady();
  const [estado, setEstado] = useState<Estado>({ lista: null, carregando: true, erro: null });

  const carregar = useCallback(async () => {
    if (!token) return;
    const resultado = await listarFavoritos(token);
    if (resultado.ok) {
      setEstado({ lista: resultado.data, carregando: false, erro: null });
    } else if (resultado.status === 401) {
      clearToken();
      router.replace("/login?aviso=sessao-expirada");
    } else {
      setEstado({ lista: null, carregando: false, erro: resultado.message });
    }
  }, [token, router]);

  // Pré-condição: o usuário deve estar autenticado.
  useEffect(() => {
    if (!pronto) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    const inicial = async () => {
      await carregar();
    };
    inicial();
  }, [pronto, token, router, carregar]);

  // C2: removido o item, a lista é recarregada (vazia, ela mostra a mensagem do FA1).
  const aoMudar = useCallback((_: number, favorito: boolean) => {
    if (!favorito) carregar();
  }, [carregar]);
  const acoes = useAcoesDeFavorito(aoMudar);
  const itens: ItemFavorito[] = estado.lista?.itens ?? [];

  return (
    <div className="min-h-screen bg-[var(--color-background)] flex flex-col">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-3 text-3xl font-bold text-[var(--color-text-title)]">
              <Star className="h-7 w-7 fill-[var(--color-cta)] text-[var(--color-cta)]" aria-hidden="true" /> Meus favoritos
            </h1>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
              Itens que você acompanha. Selecione um item para ver o histórico, a projeção e os alertas de preço.
            </p>
          </div>
          {itens.length > 0 && (
            <p className="text-sm text-[var(--color-text-secondary)]">{itens.length === 1 ? "1 item" : `${itens.length} itens`}</p>
          )}
        </div>

        {estado.carregando && !estado.lista ? (
          <p className="text-sm text-[var(--color-text-secondary)] animate-pulse">Carregando os seus favoritos...</p>
        ) : estado.erro ? (
          <p role="alert" className="rounded-xl border border-[var(--color-negative)]/50 p-6 text-center text-[var(--color-negative)]">
            {estado.erro}
          </p>
        ) : itens.length === 0 ? (
          <p role="status" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-translucent)] p-6 text-center text-[var(--color-text-secondary)]">
            {estado.lista?.mensagem}
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-translucent)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
                  <th className="px-4 py-3 font-medium">Item</th>
                  <th className="px-4 py-3 text-right font-medium">Valor de mercado</th>
                  <th className="px-4 py-3 text-right font-medium">Variação (dia anterior)</th>
                  <th className="px-4 py-3 text-center font-medium">Alertas ativos</th>
                  <th className="px-4 py-3 text-right font-medium">Ações</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((item) => (
                  <tr
                    key={item.item_id}
                    data-item={item.item_id}
                    onClick={() => router.push(`/item/${item.item_id}`)}
                    className="cursor-pointer border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface-solid)]"
                  >
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-3 text-[var(--color-text-title)]">
                        {item.icon_url
                          ? <img src={item.icon_url} alt="" className="h-10 w-10 rounded border border-[var(--color-border)]" />
                          : <span className="h-10 w-10 rounded border border-[var(--color-border)]" />}
                        <span className="font-medium">{item.name}</span>
                        {item.aviso && (
                          <span className="rounded border border-[var(--color-cta)]/40 bg-[var(--color-cta)]/10 px-2 py-0.5 text-xs text-[var(--color-cta)]">
                            {item.aviso}
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-[var(--color-cta)]">{valor(item.market_value)}</td>
                    <td className="px-4 py-3 text-right font-medium"><Variacao pct={item.variacao_pct} /></td>
                    <td className="px-4 py-3 text-center text-[var(--color-text-main)]">
                      {item.alertas_ativos > 0 ? (
                        <span className="inline-flex items-center gap-1" data-testid="alertas-ativos">
                          <Bell className="h-4 w-4 text-[var(--color-cta)]" aria-hidden="true" />{item.alertas_ativos}
                        </span>
                      ) : (
                        <span className="text-[var(--color-text-secondary)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={(evento) => {
                          evento.stopPropagation();
                          acoes.remover(item.item_id);
                        }}
                        disabled={acoes.ocupado}
                        aria-label={`Remover ${item.name} dos favoritos`}
                        className="inline-flex items-center gap-1 text-[var(--color-text-secondary)] hover:text-[var(--color-negative)]"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" /> Remover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
      {acoes.aviso && <Toast texto={acoes.aviso.texto} tom={acoes.aviso.tom} onFechar={acoes.fecharAviso} />}
      {acoes.confirmacao && (
        <Dialogo titulo="Remover dos favoritos" aoConfirmar={acoes.confirmar} aoCancelar={acoes.cancelar}
          textoConfirmar="Remover" ocupado={acoes.ocupado}>
          <p className="text-sm text-[var(--color-text-main)]">{acoes.confirmacao.texto}</p>
        </Dialogo>
      )}
    </div>
  );
}
