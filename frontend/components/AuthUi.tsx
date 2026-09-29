"use client";

import type { ReactNode } from "react";
import Header from "@/components/Header";

// Peças de interface compartilhadas pelas telas dos CU01 e CU02. Só apresentação: as regras e os textos das
// mensagens vêm do backend.

const inputBase =
  "block w-full rounded-md border bg-[#1A1525] px-3 py-2 text-[var(--color-text-main)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-cta)] disabled:opacity-60";

export function AuthPage({ titulo, children, larga = false }: { titulo: string; children: ReactNode; larga?: boolean }) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-background)]">
      <Header />
      <main className="flex flex-1 items-start justify-center px-4 py-12">
        <div className={`w-full ${larga ? "max-w-4xl" : "max-w-md"} rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-solid)] p-8 shadow-xl`}>
          <h1 className="mb-6 text-2xl font-bold text-[var(--color-text-title)]">{titulo}</h1>
          {children}
        </div>
      </main>
    </div>
  );
}

export function Aviso({ tipo, children }: { tipo: "erro" | "sucesso"; children: ReactNode }) {
  const cores =
    tipo === "erro"
      ? "border-[var(--color-negative)]/50 text-[var(--color-negative)]"
      : "border-[var(--color-positive)]/50 text-[var(--color-positive)]";
  return (
    <div role={tipo === "erro" ? "alert" : "status"} className={`mb-4 rounded-md border bg-[#1A1525] px-3 py-2 text-sm ${cores}`}>
      {children}
    </div>
  );
}

interface CampoProps {
  id: string;
  rotulo: string;
  value: string;
  onChange: (valor: string) => void;
  type?: "text" | "email" | "password";
  invalido?: boolean;
  somenteLeitura?: boolean;
  autoComplete?: string;
  maxLength?: number;
}

export function Campo({ id, rotulo, value, onChange, type = "text", invalido = false, somenteLeitura = false, autoComplete, maxLength }: CampoProps) {
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block text-sm text-[var(--color-text-secondary)]">
        {rotulo}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        readOnly={somenteLeitura}
        autoComplete={autoComplete}
        maxLength={maxLength}
        aria-invalid={invalido}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputBase} ${invalido ? "border-[var(--color-negative)]" : "border-[var(--color-border)]"} ${somenteLeitura ? "opacity-70" : ""}`}
      />
    </div>
  );
}

export function CampoRegiao({ value, onChange, invalido = false }: { value: string; onChange: (valor: string) => void; invalido?: boolean }) {
  return (
    <div className="mb-4">
      <label htmlFor="regiao" className="mb-1 block text-sm text-[var(--color-text-secondary)]">
        Região
      </label>
      <select
        id="regiao"
        name="regiao"
        value={value}
        aria-invalid={invalido}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputBase} ${invalido ? "border-[var(--color-negative)]" : "border-[var(--color-border)]"}`}
      >
        <option value="">Selecione a região</option>
        <option value="US">US</option>
        <option value="EU">EU</option>
      </select>
    </div>
  );
}

export function BotaoPrimario({ children, carregando = false }: { children: ReactNode; carregando?: boolean }) {
  return (
    <button
      type="submit"
      disabled={carregando}
      className="w-full rounded-md bg-[var(--color-cta)] px-4 py-2 font-bold text-[#161124] transition-colors hover:bg-[var(--color-cta-hover)] disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export const linkClass = "text-sm text-[var(--color-cta)] hover:underline";
