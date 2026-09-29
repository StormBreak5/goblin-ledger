"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Aviso, AuthPage, BotaoPrimario, Campo, CampoRegiao, linkClass } from "@/components/AuthUi";
import { useAuthToken } from "@/lib/auth";
import { cadastrar } from "@/lib/authApi";

/** CU01-C1 – Cadastrar usuário. A validação (FA1) e a unicidade do e-mail (FA2) são do backend. */
export default function CadastroPage() {
  const router = useRouter();
  const token = useAuthToken();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [regiao, setRegiao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [camposInvalidos, setCamposInvalidos] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  // Pré-condição: o usuário não deve estar autenticado.
  useEffect(() => {
    if (token) router.replace("/");
  }, [token, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    setCamposInvalidos([]);
    const resultado = await cadastrar({ email, senha, confirmacao_senha: confirmacao, regiao });
    setEnviando(false);
    if (resultado.ok) {
      router.push("/login?conta=criada"); // passo 8: mensagem de sucesso e direciona à tela de login
      return;
    }
    setErro(resultado.message);
    setCamposInvalidos(resultado.fields);
  };

  const invalido = (campo: string) => camposInvalidos.includes(campo);

  return (
    <AuthPage titulo="Criar conta">
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleSubmit} noValidate>
        <Campo id="email" rotulo="E-mail" type="email" value={email} onChange={setEmail} invalido={invalido("email")} autoComplete="email" maxLength={150} />
        <Campo id="senha" rotulo="Senha" type="password" value={senha} onChange={setSenha} invalido={invalido("senha")} autoComplete="new-password" maxLength={255} />
        <Campo id="confirmacao_senha" rotulo="Confirmação de senha" type="password" value={confirmacao} onChange={setConfirmacao} invalido={invalido("confirmacao_senha")} autoComplete="new-password" maxLength={255} />
        <CampoRegiao value={regiao} onChange={setRegiao} invalido={invalido("regiao")} />
        <BotaoPrimario carregando={enviando}>Criar conta</BotaoPrimario>
      </form>
      <p className="mt-4 text-center text-sm text-[var(--color-text-secondary)]">
        Já tem conta?{" "}
        <Link href="/login" className={linkClass}>
          Entrar
        </Link>
      </p>
    </AuthPage>
  );
}
