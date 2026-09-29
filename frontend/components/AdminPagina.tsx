"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import AdminNav from "@/components/AdminNav";
import { Aviso, AuthPage } from "@/components/AuthUi";
import { clearToken, useAuthReady, useAuthToken } from "@/lib/auth";
import { carregarPerfil } from "@/lib/authApi";
import { MSG_ACESSO_RESTRITO_AO_ADMIN } from "@/lib/mercadoApi";

interface Props {
  titulo: string;
  href: string;
  /** Recebe o token da sessão do Admin; só é renderizado depois de confirmado o papel (pré-condição dos CU do Admin). */
  children: (token: string) => ReactNode;
}

/** Pré-condição das telas do Admin: sessão válida e papel de Admin (CU01). Usuário comum vê "Acesso restrito ao administrador". */
export default function AdminPagina({ titulo, href, children }: Props) {
  const router = useRouter();
  const token = useAuthToken();
  const pronto = useAuthReady();
  const [admin, setAdmin] = useState<boolean | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!pronto) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelado = false;
    carregarPerfil(token).then((resultado) => {
      if (cancelado) return;
      if (resultado.ok) {
        setAdmin(resultado.data.role === "admin");
      } else if (resultado.status === 401) {
        clearToken();
        router.replace("/login?aviso=sessao-expirada");
      } else {
        setErro(resultado.message);
      }
    });
    return () => {
      cancelado = true;
    };
  }, [pronto, token, router]);

  if (admin === null || !token) {
    return (
      <AuthPage titulo={titulo} larga>
        {erro ? <Aviso tipo="erro">{erro}</Aviso> : <p role="status" className="text-sm text-[var(--color-text-secondary)]">Carregando...</p>}
      </AuthPage>
    );
  }

  if (!admin) {
    return (
      <AuthPage titulo={titulo} larga>
        <Aviso tipo="erro">{MSG_ACESSO_RESTRITO_AO_ADMIN}</Aviso>
      </AuthPage>
    );
  }

  return (
    <AuthPage titulo={titulo} larga>
      <AdminNav atual={href} />
      {children(token)}
    </AuthPage>
  );
}
