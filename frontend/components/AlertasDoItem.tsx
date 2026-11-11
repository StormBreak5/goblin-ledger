"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Pencil, Plus, Star, Trash2 } from "lucide-react";
import Dialogo from "@/components/Dialogo";
import FormularioDeAlerta from "@/components/FormularioDeAlerta";
import Toast from "@/components/Toast";
import { clearToken } from "@/lib/auth";
import {
  alertaParaEditar, alterarAlerta, criarAlerta, excluirAlerta, listarAlertas, MSG_CONFIRMAR_EXCLUSAO, novoAlerta,
  ROTULO_DO_CANAL, ROTULO_DO_TIPO, type Alerta, type AlertasDoItem as Lista, type DadosDoAlerta,
} from "@/lib/alertasApi";
import type { ApiFailure } from "@/lib/authApi";
import { formatarMoeda, partesDaMoeda } from "@/lib/moeda";
import { novoAviso, type AvisoDaTela } from "@/lib/useAcoesDeFavorito";

interface Props {
  token: string;
  itemId: number;
  itemNome: string;
  iconUrl: string | null;
  favorito: boolean;
  /** CU06-C1, para o CU07-C1-FA1: devolve se o item ficou nos favoritos. */
  aoFavoritar: () => Promise<boolean>;
}

interface Formulario {
  modo: "novo" | "editar";
  idAlerta: number | null;
  titulo: string;
  valorDeMercado: number | null;
  inicial: DadosDoAlerta;
}

const VAZIO: DadosDoAlerta = { tipo: null, canal: null, ouro: "", prata: "", cobre: "" };

function dadosDoAlerta(alerta: Alerta): DadosDoAlerta {
  const { ouro, prata, cobre } = partesDaMoeda(alerta.preco_alvo);
  return { tipo: alerta.tipo, canal: alerta.canal, ouro: String(ouro), prata: String(prata), cobre: String(cobre) };
}

function preco(cobre: number): string {
  try {
    return formatarMoeda(cobre);
  } catch {
    return "—";
  }
}

