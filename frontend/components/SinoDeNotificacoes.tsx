"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell } from "lucide-react";
import { clearToken, useAuthToken } from "@/lib/auth";
import { dataEHora } from "@/lib/instante";
import { formatarMoeda } from "@/lib/moeda";
import { contarNaoLidas, listarNotificacoes, marcarComoLidas, type Notificacao } from "@/lib/notificacoesApi";

/** CU08-C3 (observações): o contador é consultado ao carregar a página e a cada 5 minutos. */
export const INTERVALO_DO_CONTADOR_MS = 5 * 60 * 1000;

interface Painel {
  carregando: boolean;
  notificacoes: Notificacao[];
  naoLidas: number; // as não lidas no momento da consulta: o destaque continua até o painel fechar
  mensagem: string | null; // FA1
  erro: string | null; // FE1
}

const PAINEL_CARREGANDO: Painel = { carregando: true, notificacoes: [], naoLidas: 0, mensagem: null, erro: null };

function valor(cobre: number): string {
  try {
    return formatarMoeda(cobre);
  } catch {
    return "—";
  }
}

/**
 * CU08-C3 – Consultar notificações (Figura 17): o sino do cabeçalho com a quantidade de não lidas (passo 1); acionado
 * (passo 2), abre o painel com as notificações da tela, da mais recente para a mais antiga, destacando as não lidas (passos
 * 3 e 4); as exibidas ficam lidas e o contador zera (passo 5); selecionar uma abre a tela do item (passo 6). FA1 e FE1:
 * as mensagens do cenário dentro do painel. A ordem, as não lidas e os textos vêm do backend.
 */
