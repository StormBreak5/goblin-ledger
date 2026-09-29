"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AdminPagina from "@/components/AdminPagina";
import { Aviso, BotaoPrimario } from "@/components/AuthUi";
import { clearToken } from "@/lib/auth";
import {
  consultarCobertura,
  validarCobertura,
  type FiltroDeSituacao,
  type ItemCobertura,
  type ResumoCobertura,
} from "@/lib/historicoApi";

const inteiro = (valor: number) => valor.toLocaleString("pt-BR");
const dataBr = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const momento = (iso: string | null) =>
  iso ? new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleString("pt-BR") : "—";

function meses(dias: number): string {
  return `${(dias / 30.4).toFixed(1).replace(".", ",")} meses`;
}

function Coberturas({ token }: { token: string }) {
  const router = useRouter();
  const [validando, setValidando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ResumoCobertura | null>(null);
  const [itens, setItens] = useState<ItemCobertura[]>([]);
  const [filtro, setFiltro] = useState<FiltroDeSituacao>("");

  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  }, [router]);

  // Mostra a última validação, se já houve alguma.
  useEffect(() => {
    let cancelado = false;
    consultarCobertura(token, "", 1).then((resultado) => {
      if (cancelado || !resultado.ok) return;
      setResumo(resultado.data);
      setItens(resultado.data.itens);
    });
    return () => {
      cancelado = true;
    };
  }, [token]);

  const handleValidar = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidando(true);
    setErro(null);
    const resultado = await validarCobertura(token);
    setValidando(false);
    if (resultado.ok) {
      setResumo(resultado.data);
      setItens(resultado.data.itens);
      setFiltro("");
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErro(resultado.message); // FE1: "Não foi possível concluir a validação no momento. Tente novamente mais tarde"
    }
  };

  const aplicarFiltro = async (novo: FiltroDeSituacao) => {
    setFiltro(novo);
    const resultado = await consultarCobertura(token, novo, 1);
    if (resultado.ok) {
      setResumo(resultado.data);
      setItens(resultado.data.itens);
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErro(resultado.message);
    }
  };

  const carregarMais = async () => {
    if (!resumo) return;
    const resultado = await consultarCobertura(token, filtro, resumo.pagina + 1);
    if (resultado.ok) {
      setResumo(resultado.data);
      setItens((atuais) => [...atuais, ...resultado.data.itens]);
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErro(resultado.message);
    }
  };

  const totalDoFiltro = filtro === "APTO" ? (resumo?.aptos ?? 0) : filtro === "INAPTO" ? (resumo?.inaptos ?? 0) : (resumo?.total ?? 0);

  return (
    <>
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
        Verifica se o histórico de cada item ativo tem um período contínuo de pelo menos 6 meses de registros, o mínimo para o
        treinamento inicial do modelo preditivo. Os itens inaptos continuam com a predição bloqueada. Lacunas curtas na série não
        interrompem o período.
      </p>

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={handleValidar} noValidate className="max-w-md">
        <BotaoPrimario carregando={validando}>{validando ? "Validando..." : "Validar cobertura histórica"}</BotaoPrimario>
      </form>

      {resumo && resumo.total > 0 && (
        <section className="mt-6" aria-live="polite">
          <p className="text-sm text-[var(--color-text-title)]">
            <span className="text-[var(--color-positive)]">Aptos ao treinamento: {inteiro(resumo.aptos)}</span> ·{" "}
            <span className="text-[var(--color-negative)]">Inaptos: {inteiro(resumo.inaptos)}</span> · Total: {inteiro(resumo.total)}
          </p>
          <p className="mb-3 text-xs text-[var(--color-text-secondary)]">Validado em {momento(resumo.validado_em)}.</p>

          <div className="mb-3 flex gap-3 text-sm" role="group" aria-label="Filtrar por situação">
            {(
              [
                ["", "Todos"],
                ["APTO", "Aptos"],
                ["INAPTO", "Inaptos"],
              ] as [FiltroDeSituacao, string][]
            ).map(([valor, rotulo]) => (
              <button
                key={valor || "todos"}
                type="button"
                onClick={() => aplicarFiltro(valor)}
                aria-pressed={filtro === valor}
                className={filtro === valor ? "font-semibold text-[var(--color-text-title)]" : "text-[var(--color-cta)] hover:underline"}
              >
                {rotulo}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[var(--color-text-secondary)]">
                <tr>
                  <th className="py-1 pr-3 font-normal">Item</th>
                  <th className="py-1 pr-3 font-normal">Situação</th>
                  <th className="py-1 pr-3 text-right font-normal">Período contínuo</th>
                  <th className="py-1 pr-3 font-normal">De</th>
                  <th className="py-1 font-normal">Até</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-main)]">
                {itens.map((item) => (
                  <tr key={item.item_id} className="border-t border-[var(--color-border)]">
                    <td className="py-1 pr-3">
                      {item.nome ?? "—"} <span className="text-[var(--color-text-secondary)]">#{item.item_id}</span>
                    </td>
                    <td className={`py-1 pr-3 ${item.apto ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"}`}>{item.situacao}</td>
                    <td className="py-1 pr-3 text-right whitespace-nowrap">
                      {inteiro(item.periodo_continuo_dias)} dias ({meses(item.periodo_continuo_dias)})
                    </td>
                    <td className="py-1 pr-3 whitespace-nowrap">{dataBr(item.inicio_periodo)}</td>
                    <td className="py-1 whitespace-nowrap">{dataBr(item.fim_periodo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {itens.length < totalDoFiltro && (
            <button type="button" onClick={carregarMais} className="mt-3 text-sm text-[var(--color-cta)] hover:underline">
              Carregar mais
            </button>
          )}
        </section>
      )}

      {resumo && resumo.total === 0 && !erro && (
        <p className="mt-6 text-sm text-[var(--color-text-secondary)]">Nenhuma validação feita ainda. Importe o histórico e valide.</p>
      )}
    </>
  );
}

/** CU10-C3 – Validar cobertura histórica dos itens (Admin). */
export default function CoberturaPage() {
  return (
    <AdminPagina titulo="Cobertura histórica" href="/admin/cobertura">
      {(token) => <Coberturas token={token} />}
    </AdminPagina>
  );
}
