"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Aviso, AuthPage, BotaoPrimario, Campo, linkClass } from "@/components/AuthUi";
import { saveToken, useAuthToken } from "@/lib/auth";
import { entrar, MSG_CONTA_CRIADA, MSG_SENHA_REDEFINIDA, MSG_SESSAO_EXPIRADA } from "@/lib/authApi";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useAuthToken();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [camposInvalidos, setCamposInvalidos] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  // Avisos vindos de outras telas: CU01-C1 passo 8, CU02-C3 passo 8 e CU02-C4-FA1.
  const aviso = searchParams.get("conta") === "criada"
    ? { tipo: "sucesso" as const, texto: MSG_CONTA_CRIADA }
    : searchParams.get("senha") === "redefinida"
      ? { tipo: "sucesso" as const, texto: MSG_SENHA_REDEFINIDA }
      : searchParams.get("aviso") === "sessao-expirada"
        ? { tipo: "erro" as const, texto: MSG_SESSAO_EXPIRADA }
        : null;

  // Pré-condição: o usuário não deve estar autenticado.
  useEffect(() => {
    if (token) router.replace("/");
  }, [token, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    setCamposInvalidos([]);
    const resultado = await entrar({ email, senha });
    setEnviando(false);
    if (resultado.ok) {
      saveToken(resultado.data.access_token); // passo 7: inicia a sessão
      router.push("/"); // passo 8: direciona à página inicial
      return;
    }
    setErro(resultado.message);
    setCamposInvalidos(resultado.fields);
  };

  return (
    <AuthPage titulo="Entrar">
      {aviso && !erro && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleSubmit} noValidate>
        <Campo id="email" rotulo="E-mail" type="email" value={email} onChange={setEmail} invalido={camposInvalidos.includes("email")} autoComplete="email" maxLength={150} />
        <Campo id="senha" rotulo="Senha" type="password" value={senha} onChange={setSenha} invalido={camposInvalidos.includes("senha")} autoComplete="current-password" maxLength={255} />
        <BotaoPrimario carregando={enviando}>Entrar</BotaoPrimario>
      </form>
      <div className="mt-4 flex justify-between">
        <Link href="/esqueci-senha" className={linkClass}>
          Esqueci minha senha
        </Link>
        <Link href="/cadastro" className={linkClass}>
          Criar conta
        </Link>
      </div>
    </AuthPage>
  );
}

/** CU02-C1 – Autenticar usuário. Erros (FA1 a FA3 e FE1) vêm do backend com o texto do cenário. */
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
