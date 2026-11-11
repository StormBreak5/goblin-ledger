"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import AlertasDoItem from "@/components/AlertasDoItem";
import AvisosDoHistorico from "@/components/AvisosDoHistorico";
import ControleDeFavorito from "@/components/ControleDeFavorito";
import Dialogo from "@/components/Dialogo";
import Header from "@/components/Header";
import PrecoAtualDoItem from "@/components/PrecoAtualDoItem";
import PriceChart from "@/components/PriceChart";
import ProjecaoDoItem from "@/components/ProjecaoDoItem";
import Toast from "@/components/Toast";
import { useAuthToken } from "@/lib/auth";
import { fetchItem, type ItemDetail } from "@/lib/itemSearch";
import { projecaoExibida } from "@/lib/projecaoDoItem";
import { useAcoesDeFavorito } from "@/lib/useAcoesDeFavorito";
import { useHistoricoDoItem, usePrecoAtual } from "@/lib/useHistoricoDoItem";
import { useProjecaoDoItem, useProjecaoVisivel } from "@/lib/useProjecaoDoItem";

const JANELAS = [
  { value: "14D", label: "14 Dias" },
  { value: "30D", label: "1 Mês" },
  { value: "90D", label: "3 Meses" },
  { value: "365D", label: "1 Ano" },
  { value: "ALL", label: "Tudo" },
];

