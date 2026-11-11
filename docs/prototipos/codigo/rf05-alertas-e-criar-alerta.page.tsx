"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Star, Plus, Pencil, Trash2, Bell } from "lucide-react";
import Header from "@/components/Header";
import PrecoAtualDoItem from "@/components/PrecoAtualDoItem";
import PriceChart from "@/components/PriceChart";
import { fetchItem, type ItemDetail } from "@/lib/itemSearch";
import { useHistoricoDoItem, usePrecoAtual } from "@/lib/useHistoricoDoItem";
import { formatarMoeda } from "@/lib/moeda";
import { ALERTAS } from "@/components/proto/dados";

const JANELAS = ["14 Dias", "1 Mês", "3 Meses", "1 Ano", "Tudo"];

/** CU06-C1 e CU07 (protótipo): tela de detalhes do item com o controle de favorito e a seção "Alertas de preço". */
function Conteudo() {
  const id = useParams().id as string;
  const modal = useSearchParams().get("modal");
  const [item, setItem] = useState<ItemDetail | null>(null);
  useEffect(() => {
    fetchItem(id).then((r) => r.status === "found" && setItem(r.item));
  }, [id]);
  const { dados } = useHistoricoDoItem(id);
  const { preco } = usePrecoAtual(id);

  return (
    <div className="min-h-screen bg-[var(--color-background)] flex flex-col">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {item?.icon_url && <img src={item.icon_url} alt="" className="w-16 h-16 rounded-lg border border-[var(--color-border)] shadow-md" />}
            <div>
              <h1 className="text-3xl font-bold text-[var(--color-text-title)]">{item?.name}</h1>
              <button type="button" className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-[var(--color-cta)]/50 bg-[var(--color-cta)]/10 px-2.5 py-1 text-xs font-semibold text-[var(--color-cta)]">
                <Star className="h-3.5 w-3.5 fill-[var(--color-cta)]" aria-hidden="true" /> Favoritado
              </button>
            </div>
          </div>
          {preco && <PrecoAtualDoItem preco={preco} />}
        </div>
        <div className="flex justify-end gap-2 mb-4">
          {JANELAS.map((j, k) => (
            <span key={j} className={`px-3 py-1 rounded text-sm ${k === 0 ? "bg-[var(--color-cta)] text-[#161124] font-bold" : "bg-[var(--color-surface-solid)] text-[var(--color-text-secondary)] border border-[var(--color-border)]"}`}>{j}</span>
          ))}
        </div>
        <div className="h-[380px] w-full">
          <PriceChart data={dados?.pontos ?? []} />
        </div>

        <section className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-translucent)] p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-bold text-[var(--color-text-title)]">
                <Bell className="h-5 w-5 text-[var(--color-cta)]" aria-hidden="true" /> Alertas de preço
              </h2>
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Você tem 2 de 20 alertas ativos em todos os seus itens</p>
            </div>
            <button type="button" className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-cta)] px-3 py-2 text-sm font-semibold text-[#161124]">
              <Plus className="h-4 w-4" aria-hidden="true" /> Criar alerta
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
                <th className="py-2 font-medium">Tipo de gatilho</th>
                <th className="py-2 font-medium">Preço-alvo</th>
                <th className="py-2 font-medium">Canal</th>
                <th className="py-2 font-medium">Situação</th>
                <th className="py-2 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {ALERTAS.map((a) => (
                <tr key={a.tipo} className="border-b border-[var(--color-border)] last:border-0">
                  <td className="py-3 text-[var(--color-text-title)]">
                    {a.tipo} <span className="text-[var(--color-text-secondary)]">({a.tipo === "Compra" ? "preço cair até o alvo" : "preço subir até o alvo"})</span>
                  </td>
                  <td className="py-3 font-semibold text-[var(--color-cta)]">{formatarMoeda(a.alvo)}</td>
                  <td className="py-3 text-[var(--color-text-main)]">{a.canal}</td>
                  <td className="py-3">
                    {a.situacao === "Ativo" ? (
                      <span className="rounded bg-[var(--color-positive)]/15 px-2 py-0.5 text-xs font-semibold text-[var(--color-positive)]">Ativo</span>
                    ) : (
                      <span className="text-xs text-[var(--color-text-secondary)]">
                        <span className="mr-2 rounded bg-white/10 px-2 py-0.5 font-semibold text-[var(--color-text-main)]">Disparado</span>
                        em {a.disparadoEm}
                      </span>
                    )}
                  </td>
                  <td className="py-3 text-right">
                    <span className="inline-flex gap-4 text-[var(--color-text-secondary)]">
                      <span className="inline-flex items-center gap-1"><Pencil className="h-4 w-4" aria-hidden="true" /> {a.situacao === "Disparado" ? "Editar e reativar" : "Editar"}</span>
                      <span className="inline-flex items-center gap-1"><Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>

      {modal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div role="dialog" aria-labelledby="titulo-alerta" className="w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[#1A1525] p-6 shadow-2xl">
            <h2 id="titulo-alerta" className="text-xl font-bold text-[var(--color-text-title)]">Criar alerta de preço</h2>
            <div className="mt-3 flex items-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-solid)] px-3 py-2">
              {item?.icon_url && <img src={item.icon_url} alt="" className="h-9 w-9 rounded border border-[var(--color-border)]" />}
              <div className="text-sm">
                <p className="font-semibold text-[var(--color-text-title)]">{item?.name}</p>
                <p className="text-[var(--color-text-secondary)]">Valor de mercado atual: <span className="font-semibold text-[var(--color-cta)]">{preco ? formatarMoeda(preco.market_value ?? preco.min_price) : ""}</span></p>
              </div>
            </div>
            <p className="mt-5 mb-2 text-sm text-[var(--color-text-secondary)]">Tipo de gatilho</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-md border-2 border-[var(--color-cta)] bg-[var(--color-cta)]/10 px-3 py-2">
                <p className="text-sm font-semibold text-[var(--color-text-title)]">Compra</p>
                <p className="text-xs text-[var(--color-text-secondary)]">Avisar quando o preço cair até o alvo</p>
              </div>
              <div className="rounded-md border border-[var(--color-border)] px-3 py-2">
                <p className="text-sm font-semibold text-[var(--color-text-main)]">Venda</p>
                <p className="text-xs text-[var(--color-text-secondary)]">Avisar quando o preço subir até o alvo</p>
              </div>
            </div>
            <p className="mt-5 mb-2 text-sm text-[var(--color-text-secondary)]">Preço-alvo</p>
            <div className="grid grid-cols-3 gap-2">
              {[["17", "Ouro"], ["50", "Prata"], ["0", "Cobre"]].map(([v, r]) => (
                <label key={r} className="text-xs text-[var(--color-text-secondary)]">
                  <span className="flex items-center rounded-md border border-[var(--color-border)] bg-[var(--color-surface-solid)] px-3 py-2 text-sm text-[var(--color-text-title)]">{v}</span>
                  <span className="mt-1 block">{r}</span>
                </label>
              ))}
            </div>
            <p className="mt-4 mb-2 text-sm text-[var(--color-text-secondary)]">Canal de notificação</p>
            <div className="flex gap-5 text-sm text-[var(--color-text-main)]">
              {["Tela", "E-mail", "Ambos"].map((c) => (
                <span key={c} className="inline-flex items-center gap-2">
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full border ${c === "Ambos" ? "border-[var(--color-cta)]" : "border-[var(--color-text-secondary)]"}`}>
                    {c === "Ambos" && <span className="h-2 w-2 rounded-full bg-[var(--color-cta)]" />}
                  </span>
                  {c}
                </span>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-main)]">Cancelar</button>
              <button type="button" className="rounded-md bg-[var(--color-cta)] px-4 py-2 text-sm font-semibold text-[#161124]">Salvar alerta</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <Conteudo />
    </Suspense>
  );
}