export default function SinoDeNotificacoes() {
  const token = useAuthToken();
  const router = useRouter();
  const [naoLidas, setNaoLidas] = useState(0);
  const [painel, setPainel] = useState<Painel | null>(null);
  const raiz = useRef<HTMLDivElement>(null);

  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.push("/login?aviso=sessao-expirada");
  }, [router]);

  // Passo 1: ao carregar e a cada 5 minutos. Um 401 só esconde o número; outra falha mantém o último valor.
  useEffect(() => {
    if (!token) return;
    let ativo = true;
    const atualizar = async () => {
      const resultado = await contarNaoLidas(token);
      if (!ativo) return;
      if (resultado.ok) setNaoLidas(resultado.data.nao_lidas);
      else if (resultado.status === 401) setNaoLidas(0);
    };
    atualizar();
    const temporizador = setInterval(atualizar, INTERVALO_DO_CONTADOR_MS);
    return () => {
      ativo = false;
      clearInterval(temporizador);
    };
  }, [token]);

  const fechar = useCallback(() => setPainel(null), []);

  // O painel fecha com Esc ou com um clique fora dele.
  useEffect(() => {
    if (!painel) return;
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") fechar();
    };
    const aoClicar = (evento: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(evento.target as Node)) fechar();
    };
    document.addEventListener("keydown", aoTeclar);
    document.addEventListener("mousedown", aoClicar);
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.removeEventListener("mousedown", aoClicar);
    };
  }, [painel, fechar]);

  const abrir = useCallback(async () => {
    if (!token) return;
    setPainel(PAINEL_CARREGANDO);
    const lista = await listarNotificacoes(token); // passo 3
    if (!lista.ok) {
      if (lista.status === 401) {
        setPainel(null);
        sessaoExpirada();
      } else {
        setPainel({ ...PAINEL_CARREGANDO, carregando: false, erro: lista.message }); // FE1
      }
      return;
    }
    const { notificacoes, nao_lidas, mensagem } = lista.data;
    setPainel({ carregando: false, notificacoes, naoLidas: nao_lidas, mensagem, erro: null }); // passo 4 (FA1: a mensagem)

    const exibidas = notificacoes.filter((n) => !n.lida).map((n) => n.id_notificacao);
    if (exibidas.length === 0) {
      setNaoLidas(0);
      return;
    }
    const marcadas = await marcarComoLidas(token, exibidas); // passo 5
    if (marcadas.ok) {
      setNaoLidas(marcadas.data.nao_lidas);
    } else if (marcadas.status === 401) {
      sessaoExpirada();
    } else {
      setPainel((atual) => (atual ? { ...atual, erro: marcadas.message } : atual)); // FE1: o contador fica como estava
    }
  }, [token, sessaoExpirada]);

  const abrirItem = (itemId: number) => {
    fechar();
    router.push(`/item/${itemId}`); // passo 6
  };

  if (!token) return null;

  return (
    <div ref={raiz} className="relative">
      <button
        type="button"
        aria-label="Notificações"
        aria-expanded={painel !== null}
        onClick={() => (painel ? fechar() : abrir())}
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {naoLidas > 0 && (
          <span
            data-testid="contador"
            className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-cta)] px-1 text-[10px] font-bold text-[#161124]"
          >
            {naoLidas}
          </span>
        )}
      </button>

      {painel && (
        <div
          role="dialog"
          aria-label="Notificações"
          className="absolute right-0 top-11 z-50 w-[400px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-lg border border-[var(--color-border)] bg-[#1A1525] shadow-2xl"
        >
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
            <span className="font-semibold text-[var(--color-text-title)]">Notificações</span>
            {!painel.carregando && !painel.erro && painel.notificacoes.length > 0 && (
              <span className="text-xs text-[var(--color-text-secondary)]" data-testid="nao-lidas-do-painel">
                {painel.naoLidas} não lidas
              </span>
            )}
          </div>

          {painel.carregando && <p className="px-4 py-6 text-sm text-[var(--color-text-secondary)]">Carregando…</p>}
          {painel.erro && (
            <p role="alert" className="border-b border-[var(--color-border)] px-4 py-3 text-sm text-[var(--color-negative)]">
              {painel.erro}
            </p>
          )}
          {!painel.carregando && painel.mensagem && (
            <p className="px-4 py-6 text-sm text-[var(--color-text-secondary)]">{painel.mensagem}</p>
          )}

          {painel.notificacoes.length > 0 && (
            <ul className="max-h-[420px] overflow-y-auto">
              {painel.notificacoes.map((n) => (
                <li key={n.id_notificacao} className="border-b border-[var(--color-border)] last:border-0">
                  <button
                    type="button"
                    data-notificacao={n.id_notificacao}
                    data-lida={n.lida ? "sim" : "nao"}
                    onClick={() => abrirItem(n.item_id)}
                    className={`flex w-full gap-3 px-4 py-3 text-left hover:bg-white/5 ${n.lida ? "" : "bg-[var(--color-cta)]/5"}`}
                  >
                    {n.icon_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={n.icon_url} alt="" className="mt-0.5 h-9 w-9 rounded border border-[var(--color-border)]" />
                    ) : (
                      <span className="mt-0.5 h-9 w-9 shrink-0 rounded border border-[var(--color-border)]" aria-hidden="true" />
                    )}
                    <span className="flex-1 text-sm">
                      <span className="block text-[var(--color-text-title)]">
                        <span className="font-semibold">{n.name}</span> atingiu o preço do seu alerta de{" "}
                        {n.tipo === "COMPRA" ? "compra" : "venda"}
                      </span>
                      <span className="mt-0.5 block text-[var(--color-text-secondary)]">
                        Alvo: {valor(n.preco_alvo)} · Valor de mercado:{" "}
                        <span className="text-[var(--color-cta)]">{valor(n.valor_mercado)}</span>
                      </span>
                      <span className="mt-0.5 block text-xs text-[var(--color-text-secondary)]">{dataEHora(n.disparada_em)}</span>
                    </span>
                    {!n.lida && <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[var(--color-cta)]" aria-label="Não lida" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
