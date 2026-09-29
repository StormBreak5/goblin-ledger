"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AdminPagina from "@/components/AdminPagina";
import { Aviso, BotaoPrimario, Campo, CampoRegiao } from "@/components/AuthUi";
import { clearToken } from "@/lib/auth";
import {
  consultarImportacao,
  listarImportacoes,
  solicitarImportacao,
  type ResumoImportacao,
} from "@/lib/historicoApi";

// O backend devolve datas em UTC, às vezes sem o sufixo de fuso: sem ele o navegador as leria como horário local.
const formatarData = (iso: string | null) =>
  iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleString("pt-BR") : "—";
const inteiro = (valor: number) => valor.toLocaleString("pt-BR");

const STATUS: Record<ResumoImportacao["status"], string> = {
  EM_ANDAMENTO: "Em andamento",
  CONCLUIDA: "Concluída",
  FALHA: "Falha",
};

/** CU10-C1 passo 10: resumo da importação, com a quantidade de registros importados, descartados e duplicados. */
function Resumo({ execucao }: { execucao: ResumoImportacao }) {
  return (
    <div className="space-y-2 rounded-md border border-[var(--color-border)] p-3 text-sm" aria-live="polite">
      <p className="font-semibold text-[var(--color-text-title)]">
        Importação #{execucao.id_execucao}: {STATUS[execucao.status]}
      </p>
      {execucao.status === "EM_ANDAMENTO" && (
        <p className="text-[var(--color-text-secondary)]">
          {inteiro(execucao.itens_processados)}
          {execucao.itens_solicitados !== null ? ` de ${inteiro(execucao.itens_solicitados)}` : ""} itens processados. Isso pode
          levar vários minutos; a tela acompanha o andamento.
        </p>
      )}
      <p className="text-[var(--color-text-title)]">
        Importados: {inteiro(execucao.registros_importados)} · Descartados: {inteiro(execucao.registros_descartados)} · Duplicados:{" "}
        {inteiro(execucao.registros_duplicados)}
      </p>
      <p className="text-[var(--color-text-secondary)]">
        {inteiro(execucao.itens_processados)} itens processados
        {execucao.itens_cadastrados > 0 ? `, ${inteiro(execucao.itens_cadastrados)} cadastrados` : ""}
        {execucao.itens_sem_dados > 0 ? `, ${inteiro(execucao.itens_sem_dados)} sem arquivo na fonte` : ""}
        {execucao.itens_com_erro > 0 ? `, ${inteiro(execucao.itens_com_erro)} com falha de leitura` : ""}. Iniciada em{" "}
        {formatarData(execucao.iniciada_em)}
        {execucao.concluida_em ? `, terminada em ${formatarData(execucao.concluida_em)}` : ""}.
      </p>
      {execucao.status === "FALHA" && (
        <p role="alert" className="text-[var(--color-negative)]">
          {execucao.mensagem}
          {execucao.etapa_da_falha === "FONTE" || execucao.etapa_da_falha === "FORMATO"
            ? " Os registros já gravados foram mantidos."
            : execucao.etapa_da_falha === "BANCO"
              ? " Nada foi gravado."
              : ""}
        </p>
      )}
      {execucao.status === "FALHA" && execucao.erro && (
        <p className="break-words text-xs text-[var(--color-text-secondary)]">
          Etapa {execucao.etapa_da_falha}: {execucao.erro}
        </p>
      )}
    </div>
  );
}

