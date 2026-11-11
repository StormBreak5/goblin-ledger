"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import { formatarMoeda } from "@/lib/moeda";
import { icone, NOTIFICACOES } from "@/components/proto/dados";

/** CU08-C3 (protótipo): sino com a quantidade de não lidas e a lista das notificações. */
export default function SinoDeNotificacoes() {
  const [aberto, setAberto] = useState(false);
  const naoLidas = NOTIFICACOES.filter((n) => !n.lida).length;
  return (
    <div className="relative">
      <button type="button" aria-label="Notificações" onClick={() => setAberto((a) => !a)}
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]">
        <Bell className="h-5 w-5" aria-hidden="true" />
        {naoLidas > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-cta)] px-1 text-[10px] font-bold text-[#161124]">
            {naoLidas}
          </span>
        )}
      </button>
      {aberto && (
        <div className="absolute right-0 top-11 z-50 w-[400px] overflow-hidden rounded-lg border border-[var(--color-border)] bg-[#1A1525] shadow-2xl">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
            <span className="font-semibold text-[var(--color-text-title)]">Notificações</span>
            <span className="text-xs text-[var(--color-text-secondary)]">{naoLidas} não lidas</span>
          </div>
          <ul>
            {NOTIFICACOES.map((n) => (
              <li key={n.quando} className={`flex gap-3 border-b border-[var(--color-border)] px-4 py-3 last:border-0 ${n.lida ? "" : "bg-[var(--color-cta)]/5"}`}>
                <img src={icone(n.icone)} alt="" className="mt-0.5 h-9 w-9 rounded border border-[var(--color-border)]" />
                <div className="flex-1 text-sm">
                  <p className="text-[var(--color-text-title)]">
                    <span className="font-semibold">{n.item}</span> atingiu o preço do seu alerta de {n.tipo.toLowerCase()}
                  </p>
                  <p className="mt-0.5 text-[var(--color-text-secondary)]">
                    Alvo: {formatarMoeda(n.alvo)} · Valor de mercado: <span className="text-[var(--color-cta)]">{formatarMoeda(n.valor)}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">{n.quando}</p>
                </div>
                {!n.lida && <span className="mt-2 h-2 w-2 rounded-full bg-[var(--color-cta)]" aria-label="Não lida" />}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