export default function ItemDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // CU03-C3: nome e ícone vêm do backend; item removido durante a navegação volta para a busca (C3-FE1).
  // CU06: com a sessão, o backend também diz se o item está nos favoritos.
  const token = useAuthToken();
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);
  const itemName = item?.name ?? `Item ${id}`;
  const iconUrl = item?.icon_url ?? null;

  useEffect(() => {
    const controller = new AbortController();
    fetchItem(id, controller.signal, token).then((lookup) => {
      if (controller.signal.aborted) return;
      if (lookup.status === "found") {
        setItem(lookup.item);
      } else if (lookup.status === "unavailable") {
        router.replace("/?aviso=item-indisponivel");
      } else {
        setItemError(lookup.message);
      }
    });
    return () => controller.abort();
  }, [id, router, token]);

  // CU06-C1 e C2: o controle "Favoritar"/"Favoritado", com a confirmação do C2-FA1 num diálogo.
  const aoMudarFavorito = useCallback((_: number, favorito: boolean) => {
    setItem((atual) => (atual ? { ...atual, favorito } : atual));
  }, []);
  const favoritos = useAcoesDeFavorito(aoMudarFavorito);
  const favorito = item?.favorito ?? false;

  // CU04: a série, os avisos (Dados Desatualizados / Dados limitados / sem histórico) e o preço atual vêm do backend.
  const { dados, janela, pendente, carregando, erro, toast, mudarJanela, fecharToast } = useHistoricoDoItem(id);
  const { preco, carregando: carregandoPreco } = usePrecoAtual(id);
  const semHistorico = dados?.avisos.find((aviso) => aviso.codigo === "SEM_HISTORICO");

  // CU05: a projeção, com a situação e os textos vindos do backend. Pré-condição: o histórico está exibido na tela.
  const estadoDaProjecao = useProjecaoDoItem(id);
  const [projecaoVisivel, alternarProjecao] = useProjecaoVisivel(); // C3
  // C2: o dia em destaque, apontado pelo ponto do gráfico ou pela linha da tabela.
  const [destaque, setDestaque] = useState<{ dia: string; pelaTabela: boolean } | null>(null);
  const destacarPeloGrafico = useCallback((dia: string | null) => setDestaque(dia ? { dia, pelaTabela: false } : null), []);
  const destacarPelaTabela = useCallback((dia: string | null) => setDestaque(dia ? { dia, pelaTabela: true } : null), []);
  const historicoExibido = !erro && (dados?.pontos.length ?? 0) > 0;
  const projecao = useMemo(
    () => (historicoExibido ? projecaoExibida(estadoDaProjecao.projecao) : null),
    [historicoExibido, estadoDaProjecao.projecao],
  );

  return (
    <div className="min-h-screen bg-[var(--color-background)] flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {iconUrl && (
              <img src={iconUrl} alt={itemName} className="w-16 h-16 rounded-lg border border-[var(--color-border)] shadow-md" />
            )}
            <div>
              <h1 className="text-3xl font-bold text-[var(--color-text-title)] capitalize">
                {itemName}
              </h1>
              {itemError && (
                <p role="alert" className="mt-1 text-sm text-[var(--color-negative)]">{itemError}</p>
              )}
              {item && (
                <ControleDeFavorito
                  favorito={favorito}
                  ocupado={favoritos.ocupado}
                  aoAlternar={() => (favorito ? favoritos.remover(item.id) : favoritos.adicionar(item.id))}
                />
              )}
            </div>
          </div>

          {carregandoPreco ? (
            <p className="text-[var(--color-text-secondary)] text-sm animate-pulse">Consultando Casa de Leilões...</p>
          ) : preco ? (
            <PrecoAtualDoItem preco={preco} />
          ) : null}
        </div>

        <div className="flex justify-end gap-2 mb-4">
          {JANELAS.map((w) => (
            <button
              key={w.value}
              onClick={() => mudarJanela(w.value)}
              aria-pressed={(pendente ?? janela) === w.value}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                (pendente ?? janela) === w.value
                  ? 'bg-[var(--color-cta)] text-[#161124] font-bold'
                  : 'bg-[var(--color-surface-solid)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)] border border-[var(--color-border)]'
              }`}
            >
              {w.label}
            </button>
          ))}
          {projecao && (
            <button
              onClick={alternarProjecao}
              aria-pressed={projecaoVisivel}
              className={`ml-2 flex items-center gap-2 px-3 py-1 rounded text-sm border transition-colors ${
                projecaoVisivel
                  ? 'border-[var(--color-projection)] text-[var(--color-projection)] bg-[var(--color-projection)]/10'
                  : 'border-[var(--color-border)] text-[var(--color-text-secondary)] bg-[var(--color-surface-solid)] hover:text-[var(--color-text-main)]'
              }`}
            >
              <span aria-hidden className={`relative inline-block h-3.5 w-6 rounded-full transition-colors ${projecaoVisivel ? 'bg-[var(--color-projection)]' : 'bg-[var(--color-border)]'}`}>
                <span className={`absolute top-0.5 h-2.5 w-2.5 rounded-full bg-white transition-all ${projecaoVisivel ? 'left-3' : 'left-0.5'}`} />
              </span>
              Projeção
            </button>
          )}
        </div>

        {dados && <AvisosDoHistorico avisos={dados.avisos} />}

        <div className={`h-[500px] w-full transition-opacity ${carregando && dados ? "opacity-60" : ""}`}>
          {carregando && !dados ? (
            <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)]">
              <div className="animate-pulse flex flex-col items-center">
                <div className="h-8 w-8 rounded-full border-4 border-[var(--color-cta)] border-t-transparent animate-spin mb-4"></div>
                <p className="text-[var(--color-text-secondary)]">Carregando dados da Auction House...</p>
              </div>
            </div>
          ) : erro ? (
            <div role="alert" className="w-full h-full flex flex-col items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-negative)]/50 p-6 text-center">
              <p className="text-[var(--color-negative)] font-medium">{erro}</p>
            </div>
          ) : (
            <PriceChart
              data={dados?.pontos ?? []}
              mensagemVazia={semHistorico?.texto}
              projecao={projecao && projecaoVisivel ? projecao : null}
              diaDestacado={destaque?.dia ?? null}
              aoDestacarDia={destacarPeloGrafico}
              dicaNoPonto={destaque?.pelaTabela ?? false}
            />
          )}
        </div>

        {historicoExibido && (
          <ProjecaoDoItem estado={estadoDaProjecao} visivel={projecaoVisivel} diaDestacado={destaque?.dia ?? null}
            aoDestacarDia={destacarPelaTabela} />
        )}

        {/* CU07: a seção "Alertas de preço", só para o usuário autenticado. */}
        {token && item && (
          <AlertasDoItem token={token} itemId={item.id} itemNome={itemName} iconUrl={iconUrl} favorito={favorito}
            aoFavoritar={() => favoritos.adicionar(item.id)} />
        )}
      </main>
      {toast && <Toast texto={toast} onFechar={fecharToast} />}
      {favoritos.aviso && <Toast key={favoritos.aviso.id} texto={favoritos.aviso.texto} tom={favoritos.aviso.tom} onFechar={favoritos.fecharAviso} />}
      {favoritos.confirmacao && (
        <Dialogo titulo="Remover dos favoritos" aoConfirmar={favoritos.confirmar} aoCancelar={favoritos.cancelar}
          textoConfirmar="Remover" ocupado={favoritos.ocupado}>
          <p className="text-sm text-[var(--color-text-main)]">{favoritos.confirmacao.texto}</p>
        </Dialogo>
      )}
    </div>
  );
}
