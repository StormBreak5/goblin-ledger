"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AdminPagina from "@/components/AdminPagina";
import { Aviso, BotaoPrimario, CampoRegiao } from "@/components/AuthUi";
import { clearToken } from "@/lib/auth";
import {
  consultarTreinamento,
  emAndamento,
  listarTreinamentos,
  solicitarTreinamento,
  type ResumoTreinamento,
} from "@/lib/treinamentoApi";

// O backend devolve datas em UTC, às vezes sem o sufixo de fuso: sem ele o navegador as leria como horário local.
const formatarDataHora = (iso: string | null) =>
  iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleString("pt-BR") : "—";
const formatarData = (aaaaMmDd: string) => aaaaMmDd.split("-").reverse().join("/");
const inteiro = (valor: number | null) => (valor === null ? "—" : valor.toLocaleString("pt-BR"));
const percentual = (valor: number | null) =>
  valor === null ? "—" : valor.toLocaleString("pt-BR", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const duracao = (segundos: number) => {
  const minutos = Math.floor(segundos / 60);
  return minutos > 0 ? `${minutos} min ${Math.round(segundos % 60)} s` : `${segundos.toLocaleString("pt-BR")} s`;
};

const TIPO: Record<string, string> = { INICIAL: "Treinamento inicial", RETREINAMENTO: "Retreinamento" };

const STATUS: Record<ResumoTreinamento["status"], string> = {
  AGUARDANDO: "Aguardando",
  EXECUTANDO: "Em andamento",
  SUCESSO: "Concluído",
  FALHA: "Não concluído",
};

/** CU11-C2 passos 6 e 7 (RN26): o modelo novo e o vigente no mesmo período de teste, e a decisão. */
function Comparacao({ execucao }: { execucao: ResumoTreinamento }) {
  const novo = execucao.modelo?.versao;
  return (
    <div className="space-y-1 rounded-md bg-[#1A1525] p-2">
      <p className="text-[var(--color-text-title)]">
        {execucao.decisao === "SUBSTITUIDO"
          ? `O modelo novo (versão ${novo}) substituiu o vigente (versão ${execucao.versao_anterior}).`
          : `O modelo vigente (versão ${execucao.versao_anterior}) foi mantido; o novo (versão ${novo}) foi descartado.`}
      </p>
      <p className="text-[var(--color-text-secondary)]">
        No mesmo período de teste, nos {inteiro(execucao.itens_comparados)} itens avaliados pelos dois: mediana do MdAPE por
        item {percentual(execucao.mdape_novo)} no novo e {percentual(execucao.mdape_vigente)} no vigente.
      </p>
      <p className="text-[var(--color-text-secondary)]">
        Deixaram de ser elegíveis: {inteiro(execucao.deixaram_de_ser_elegiveis)} itens (
        {inteiro(execucao.liberados_que_deixaram_de_ser_elegiveis)} estavam liberados), com a projeção bloqueada.
      </p>
    </div>
  );
}

/** CU11-C1 passo 12 e CU11-C2 passo 10: resumo do treinamento, com os itens com projeção liberada, bloqueada e
 * ignorada (e, no retreinamento, a comparação com o modelo vigente). */
function Resumo({ execucao }: { execucao: ResumoTreinamento }) {
  const modelo = execucao.modelo;
  return (
    <div className="space-y-2 rounded-md border border-[var(--color-border)] p-3 text-sm" aria-live="polite">
      <p className="font-semibold text-[var(--color-text-title)]">
        {TIPO[execucao.tipo] ?? execucao.tipo} #{execucao.id_execucao} ({execucao.regiao}): {STATUS[execucao.status]}
      </p>
      {execucao.status === "SUCESSO" && execucao.decisao && <Comparacao execucao={execucao} />}
      {emAndamento(execucao) && (
        <p className="text-[var(--color-text-secondary)]">
          {execucao.andamento ?? "Aguardando o serviço de treinamento"}. O treinamento completo leva de 20 a 40 minutos; a tela
          acompanha o andamento.
        </p>
      )}

      {execucao.status === "SUCESSO" && (
        <>
          <p className="text-[var(--color-text-title)]">
            Projeção liberada: {inteiro(execucao.itens_liberados)} · Projeção bloqueada: {inteiro(execucao.itens_bloqueados)} ·
            Projeção ignorada: {inteiro(execucao.itens_ignorados)}
          </p>
          <ul className="list-inside list-disc text-[var(--color-text-secondary)]">
            <li>
              Bloqueados: {inteiro(execucao.bloqueados_acima_do_limiar)} acima do limiar,{" "}
              {inteiro(execucao.bloqueados_nao_supera_ingenuo)} sem superar o modelo ingênuo e{" "}
              {inteiro(execucao.bloqueados_avaliacao_insuficiente)} com avaliação insuficiente (menos de 30 dias avaliados).
            </li>
            <li>
              {inteiro(execucao.itens_elegiveis)} itens elegíveis à projeção, {inteiro(execucao.itens_treino)} no conjunto de
              treinamento; {inteiro(execucao.liberados_fora_do_treino)} liberados não integram o conjunto de treinamento.
            </li>
            <li>
              {inteiro(execucao.liberados_sem_amostra_de_treino)} liberados não têm nenhuma amostra no período de treinamento
              (lançados depois dele, não ajustaram os pesos do modelo).
            </li>
            {execucao.ultimo_dia && <li>Último dia encerrado da série usada: {formatarData(execucao.ultimo_dia)}.</li>}
          </ul>
        </>
      )}

      {modelo && (
        <div className="space-y-1 text-[var(--color-text-secondary)]">
          <p>
            Versão {modelo.versao}
            {modelo.vigente ? " (vigente)" : modelo.descartado ? " (descartada)" : ""}, treinada em {formatarDataHora(modelo.treinado_em)}: {modelo.epocas} épocas
            (melhor: {modelo.melhor_epoca}), {duracao(modelo.duracao_segundos)} de treino, {modelo.segundos_por_epoca.toLocaleString("pt-BR")} s
            por época.
          </p>
          <p>
            Períodos (RN25): treinamento a partir de {formatarData(modelo.data_inicio)}, validação a partir de{" "}
            {formatarData(modelo.corte_validacao)} e teste de {formatarData(modelo.corte_teste)} a {formatarData(modelo.data_fim)}.
          </p>
          <p>
            No período de teste ({inteiro(modelo.itens_avaliados)} itens avaliados): mediana do MdAPE por item{" "}
            {percentual(modelo.mediana_mdape)} (ingênuo: {percentual(modelo.mediana_mdape_ingenuo)}); mediana do MAPE{" "}
            {percentual(modelo.mediana_mape)} (ingênuo: {percentual(modelo.mediana_mape_ingenuo)});{" "}
            {inteiro(modelo.itens_supera_ingenuo)} itens superam o ingênuo.
          </p>
        </div>
      )}

      {execucao.avisos?.split("\n").map((aviso) => (
        <p key={aviso} className="text-[var(--color-text-secondary)]">
          Aviso: {aviso}
        </p>
      ))}

      {execucao.status === "FALHA" && (
        <>
          <p role="alert" className="text-[var(--color-negative)]">
            {execucao.tipo === "RETREINAMENTO"
              ? "Retreinamento não concluído: o modelo vigente e a situação dos itens foram mantidos."
              : execucao.mensagem}
            {execucao.tipo !== "RETREINAMENTO" && execucao.etapa_da_falha !== "SELECAO"
              ? " A versão vigente e a situação dos itens foram mantidas."
              : ""}
          </p>
          {execucao.itens_elegiveis !== null && (
            <p className="text-[var(--color-text-secondary)]">
              {inteiro(execucao.itens_elegiveis)} itens elegíveis à projeção, {inteiro(execucao.itens_treino)} no conjunto de
              treinamento.
            </p>
          )}
          {execucao.erro && (
            <p className="break-words text-xs text-[var(--color-text-secondary)]">
              Etapa {execucao.etapa_da_falha}: {execucao.erro}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function TreinamentoDoModelo({ token }: { token: string }) {
  const router = useRouter();
  const [regiao, setRegiao] = useState("US");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [execucao, setExecucao] = useState<ResumoTreinamento | null>(null);
  const [recentes, setRecentes] = useState<ResumoTreinamento[]>([]);

  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  }, [router]);

  const carregarRecentes = useCallback(async () => {
    const resultado = await listarTreinamentos(token);
    if (resultado.ok) setRecentes(resultado.data);
  }, [token]);

  // Ao abrir a tela, retoma o acompanhamento de um treinamento que ainda esteja rodando.
  useEffect(() => {
    let cancelado = false;
    listarTreinamentos(token).then((resultado) => {
      if (cancelado || !resultado.ok) return;
      setRecentes(resultado.data);
      const rodando = resultado.data.find((item) => emAndamento(item));
      if (rodando) setExecucao((atual) => atual ?? rodando);
    });
    return () => {
      cancelado = true;
    };
  }, [token]);

  // Acompanha o treinamento enquanto ele roda no serviço `modelo`.
  const idEmAndamento = emAndamento(execucao) && execucao ? execucao.id_execucao : null;
  useEffect(() => {
    if (idEmAndamento === null) return;
    let cancelado = false;
    const temporizador = setInterval(async () => {
      const resultado = await consultarTreinamento(token, idEmAndamento);
      if (cancelado) return;
      if (resultado.ok) {
        const atual = resultado.data;
        setErro(null);
        setExecucao(atual);
        setRecentes((lista) => lista.map((item) => (item.id_execucao === atual.id_execucao ? atual : item)));
        if (!emAndamento(atual)) carregarRecentes();
      } else if (resultado.status === 401) {
        sessaoExpirada();
      } else {
        setErro(resultado.message);
      }
    }, 5000);
    return () => {
      cancelado = true;
      clearInterval(temporizador);
    };
  }, [idEmAndamento, token, carregarRecentes, sessaoExpirada]);

  const handleTreinar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    const resultado = await solicitarTreinamento(token, regiao);
    setEnviando(false);
    if (resultado.ok) {
      setExecucao(resultado.data);
      carregarRecentes();
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErro(resultado.message); // FA2: "Já existe um treinamento em andamento"
    }
  };

  return (
    <>
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
        Treina o modelo preditivo global com os itens do conjunto de treinamento (elegíveis à projeção e aptos ao treinamento) e avalia,
        no período de teste, todos os itens elegíveis, liberando a projeção dos que atingem o limiar de acurácia (RN10).
      </p>

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleTreinar} noValidate className="max-w-md">
        <CampoRegiao value={regiao} onChange={setRegiao} />
        <BotaoPrimario carregando={enviando || idEmAndamento !== null}>
          {enviando ? "Enviando..." : idEmAndamento !== null ? "Treinamento em andamento..." : "Executar treinamento inicial"}
        </BotaoPrimario>
      </form>

      {execucao && (
        <div className="mt-6">
          <Resumo execucao={execucao} />
        </div>
      )}

      {recentes.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-2 text-lg font-semibold text-[var(--color-text-title)]">Treinamentos recentes</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[var(--color-text-secondary)]">
                <tr>
                  <th className="py-1 pr-3 font-normal">Pedido</th>
                  <th className="py-1 pr-3 font-normal">Tipo</th>
                  <th className="py-1 pr-3 font-normal">Região</th>
                  <th className="py-1 pr-3 font-normal">Situação</th>
                  <th className="py-1 pr-3 text-right font-normal">Versão</th>
                  <th className="py-1 pr-3 font-normal">Decisão</th>
                  <th className="py-1 pr-3 text-right font-normal">Liberados</th>
                  <th className="py-1 pr-3 text-right font-normal">Bloqueados</th>
                  <th className="py-1 text-right font-normal">Ignoradas</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-main)]">
                {recentes.map((item) => (
                  <tr key={item.id_execucao} className="border-t border-[var(--color-border)]">
                    <td className="py-1 pr-3">
                      <button type="button" onClick={() => setExecucao(item)} className="text-[var(--color-cta)] hover:underline">
                        {formatarDataHora(item.solicitado_em)}
                      </button>
                    </td>
                    <td className="py-1 pr-3">{TIPO[item.tipo] ?? item.tipo}</td>
                    <td className="py-1 pr-3">{item.regiao}</td>
                    <td className="py-1 pr-3">{STATUS[item.status]}</td>
                    <td className="py-1 pr-3 text-right">{item.modelo ? item.modelo.versao : "—"}</td>
                    <td className="py-1 pr-3">
                      {item.decisao === "SUBSTITUIDO" ? "Substituiu o vigente" : item.decisao === "MANTIDO" ? "Vigente mantido" : "—"}
                    </td>
                    <td className="py-1 pr-3 text-right">{inteiro(item.itens_liberados)}</td>
                    <td className="py-1 pr-3 text-right">{inteiro(item.itens_bloqueados)}</td>
                    <td className="py-1 text-right">{inteiro(item.itens_ignorados)}</td>
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

/** CU11-C1 – Executar treinamento inicial (Admin). */
export default function TreinamentoPage() {
  return (
    <AdminPagina titulo="Treinamento do modelo" href="/admin/treinamento">
      {(token) => <TreinamentoDoModelo token={token} />}
    </AdminPagina>
  );
}
