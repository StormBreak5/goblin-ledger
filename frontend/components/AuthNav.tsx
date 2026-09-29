"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearToken, useAuthToken } from "@/lib/auth";
import { sair } from "@/lib/authApi";

const linkClass = "text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)] transition-colors";

/** CU01/CU02: "Entrar" e "Criar conta" para o anônimo; "Meu perfil" e "Sair" para o usuário autenticado. */
export default function AuthNav() {
  const token = useAuthToken();
  const router = useRouter();

  // CU02-C4: invalida a sessão no backend, remove os dados de sessão do navegador e volta à página inicial.
  const handleSair = async () => {
    if (token) await sair(token);
    clearToken();
    router.push("/");
  };

  if (token) {
    return (
      <>
        <Link href="/perfil" className={linkClass}>
          Meu perfil
        </Link>
        <button type="button" onClick={handleSair} className={linkClass}>
          Sair
        </button>
      </>
    );
  }

  return (
    <>
      <Link href="/login" className={linkClass}>
        Entrar
      </Link>
      <Link href="/cadastro" className="rounded-md bg-[var(--color-cta)] px-3 py-1 font-semibold text-[#161124] hover:bg-[var(--color-cta-hover)]">
        Criar conta
      </Link>
    </>
  );
}
