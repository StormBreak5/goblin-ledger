"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Aviso, AuthPage, BotaoPrimario, Campo, CampoRegiao } from "@/components/AuthUi";
import { clearToken, useAuthReady, useAuthToken } from "@/lib/auth";
import { alterarDados, carregarPerfil, excluirConta, type Perfil } from "@/lib/authApi";

/** CU01-C2 (Alterar dados) e CU01-C3 (Excluir conta): tela "Meu perfil". */
export default function PerfilPage() {
  const router = useRouter();
  const token = useAuthToken();
  const pronto = useAuthReady();
  const jaCarregou = useRef(false);

  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [erroDeCarga, setErroDeCarga] = useState<string | null>(null);
  const [regiao, setRegiao] = useState("");
  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [camposInvalidos, setCamposInvalidos] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);

  const [modalAberto, setModalAberto] = useState(false);
  const [senhaDaExclusao, setSenhaDaExclusao] = useState("");
  const [erroDaExclusao, setErroDaExclusao] = useState<string | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  // CU02-C4-FA1: a sessão deixou de valer (expirada ou encerrada).
  const sessaoExpirou = () => {
    jaCarregou.current = true; // o redirecionamento já está sendo feito aqui
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  };

  // Pré-condição: o usuário deve estar autenticado. Passo 2: recupera e exibe os dados cadastrados.
  useEffect(() => {
    if (!pronto) return;
    if (!token) {
      // Sem token desde o início: vai ao login. Se o token sumiu depois de carregar (o usuário saiu ou excluiu a
      // conta), quem removeu o token já direciona à página inicial (CU02-C4 passo 4 / CU01-C3 passo 7).
      if (!jaCarregou.current) router.replace("/login");
      return;
    }
    let cancelado = false;
    carregarPerfil(token).then((resultado) => {
      if (cancelado) return;
      if (resultado.ok) {
        jaCarregou.current = true;
        setPerfil(resultado.data);
        setRegiao(resultado.data.regiao);
      } else if (resultado.status === 401) {
        jaCarregou.current = true; // o redirecionamento já está sendo feito aqui
        clearToken();
        router.replace("/login?aviso=sessao-expirada");
      } else {
        setErroDeCarga(resultado.message);
      }
    });
    return () => {
      cancelado = true;
    };
  }, [pronto, token, router]);

  const handleSalvar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setEnviando(true);
    setErro(null);
    setSucesso(null);
    setCamposInvalidos([]);
    const resultado = await alterarDados(token, {
      regiao,
      senha_atual: senhaAtual,
      nova_senha: novaSenha,
      confirmacao_nova_senha: confirmacao,
    });
    setEnviando(false);
    if (resultado.ok) {
      setSucesso(resultado.data.message);
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmacao("");
      return;
    }
    if (resultado.status === 401) return sessaoExpirou();
    setErro(resultado.message);
    setCamposInvalidos(resultado.fields);
  };

  const fecharModal = () => {
    setModalAberto(false);
    setSenhaDaExclusao("");
    setErroDaExclusao(null);
  };

  // CU01-C3 passos 3 a 7. FA2: senha incorreta mantém o aviso aberto; FA1: cancelar não altera a conta.
  const handleExcluir = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setExcluindo(true);
    setErroDaExclusao(null);
    const resultado = await excluirConta(token, senhaDaExclusao);
    setExcluindo(false);
    if (resultado.ok) {
      clearToken(); // passo 7: encerra a sessão e direciona à página inicial
      router.push("/");
      return;
    }
    if (resultado.status === 401) return sessaoExpirou();
    setErroDaExclusao(resultado.message);
  };

  const invalido = (campo: string) => camposInvalidos.includes(campo);

  if (erroDeCarga) {
    return (
      <AuthPage titulo="Meu perfil">
        <Aviso tipo="erro">{erroDeCarga}</Aviso>
      </AuthPage>
    );
  }

  if (!perfil) {
    return (
      <AuthPage titulo="Meu perfil">
        <p role="status" className="text-sm text-[var(--color-text-secondary)]">
          Carregando...
        </p>
      </AuthPage>
    );
  }

  return (
    <AuthPage titulo="Meu perfil">
      {sucesso && <Aviso tipo="sucesso">{sucesso}</Aviso>}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleSalvar} noValidate>
        <Campo id="email" rotulo="E-mail" type="email" value={perfil.email} onChange={() => {}} somenteLeitura />
        <CampoRegiao value={regiao} onChange={setRegiao} invalido={invalido("regiao")} />
        <p className="mb-3 text-sm text-[var(--color-text-secondary)]">Para trocar a senha, preencha os três campos abaixo.</p>
        <Campo id="senha_atual" rotulo="Senha atual" type="password" value={senhaAtual} onChange={setSenhaAtual} invalido={invalido("senha_atual")} autoComplete="current-password" maxLength={255} />
        <Campo id="nova_senha" rotulo="Nova senha" type="password" value={novaSenha} onChange={setNovaSenha} invalido={invalido("nova_senha")} autoComplete="new-password" maxLength={255} />
        <Campo id="confirmacao_nova_senha" rotulo="Confirmação da nova senha" type="password" value={confirmacao} onChange={setConfirmacao} invalido={invalido("confirmacao_nova_senha")} autoComplete="new-password" maxLength={255} />
        <BotaoPrimario carregando={enviando}>Salvar alterações</BotaoPrimario>
      </form>

      {perfil.role === "admin" && (
        <p className="mt-6 text-center">
          <Link href="/admin/ingestao" className="text-sm text-[var(--color-cta)] hover:underline">
            Ingestão de mercado (Admin)
          </Link>
        </p>
      )}

      <hr className="my-8 border-[var(--color-border)]" />
      <button
        type="button"
        onClick={() => setModalAberto(true)}
        className="w-full rounded-md border border-[var(--color-negative)] px-4 py-2 font-semibold text-[var(--color-negative)] transition-colors hover:bg-[var(--color-negative)]/10"
      >
        Excluir conta
      </button>

      {modalAberto && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 px-4">
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-exclusao"
            onSubmit={handleExcluir}
            className="w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-solid)] p-6 shadow-2xl"
          >
            <h2 id="titulo-exclusao" className="mb-3 text-xl font-bold text-[var(--color-text-title)]">
              Excluir conta
            </h2>
            <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
              A exclusão é definitiva e removerá a sua conta, os itens favoritos e os alertas cadastrados. Informe a sua senha para confirmar.
            </p>
            {erroDaExclusao && <Aviso tipo="erro">{erroDaExclusao}</Aviso>}
            <Campo id="senha_exclusao" rotulo="Senha" type="password" value={senhaDaExclusao} onChange={setSenhaDaExclusao} invalido={erroDaExclusao !== null} autoComplete="current-password" maxLength={255} />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={fecharModal}
                className="flex-1 rounded-md border border-[var(--color-border)] px-4 py-2 text-[var(--color-text-main)] hover:bg-[var(--color-surface-translucent)]"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={excluindo}
                className="flex-1 rounded-md bg-[var(--color-negative)] px-4 py-2 font-bold text-white disabled:opacity-60"
              >
                Excluir definitivamente
              </button>
            </div>
          </form>
        </div>
      )}
    </AuthPage>
  );
}
