"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Aviso, AuthPage, BotaoPrimario, Campo, linkClass } from "@/components/AuthUi";
import { redefinirSenha, validarLinkDeRedefinicao } from "@/lib/authApi";

function RedefinirSenhaForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [validacao, setValidacao] = useState<{ token: string; ok: boolean; message: string } | null>(null);
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [camposInvalidos, setCamposInvalidos] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  // CU02-C3 passo 2: o link é verificado ao ser aberto (válido, dentro do prazo e ainda não usado).
  useEffect(() => {
    let cancelado = false;
    validarLinkDeRedefinicao(token).then((resultado) => {
      if (!cancelado) setValidacao({ token, ok: resultado.ok, message: resultado.ok ? "" : resultado.message });
    });
    return () => {
      cancelado = true;
    };
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    setCamposInvalidos([]);
    const resultado = await redefinirSenha({ token, nova_senha: novaSenha, confirmacao_nova_senha: confirmacao });
    setEnviando(false);
    if (resultado.ok) {
      router.push("/login?senha=redefinida"); // passo 8
      return;
    }
    setErro(resultado.message); // FA1 (link), FA2 (confirmação) e FE1
    setCamposInvalidos(resultado.fields);
  };

  if (validacao?.token !== token) {
    return (
      <AuthPage titulo="Redefinir senha">
        <p role="status" className="text-sm text-[var(--color-text-secondary)]">
          Verificando o link...
        </p>
      </AuthPage>
    );
  }

  // FA1: link inválido, expirado ou já utilizado.
  if (!validacao.ok) {
    return (
      <AuthPage titulo="Redefinir senha">
        <Aviso tipo="erro">{validacao.message}</Aviso>
        <Link href="/esqueci-senha" className={linkClass}>
          Solicitar nova recuperação de senha
        </Link>
      </AuthPage>
    );
  }

  return (
    <AuthPage titulo="Redefinir senha">
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleSubmit} noValidate>
        <Campo id="nova_senha" rotulo="Nova senha" type="password" value={novaSenha} onChange={setNovaSenha} invalido={camposInvalidos.includes("nova_senha")} autoComplete="new-password" maxLength={255} />
        <Campo id="confirmacao_nova_senha" rotulo="Confirmação da nova senha" type="password" value={confirmacao} onChange={setConfirmacao} invalido={camposInvalidos.includes("confirmacao_nova_senha")} autoComplete="new-password" maxLength={255} />
        <BotaoPrimario carregando={enviando}>Redefinir senha</BotaoPrimario>
      </form>
    </AuthPage>
  );
}

/** CU02-C3 – Redefinir senha, a partir do link recebido por e-mail (`/redefinir-senha?token=...`). */
export default function RedefinirSenhaPage() {
  return (
    <Suspense fallback={null}>
      <RedefinirSenhaForm />
    </Suspense>
  );
}
