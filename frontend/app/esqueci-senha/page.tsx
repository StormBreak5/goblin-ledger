"use client";

import { useState } from "react";
import Link from "next/link";
import { Aviso, AuthPage, BotaoPrimario, Campo, linkClass } from "@/components/AuthUi";
import { pedirRecuperacao } from "@/lib/authApi";

/** CU02-C2 – Solicitar recuperação de senha. A resposta é a mesma para e-mail cadastrado ou não (FA2). */
export default function EsqueciSenhaPage() {
  const [email, setEmail] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    setSucesso(null);
    const resultado = await pedirRecuperacao(email);
    setEnviando(false);
    if (resultado.ok) {
      setSucesso(resultado.data.message); // passo 8
    } else {
      setErro(resultado.message); // FA1 e FE1
    }
  };

  return (
    <AuthPage titulo="Esqueci minha senha">
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">Informe o e-mail cadastrado para receber o link de redefinição.</p>
      {sucesso && <Aviso tipo="sucesso">{sucesso}</Aviso>}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleSubmit} noValidate>
        <Campo id="email" rotulo="E-mail" type="email" value={email} onChange={setEmail} invalido={erro !== null} autoComplete="email" maxLength={150} />
        <BotaoPrimario carregando={enviando}>Enviar link</BotaoPrimario>
      </form>
      <p className="mt-4 text-center">
        <Link href="/login" className={linkClass}>
          Voltar para o login
        </Link>
      </p>
    </AuthPage>
  );
}
