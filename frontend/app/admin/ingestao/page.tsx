"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Aviso, AuthPage, BotaoPrimario, Campo, CampoRegiao } from "@/components/AuthUi";
import { clearToken, useAuthReady, useAuthToken } from "@/lib/auth";
import { carregarPerfil, type Perfil } from "@/lib/authApi";
import {
  carregarEstadoDosMercados,
  executarIngestao,
  MSG_ACESSO_RESTRITO_AO_ADMIN,
  type EstadoMercado,
  type ResumoIngestao,
} from "@/lib/mercadoApi";

const formatarData = (iso: string | null) => (iso ? new Date(iso).toLocaleString("pt-BR") : "—");

/** CU09-C4 – Executar ingestão manual (Admin) e frescor dos mercados (RN09 / RN14). */
export default function IngestaoManualPage() {
  const router = useRouter();
  const token = useAuthToken();
  const pronto = useAuthReady();

  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [regiao, setRegiao] = useState("US");
  const [reino, setReino] = useState("");
  const [executando, setExecutando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ResumoIngestao | null>(null);
  const [estados, setEstados] = useState<EstadoMercado[]>([]);

  // Pré-condição: o usuário deve estar autenticado e ter o papel de Admin.
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
        setPerfil(resultado.data);
      } else if (resultado.status === 401) {
        clearToken();
        router.replace("/login?aviso=sessao-expirada");
      } else {
        setErro(resultado.message);
      }
    });
    carregarEstadoDosMercados().then((resultado) => {
      if (!cancelado && resultado.ok) setEstados(resultado.data);
    });
    return () => {
      cancelado = true;
    };
  }, [pronto, token, router]);

  const handleExecutar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setExecutando(true);
    setErro(null);
    setResumo(null);
    const numero = reino.trim() === "" ? null : Number(reino);
    const resultado = await executarIngestao(token, regiao, numero);
    setExecutando(false);
    if (resultado.ok) {
      setResumo(resultado.data);
      const estado = await carregarEstadoDosMercados();
      if (estado.ok) setEstados(estado.data);
    } else if (resultado.status === 401) {
      clearToken();
      router.replace("/login?aviso=sessao-expirada");
    } else {
      setErro(resultado.message);
    }
  };

  if (!perfil) {
    return (
      <AuthPage titulo="Ingestão de mercado">
        {erro ? <Aviso tipo="erro">{erro}</Aviso> : <p role="status" className="text-sm text-[var(--color-text-secondary)]">Carregando...</p>}
      </AuthPage>
    );
  }

  if (perfil.role !== "admin") {
    return (
      <AuthPage titulo="Ingestão de mercado">
        <Aviso tipo="erro">{MSG_ACESSO_RESTRITO_AO_ADMIN}</Aviso>
      </AuthPage>
    );
  }

  return (
    <AuthPage titulo="Ingestão de mercado">
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
        Coleta, sanitiza e consolida os leilões da Blizzard. O intervalo mínimo entre coletas de um mesmo endpoint é de 60 minutos.
      </p>

      {estados.length > 0 && (
        <ul className="mb-6 space-y-1 text-sm">
          {estados.map((estado) => (
            <li key={estado.mercado} className="flex items-center justify-between gap-3 text-[var(--color-text-main)]">
              <span>{estado.mercado}</span>
              <span className={estado.desatualizado ? "text-[var(--color-negative)]" : "text-[var(--color-text-secondary)]"}>
                {estado.desatualizado ? "Dados Desatualizados · " : ""}
                atualizado em {formatarData(estado.ultima_atualizacao_em)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleExecutar} noValidate>
        <CampoRegiao value={regiao} onChange={setRegiao} />
        <Campo id="reino" rotulo="Reino conectado (opcional)" value={reino} onChange={setReino} maxLength={8} />
        <BotaoPrimario carregando={executando}>{executando ? "Executando..." : "Executar ingestão"}</BotaoPrimario>
      </form>

      {resumo && (
        <div className="mt-6 space-y-3 text-sm">
          <p className="text-[var(--color-text-title)]">
            Coletados: {resumo.leiloes_coletados} · Descartados: {resumo.leiloes_descartados} · Itens atualizados: {resumo.itens_atualizados}
          </p>
          {resumo.mercados.map((mercado) => (
            <div key={mercado.mercado} className="rounded-md border border-[var(--color-border)] p-3">
              <p className="font-semibold text-[var(--color-text-title)]">
                {mercado.mercado}: {mercado.status}
              </p>
              {mercado.status === "SUCESSO" && (
                <p className="text-[var(--color-text-secondary)]">
                  {mercado.leiloes_coletados} leilões, {mercado.leiloes_descartados} descartados, {mercado.itens_atualizados} itens atualizados
                  {mercado.itens_anomalos > 0 ? `, ${mercado.itens_anomalos} com volume anômalo` : ""}
                  {mercado.itens_cadastrados > 0 ? `, ${mercado.itens_cadastrados} itens cadastrados` : ""}.
                </p>
              )}
              {mercado.status === "CANCELADO" && (
                <p className="text-[var(--color-text-secondary)]">
                  Intervalo mínimo não atingido. Nova coleta permitida a partir de {formatarData(mercado.proxima_permitida)}.
                </p>
              )}
              {mercado.status === "FALHA" && (
                <p className="text-[var(--color-negative)]">
                  Falha na etapa {mercado.etapa_da_falha}: {mercado.erro}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </AuthPage>
  );
}
