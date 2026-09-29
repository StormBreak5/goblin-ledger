"use client";

import { useSyncExternalStore } from "react";

// CU02: o JWT da sessão fica no navegador (localStorage) e é enviado em `Authorization: Bearer`.
// Sair (C4) e a sessão expirada removem o token.
const TOKEN_KEY = "goblin_ledger_token";
const AUTH_EVENT = "goblin-ledger-auth";

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event(AUTH_EVENT));
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // sem acesso ao armazenamento: não há token a remover
  }
  window.dispatchEvent(new Event(AUTH_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  window.addEventListener(AUTH_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(AUTH_EVENT, onChange);
  };
}

/** Token da sessão atual (null se anônimo). No servidor, e na primeira renderização, é sempre null. */
export function useAuthToken(): string | null {
  return useSyncExternalStore(subscribe, getToken, () => null);
}

const noopSubscribe = () => () => {};

/** false no servidor e na hidratação; true depois. Evita tratar "token ainda não lido" como "anônimo". */
export function useAuthReady(): boolean {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}
