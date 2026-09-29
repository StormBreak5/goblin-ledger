"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AdminPagina from "@/components/AdminPagina";
import { Aviso, BotaoPrimario, Campo } from "@/components/AuthUi";
import { clearToken } from "@/lib/auth";
import {
  cadastrarEvento,
  extrairEventos,
  FONTES_DE_EVENTOS,
  listarEventos,
  TIPOS_DE_EVENTO,
  type EventoJogo,
  type FonteDeEventos,
  type ResumoExtracao,
} from "@/lib/historicoApi";

const selectClass =
  "block w-full rounded-md border border-[var(--color-border)] bg-[#1A1525] px-3 py-2 text-[var(--color-text-main)] focus:outline-none focus:ring-1 focus:ring-[var(--color-cta)] disabled:opacity-60";
const rotuloDoTipo = (tipo: string) => TIPOS_DE_EVENTO.find((item) => item.valor === tipo)?.rotulo ?? tipo;

interface ResultadoDaFonte {
  fonte: FonteDeEventos;
  resumo?: ResumoExtracao;
  erro?: string;
}

function TabelaDeEventos({ eventos }: { eventos: EventoJogo[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-[var(--color-text-secondary)]">
          <tr>
            <th className="py-1 pr-3 font-normal">Início</th>
            <th className="py-1 pr-3 font-normal">Fim</th>
            <th className="py-1 pr-3 font-normal">Tipo</th>
            <th className="py-1 pr-3 font-normal">Nome</th>
            <th className="py-1 pr-3 font-normal">Região</th>
            <th className="py-1 font-normal">Origem</th>
          </tr>
        </thead>
        <tbody className="text-[var(--color-text-main)]">
          {eventos.map((evento) => (
            <tr key={evento.id_evento} className="border-t border-[var(--color-border)]">
              <td className="py-1 pr-3 whitespace-nowrap">{evento.data_inicio}</td>
              <td className="py-1 pr-3 whitespace-nowrap">{evento.data_fim ?? "—"}</td>
              <td className="py-1 pr-3">{rotuloDoTipo(evento.tipo)}</td>
              <td className="py-1 pr-3">{evento.nome}</td>
              <td className="py-1 pr-3">{evento.regiao}</td>
              <td className="py-1 text-[var(--color-text-secondary)]">{evento.origem}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Eventos({ token }: { token: string }) {
  const router = useRouter();
  const sessaoExpirada = useCallback(() => {
    clearToken();
    router.replace("/login?aviso=sessao-expirada");
  }, [router]);

  // Extração (passos 1 a 6)
  const [fonte, setFonte] = useState<FonteDeEventos | "TODAS">("EXPANSOES");
  const [url, setUrl] = useState("");
  const [extraindo, setExtraindo] = useState(false);
  const [resultados, setResultados] = useState<ResultadoDaFonte[]>([]);

  // Cadastro manual (FA2)
  const [nome, setNome] = useState("");
  const [versao, setVersao] = useState("");
  const [tipo, setTipo] = useState("PATCH");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [regiao, setRegiao] = useState("GLOBAL");
  const [cadastrando, setCadastrando] = useState(false);
  const [erroManual, setErroManual] = useState<string | null>(null);
  const [camposInvalidos, setCamposInvalidos] = useState<string[]>([]);
  const [avisoManual, setAvisoManual] = useState<string | null>(null);

  // Relação de eventos registrados
  const [filtro, setFiltro] = useState("");
  const [eventos, setEventos] = useState<EventoJogo[]>([]);
  const [total, setTotal] = useState(0);
  const [erroLista, setErroLista] = useState<string | null>(null);

  const carregar = useCallback(
    async (tipoFiltrado: string, deslocamento: number) => {
      const resultado = await listarEventos(token, tipoFiltrado, deslocamento);
      if (resultado.ok) {
        setErroLista(null);
        setTotal(resultado.data.total);
        setEventos((atuais) => (deslocamento === 0 ? resultado.data.eventos : [...atuais, ...resultado.data.eventos]));
      } else if (resultado.status === 401) {
        sessaoExpirada();
      } else {
        setErroLista(resultado.message);
      }
    },
    [token, sessaoExpirada],
  );

  useEffect(() => {
    let cancelado = false;
    listarEventos(token, filtro, 0).then((resultado) => {
      if (cancelado) return;
      if (resultado.ok) {
        setErroLista(null);
        setTotal(resultado.data.total);
        setEventos(resultado.data.eventos);
      } else {
        setErroLista(resultado.message);
      }
    });
    return () => {
      cancelado = true;
    };
  }, [token, filtro]);

  const fonteComPagina = fonte !== "TODAS" && (FONTES_DE_EVENTOS.find((item) => item.valor === fonte)?.pagina ?? false);

  const handleExtrair = async (e: React.FormEvent) => {
    e.preventDefault();
    setExtraindo(true);
    setResultados([]);
    const fontes = fonte === "TODAS" ? FONTES_DE_EVENTOS.map((item) => item.valor) : [fonte];
    const obtidos: ResultadoDaFonte[] = [];
    for (const atual of fontes) {
      const resultado = await extrairEventos(token, atual, fonte === "TODAS" ? "" : url);
      if (!resultado.ok && resultado.status === 401) {
        sessaoExpirada();
        return;
      }
      obtidos.push(resultado.ok ? { fonte: atual, resumo: resultado.data } : { fonte: atual, erro: resultado.message });
      setResultados([...obtidos]);
    }
    setExtraindo(false);
    carregar(filtro, 0);
  };

  const handleCadastrar = async (e: React.FormEvent) => {
    e.preventDefault();
    setCadastrando(true);
    setErroManual(null);
    setCamposInvalidos([]);
    setAvisoManual(null);
    const resultado = await cadastrarEvento(token, { nome, versao, tipo, data_inicio: dataInicio, data_fim: dataFim, regiao });
    setCadastrando(false);
    if (resultado.ok) {
      setAvisoManual(
        resultado.data.eventos_registrados > 0 ? "Evento cadastrado." : "Este evento já estava registrado; foi ignorado.",
      );
      setNome("");
      setVersao("");
      setDataInicio("");
      setDataFim("");
      carregar(filtro, 0);
    } else if (resultado.status === 401) {
      sessaoExpirada();
    } else {
      setErroManual(resultado.message); // FA2: "Verifique os campos destacados"
      setCamposInvalidos(resultado.fields);
    }
  };

  return (
    <>
      <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
        Registra as datas que podem influenciar os preços dos itens (expansões, patches, temporadas, eventos sazonais e rotinas
        semanais e mensais), que o modelo preditivo usa como variáveis categóricas. As páginas de terceiros não são lidas de novo
        em menos de 10 minutos.
      </p>

      <section aria-labelledby="titulo-extracao" className="mb-8">
        <h2 id="titulo-extracao" className="mb-3 text-lg font-semibold text-[var(--color-text-title)]">
          Extrair eventos
        </h2>
        <form onSubmit={handleExtrair} noValidate className="max-w-xl">
          <div className="mb-4">
            <label htmlFor="fonte" className="mb-1 block text-sm text-[var(--color-text-secondary)]">
              Fonte
            </label>
            <select id="fonte" value={fonte} onChange={(e) => setFonte(e.target.value as FonteDeEventos | "TODAS")} className={selectClass}>
              {FONTES_DE_EVENTOS.map((item) => (
                <option key={item.valor} value={item.valor}>
                  {item.rotulo}
                </option>
              ))}
              <option value="TODAS">Todas as fontes</option>
            </select>
          </div>
          {fonteComPagina && (
            <Campo id="url" rotulo="Endereço da página (opcional: sem ele, usa a página padrão da fonte)" value={url} onChange={setUrl} maxLength={500} />
          )}
          <BotaoPrimario carregando={extraindo}>{extraindo ? "Extraindo..." : "Extrair eventos"}</BotaoPrimario>
        </form>

        {resultados.length > 0 && (
          <ul className="mt-4 space-y-2 text-sm" aria-live="polite">
            {resultados.map((item) => (
              <li key={item.fonte} className="rounded-md border border-[var(--color-border)] p-3">
                <span className="font-semibold text-[var(--color-text-title)]">
                  {FONTES_DE_EVENTOS.find((f) => f.valor === item.fonte)?.rotulo}
                </span>
                {item.resumo ? (
                  <p className="text-[var(--color-text-secondary)]">
                    {item.resumo.eventos_registrados} registrados; {item.resumo.eventos_ignorados} já constavam (ignorados).
                  </p>
                ) : (
                  <p role="alert" className="text-[var(--color-negative)]">
                    {item.erro}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="titulo-manual" className="mb-8">
        <h2 id="titulo-manual" className="mb-3 text-lg font-semibold text-[var(--color-text-title)]">
          Cadastrar evento manualmente
        </h2>
        {erroManual && <Aviso tipo="erro">{erroManual}</Aviso>}
        {avisoManual && <Aviso tipo="sucesso">{avisoManual}</Aviso>}
        <form onSubmit={handleCadastrar} noValidate className="max-w-xl">
          <Campo id="nome" rotulo="Nome" value={nome} onChange={setNome} invalido={camposInvalidos.includes("nome")} maxLength={150} />
          <Campo id="versao" rotulo="Versão (opcional)" value={versao} onChange={setVersao} invalido={camposInvalidos.includes("versao")} maxLength={20} />
          <div className="mb-4">
            <label htmlFor="tipo" className="mb-1 block text-sm text-[var(--color-text-secondary)]">
              Tipo
            </label>
            <select id="tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-invalid={camposInvalidos.includes("tipo")} className={selectClass}>
              {TIPOS_DE_EVENTO.map((item) => (
                <option key={item.valor} value={item.valor}>
                  {item.rotulo}
                </option>
              ))}
            </select>
          </div>
          <Campo id="data_inicio" rotulo="Data de lançamento (DD/MM/AAAA)" value={dataInicio} onChange={setDataInicio} invalido={camposInvalidos.includes("data_inicio")} maxLength={10} />
          <Campo id="data_fim" rotulo="Data de término (opcional, DD/MM/AAAA)" value={dataFim} onChange={setDataFim} invalido={camposInvalidos.includes("data_fim")} maxLength={10} />
          <div className="mb-4">
            <label htmlFor="regiao_evento" className="mb-1 block text-sm text-[var(--color-text-secondary)]">
              Região
            </label>
            <select id="regiao_evento" value={regiao} onChange={(e) => setRegiao(e.target.value)} aria-invalid={camposInvalidos.includes("regiao")} className={selectClass}>
              <option value="GLOBAL">Global (US e EU)</option>
              <option value="US">US</option>
              <option value="EU">EU</option>
            </select>
          </div>
          <BotaoPrimario carregando={cadastrando}>{cadastrando ? "Cadastrando..." : "Cadastrar evento"}</BotaoPrimario>
        </form>
      </section>

      <section aria-labelledby="titulo-lista">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="titulo-lista" className="text-lg font-semibold text-[var(--color-text-title)]">
            Eventos registrados ({total})
          </h2>
          <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
            Tipo
            <select value={filtro} onChange={(e) => setFiltro(e.target.value)} className={`${selectClass} w-auto`} aria-label="Filtrar por tipo">
              <option value="">Todos</option>
              {TIPOS_DE_EVENTO.map((item) => (
                <option key={item.valor} value={item.valor}>
                  {item.rotulo}
                </option>
              ))}
            </select>
          </label>
        </div>
        {erroLista && <Aviso tipo="erro">{erroLista}</Aviso>}
        {eventos.length === 0 && !erroLista ? (
          <p className="text-sm text-[var(--color-text-secondary)]">Nenhum evento registrado ainda.</p>
        ) : (
          <TabelaDeEventos eventos={eventos} />
        )}
        {eventos.length < total && (
          <button
            type="button"
            onClick={() => carregar(filtro, eventos.length)}
            className="mt-3 text-sm text-[var(--color-cta)] hover:underline"
          >
            Carregar mais
          </button>
        )}
      </section>
    </>
  );
}

/** CU10-C2 – Registrar eventos de atualização do jogo (Admin). */
export default function EventosPage() {
  return (
    <AdminPagina titulo="Eventos do jogo" href="/admin/eventos">
      {(token) => <Eventos token={token} />}
    </AdminPagina>
  );
}