/** "Disparado em dd/mm/aaaa às hh:mm", no fuso de quem vê (como o CU04). */
function quando(instante: string | null): string {
  if (!instante) return "";
  const data = new Date(instante);
  if (Number.isNaN(data.getTime())) return "";
  return ` em ${data.toLocaleDateString("pt-BR")} às ${data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

/**
 * CU07 – a seção "Alertas de preço" da tela do item (Figura 15), só para o usuário autenticado: criar (C1), alterar ou
 * reativar (C2) e excluir (C3). As regras (favorito, RN08, validação e conversão para Cobre) e as mensagens são do backend.
 */
export default function AlertasDoItem({ token, itemId, itemNome, iconUrl, favorito, aoFavoritar }: Props) {
  const router = useRouter();
  const [lista, setLista] = useState<Lista | null>(null);
  const [formulario, setFormulario] = useState<Formulario | null>(null);
  const [erroDoFormulario, setErroDoFormulario] = useState<string | null>(null);
  const [bloqueio, setBloqueio] = useState<{ texto: string; foraDosFavoritos: boolean } | null>(null);
  const [exclusao, setExclusao] = useState<Alerta | null>(null);
  const [aviso, setAviso] = useState<AvisoDaTela | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const fecharAviso = useCallback(() => setAviso(null), []);

  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  }, [router]);

  const carregar = useCallback(async () => {
    const resultado = await listarAlertas(token, itemId);
    if (resultado.ok) setLista(resultado.data);
    else if (resultado.status === 401) sessaoExpirada();
    else setAviso(novoAviso(resultado.message, "erro"));
  }, [token, itemId, sessaoExpirada]);

  // A seção acompanha o favorito: removido o item (CU06-C2), os alertas dele também saíram.
  useEffect(() => {
    const inicial = async () => {
      await carregar();
    };
    inicial();
  }, [carregar, favorito]);

  const falha = (resultado: ApiFailure) => {
    if (resultado.status === 401) sessaoExpirada();
    else setAviso(novoAviso(resultado.message, "erro"));
  };

  // C1 passos 2 a 4: o backend confere o favorito (FA1) e a cota (FA2) antes do formulário.
  const abrirNovo = async (aindaForaDosFavoritos: boolean) => {
    setOcupado(true);
    const resultado = await novoAlerta(token, itemId);
    setOcupado(false);
    if (resultado.ok) {
      setBloqueio(null);
      setErroDoFormulario(null);
      setFormulario({ modo: "novo", idAlerta: null, titulo: "Criar alerta de preço", valorDeMercado: resultado.data.market_value, inicial: VAZIO });
    } else if (resultado.status === 409) {
      setBloqueio({ texto: resultado.message, foraDosFavoritos: aindaForaDosFavoritos });
    } else {
      falha(resultado);
    }
  };

  // C1-FA1, 1.3 e 1.4: favoritado o item (CU06-C1), o fluxo volta ao passo 3 (a cota) e abre o formulário.
  const favoritarEContinuar = async () => {
    if (await aoFavoritar()) await abrirNovo(false);
  };

  // C2 passos 1 e 2 (e FA1/FA2: o disparado só abre para reativar abaixo da cota).
  const abrirEdicao = async (alerta: Alerta) => {
    setOcupado(true);
    const resultado = await alertaParaEditar(token, alerta.id_alerta);
    setOcupado(false);
    if (resultado.ok && resultado.data.alerta) {
      const atual = resultado.data.alerta;
      setBloqueio(null);
      setErroDoFormulario(null);
      setFormulario({
        modo: "editar", idAlerta: atual.id_alerta, valorDeMercado: resultado.data.market_value, inicial: dadosDoAlerta(atual),
        titulo: atual.situacao === "DISPARADO" ? "Reativar alerta de preço" : "Alterar alerta de preço",
      });
    } else if (!resultado.ok && resultado.status === 409) {
      setBloqueio({ texto: resultado.message, foraDosFavoritos: false });
    } else if (!resultado.ok) {
      falha(resultado);
    }
  };

  // C1 passos 6 a 8 / C2 passos 4 a 6. FA3: a mensagem fica no formulário, aberto. FE1: fecha e avisa.
  const salvar = async (dados: DadosDoAlerta) => {
    if (!formulario) return;
    setOcupado(true);
    const resultado = formulario.modo === "novo"
      ? await criarAlerta(token, itemId, dados)
      : await alterarAlerta(token, formulario.idAlerta ?? 0, dados);
    setOcupado(false);
    if (resultado.ok) {
      setFormulario(null);
      setAviso(novoAviso(resultado.data.message, "sucesso"));
      await carregar();
    } else if (resultado.status === 422) {
      setErroDoFormulario(resultado.message);
    } else if (resultado.status === 409) {
      setFormulario(null);
      setBloqueio({ texto: resultado.message, foraDosFavoritos: !favorito });
    } else {
      setFormulario(null);
      falha(resultado);
    }
  };

  // C3 passos 3 a 5 (a confirmação é do passo 2; cancelar é o FA1).
  const excluir = async () => {
    if (!exclusao) return;
    setOcupado(true);
    const resultado = await excluirAlerta(token, exclusao.id_alerta);
    setOcupado(false);
    setExclusao(null);
    if (resultado.ok) {
      setAviso(novoAviso(resultado.data.message, "sucesso"));
      await carregar();
    } else {
      falha(resultado); // FE1: o alerta é mantido
    }
  };

  const alertas = lista?.alertas ?? [];
  return (
    <section aria-label="Alertas de preço" className="mt-8 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-translucent)] p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold text-[var(--color-text-title)]">
            <Bell className="h-5 w-5 text-[var(--color-cta)]" aria-hidden="true" /> Alertas de preço
          </h2>
          {lista && (
            <p data-testid="cota" className="mt-1 text-sm text-[var(--color-text-secondary)]">
              Você tem {lista.ativos_do_usuario} de {lista.limite} alertas ativos em todos os seus itens
            </p>
          )}
        </div>
        <button type="button" onClick={() => abrirNovo(!favorito)} disabled={ocupado}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--color-cta)] px-4 py-2 text-sm font-semibold text-[#161124] hover:bg-[var(--color-cta-hover)] disabled:opacity-60">
          <Plus className="h-4 w-4" aria-hidden="true" /> Criar alerta
        </button>
      </div>

      {bloqueio && (
        <div role="alert" className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-[var(--color-cta)]/50 bg-[var(--color-cta)]/10 px-4 py-3 text-sm text-[var(--color-cta)]">
          <span>{bloqueio.texto}</span>
          {bloqueio.foraDosFavoritos && (
            <button type="button" onClick={favoritarEContinuar} disabled={ocupado}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--color-cta)]/70 px-3 py-1 font-medium hover:bg-[var(--color-cta)]/10">
              <Star className="h-4 w-4" aria-hidden="true" /> Adicionar aos favoritos
            </button>
          )}
        </div>
      )}

      {alertas.length > 0 && (
        <table className="mt-5 w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
              <th className="py-2 font-medium">Tipo de gatilho</th>
              <th className="py-2 font-medium">Preço-alvo</th>
              <th className="py-2 font-medium">Canal</th>
              <th className="py-2 font-medium">Situação</th>
              <th className="py-2 text-right font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            {alertas.map((alerta) => {
              const disparado = alerta.situacao === "DISPARADO";
              return (
                <tr key={alerta.id_alerta} data-alerta={alerta.id_alerta} className="border-b border-[var(--color-border)] last:border-0">
                  <td className="py-3 text-[var(--color-text-main)]">
                    {ROTULO_DO_TIPO[alerta.tipo].nome}{" "}
                    <span className="text-[var(--color-text-secondary)]">({ROTULO_DO_TIPO[alerta.tipo].gatilho})</span>
                  </td>
                  <td className="py-3 font-semibold text-[var(--color-cta)]">{preco(alerta.preco_alvo)}</td>
                  <td className="py-3 text-[var(--color-text-main)]">{ROTULO_DO_CANAL[alerta.canal]}</td>
                  <td className="py-3" data-testid="situacao">
                    {disparado ? (
                      <span className="text-[var(--color-text-secondary)]">
                        <span className="rounded bg-white/10 px-2 py-0.5 font-medium text-[var(--color-text-main)]">Disparado</span>
                        <span className="mt-1 block text-xs">{quando(alerta.disparado_em)}</span>
                      </span>
                    ) : (
                      <span className="rounded bg-[var(--color-positive)]/15 px-2 py-0.5 font-medium text-[var(--color-positive)]">Ativo</span>
                    )}
                  </td>
                  <td className="py-3 text-right whitespace-nowrap">
                    <button type="button" onClick={() => abrirEdicao(alerta)} disabled={ocupado}
                      className="mr-4 inline-flex items-center gap-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)]">
                      <Pencil className="h-4 w-4" aria-hidden="true" /> {disparado ? "Editar e reativar" : "Editar"}
                    </button>
                    <button type="button" onClick={() => setExclusao(alerta)} disabled={ocupado}
                      className="inline-flex items-center gap-1 text-[var(--color-text-secondary)] hover:text-[var(--color-negative)]">
                      <Trash2 className="h-4 w-4" aria-hidden="true" /> Excluir
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {formulario && (
        <FormularioDeAlerta
          key={`${formulario.modo}-${formulario.idAlerta ?? "novo"}`}
          titulo={formulario.titulo}
          itemNome={itemNome}
          iconUrl={iconUrl}
          valorDeMercado={formulario.valorDeMercado}
          inicial={formulario.inicial}
          erro={erroDoFormulario}
          ocupado={ocupado}
          aoSalvar={salvar}
          aoCancelar={() => setFormulario(null)}
        />
      )}
      {exclusao && (
        <Dialogo titulo="Excluir alerta" aoConfirmar={excluir} aoCancelar={() => setExclusao(null)} textoConfirmar="Excluir" ocupado={ocupado}>
          <p className="text-sm text-[var(--color-text-main)]">{MSG_CONFIRMAR_EXCLUSAO}</p>
        </Dialogo>
      )}
      {aviso && <Toast key={aviso.id} texto={aviso.texto} tom={aviso.tom} onFechar={fecharAviso} />}
    </section>
  );
}