function ImportacaoDeHistorico({ token }: { token: string }) {
  const router = useRouter();
  const [regiao, setRegiao] = useState("US");
  const [reino, setReino] = useState("");
  const [itens, setItens] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [execucao, setExecucao] = useState<ResumoImportacao | null>(null);
  const [recentes, setRecentes] = useState<ResumoImportacao[]>([]);

  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  }, [router]);

  const carregarRecentes = useCallback(async () => {
    const resultado = await listarImportacoes(token);
    if (resultado.ok) setRecentes(resultado.data);
  }, [token]);

  useEffect(() => {
    let cancelado = false;
    listarImportacoes(token).then((resultado) => {
      if (!cancelado && resultado.ok) setRecentes(resultado.data);
    });
    return () => {
      cancelado = true;
    };
  }, [token]);

  // Acompanha a importação enquanto ela roda em segundo plano no servidor.
  const idEmAndamento = execucao?.status === "EM_ANDAMENTO" ? execucao.id_execucao : null;
  useEffect(() => {
    if (idEmAndamento === null) return;
    let cancelado = false;
    const temporizador = setInterval(async () => {
      const resultado = await consultarImportacao(token, idEmAndamento);
      if (cancelado) return;
      if (resultado.ok) {
        setErro(null);
        setExecucao(resultado.data);
        if (resultado.data.status !== "EM_ANDAMENTO") carregarRecentes();
      } else if (resultado.status === 401) {
        sessaoExpirada();
      } else {
        setErro(resultado.message);
      }
    }, 3000);
    return () => {
      cancelado = true;
      clearInterval(temporizador);
    };
  }, [idEmAndamento, token, carregarRecentes, sessaoExpirada]);

  const handleImportar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    setExecucao(null);
    const ids = itens.split(/[\s,;]+/).filter((valor) => valor !== "");
    const resultado = await solicitarImportacao(token, { regiao, reino, itens: ids });
    setEnviando(false);
    if (resultado.ok) {
      setExecucao(resultado.data);
      carregarRecentes();
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErro(resultado.message); // FA1: "Região ou item inválido. Verifique os dados informados" (volta ao passo 1)
    }
  };

  return (
    <>
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
        Importa o histórico retroativo de preços dos arquivos da Undermine Exchange (diário desde set/2022, mais os últimos snapshots
        horários), harmonizado ao padrão do sistema. Sem itens informados, importa todos os itens ativos, o que leva bem mais tempo; a tela acompanha o andamento.
      </p>

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleImportar} noValidate className="max-w-md">
        <CampoRegiao value={regiao} onChange={setRegiao} />
        <Campo id="reino" rotulo="Reino conectado (opcional)" value={reino} onChange={setReino} maxLength={8} />
        <div className="mb-4">
          <label htmlFor="itens" className="mb-1 block text-sm text-[var(--color-text-secondary)]">
            Itens (opcional): ids separados por vírgula ou por linha
          </label>
          <textarea
            id="itens"
            name="itens"
            rows={3}
            value={itens}
            onChange={(e) => setItens(e.target.value)}
            className="block w-full rounded-md border border-[var(--color-border)] bg-[#1A1525] px-3 py-2 text-[var(--color-text-main)] focus:outline-none focus:ring-1 focus:ring-[var(--color-cta)]"
          />
        </div>
        <BotaoPrimario carregando={enviando || idEmAndamento !== null}>
          {enviando ? "Enviando..." : idEmAndamento !== null ? "Importação em andamento..." : "Importar histórico"}
        </BotaoPrimario>
      </form>

      {execucao && (
        <div className="mt-6">
          <Resumo execucao={execucao} />
        </div>
      )}

      {recentes.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-2 text-lg font-semibold text-[var(--color-text-title)]">Importações recentes</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[var(--color-text-secondary)]">
                <tr>
                  <th className="py-1 pr-3 font-normal">Início</th>
                  <th className="py-1 pr-3 font-normal">Situação</th>
                  <th className="py-1 pr-3 text-right font-normal">Importados</th>
                  <th className="py-1 pr-3 text-right font-normal">Descartados</th>
                  <th className="py-1 text-right font-normal">Duplicados</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-main)]">
                {recentes.map((item) => (
                  <tr key={item.id_execucao} className="border-t border-[var(--color-border)]">
                    <td className="py-1 pr-3">{formatarData(item.iniciada_em)}</td>
                    <td className="py-1 pr-3">
                      {STATUS[item.status]}
                      {item.disparo === "RECUPERACAO" ? " (recuperação automática)" : ""}
                    </td>
                    <td className="py-1 pr-3 text-right">{inteiro(item.registros_importados)}</td>
                    <td className="py-1 pr-3 text-right">{inteiro(item.registros_descartados)}</td>
                    <td className="py-1 text-right">{inteiro(item.registros_duplicados)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

/** CU10-C1 – Importar histórico de preços (Admin). */
export default function HistoricoPage() {
  return (
    <AdminPagina titulo="Histórico de preços" href="/admin/historico">
      {(token) => <ImportacaoDeHistorico token={token} />}
    </AdminPagina>
  );
}
