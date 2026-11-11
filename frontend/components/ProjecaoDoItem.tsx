import { formatarMoeda } from "@/lib/moeda";
import { formatarDia, formatarVariacao, projecaoExibida, type AvisoDaProjecao, type ProjecaoDoItem as Projecao } from "@/lib/projecaoDoItem";
import type { EstadoDaProjecao } from "@/lib/useProjecaoDoItem";

interface Props {
  estado: EstadoDaProjecao;
  /** CU05-C3: com a projeção oculta, a tabela e os textos dela não aparecem. */
  visivel: boolean;
  diaDestacado: string | null;
  aoDestacarDia: (dia: string | null) => void;
}

function texto(avisos: AvisoDaProjecao[], codigo: AvisoDaProjecao["codigo"]): string | undefined {
  return avisos.find((aviso) => aviso.codigo === codigo)?.texto;
}

function moeda(cobre: number): string {
  try {
    return formatarMoeda(cobre);
  } catch (erro) {
    console.error("CU05: preço previsto não pôde ser convertido.", erro, cobre);
    return "N/D";
  }
}

function variacao(pct: number): string {
  try {
    return formatarVariacao(pct);
  } catch {
    return "N/D";
  }
}

/**
 * CU05-C1 passos 6 e 7 (e FA7): abaixo do gráfico, a origem da projeção, o erro típico do item, o aviso de estimativa, o
 * alerta de projeção desatualizada e a tabela dos dias previstos. FA1 a FA6 e FE1: a mensagem do cenário no lugar da
 * projeção; o histórico continua exibido. CU05-C2 passo 3: a linha em destaque acompanha o ponto do gráfico.
 */
export default function ProjecaoDoItem({ estado, visivel, diaDestacado, aoDestacarDia }: Props) {
  if (estado.carregando) return null;
  if (estado.erro) {
    return <p role="alert" data-testid="projecao-indisponivel" className="mt-4 text-sm text-[var(--color-negative)]">{estado.erro}</p>;
  }
  const projecao: Projecao | null = estado.projecao;
  const exibida = projecaoExibida(projecao);
  if (!projecao || !exibida) {
    return (
      <p role="status" data-testid="projecao-indisponivel" className="mt-4 text-sm text-[var(--color-text-secondary)]">
        {projecao?.mensagem}
      </p>
    );
  }
  if (!visivel) return null;

  const origem = texto(projecao.avisos, "ORIGEM");
  const erroTipico = texto(projecao.avisos, "ERRO_TIPICO");
  const estimativa = texto(projecao.avisos, "ESTIMATIVA");
  const desatualizada = texto(projecao.avisos, "DESATUALIZADA");
  const quantidade = exibida.predicoes.length;

  return (
    <section aria-label="Projeção" className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-2 text-sm text-[var(--color-text-secondary)]">
        <div>
          {origem && <p data-testid="projecao-origem">{origem}</p>}
          {estimativa && <p data-testid="projecao-estimativa" className="italic text-xs mt-1">{estimativa}</p>}
        </div>
        {erroTipico && <p data-testid="projecao-erro-tipico">{erroTipico}</p>}
      </div>
      {desatualizada && (
        <p role="status" data-codigo="DESATUALIZADA"
          className="mt-3 inline-block rounded-md border border-[var(--color-cta)]/60 bg-[var(--color-cta)]/10 px-3 py-1 text-sm font-medium text-[var(--color-cta)]">
          {desatualizada}
        </p>
      )}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-[var(--color-text-title)]">
        {quantidade === 1 ? "Projeção para o próximo dia" : `Projeção para os próximos ${quantidade} dias`}
      </h3>
      <table className="w-full text-sm border border-[var(--color-border)] rounded-lg overflow-hidden">
        <thead className="bg-[var(--color-surface-solid)] text-left text-[var(--color-text-title)]">
          <tr>
            <th className="px-4 py-2 font-semibold">Data</th>
            <th className="px-4 py-2 font-semibold">Preço previsto (menor preço do dia)</th>
            <th className="px-4 py-2 font-semibold">Variação sobre {formatarDia(exibida.dataReferencia, false)}</th>
          </tr>
        </thead>
        <tbody>
          {exibida.predicoes.map((predicao) => {
            const emDestaque = predicao.data_prevista === diaDestacado;
            return (
              <tr
                key={predicao.data_prevista}
                data-dia={predicao.data_prevista}
                data-destacado={emDestaque ? "true" : undefined}
                tabIndex={0}
                onMouseEnter={() => aoDestacarDia(predicao.data_prevista)}
                onMouseLeave={() => aoDestacarDia(null)}
                onFocus={() => aoDestacarDia(predicao.data_prevista)}
                onBlur={() => aoDestacarDia(null)}
                className={`border-t border-[var(--color-border)] transition-colors ${emDestaque ? "bg-[var(--color-projection)]/15" : ""}`}
              >
                <td className="px-4 py-2 text-[var(--color-text-main)]">{formatarDia(predicao.data_prevista)}</td>
                <td className="px-4 py-2 text-[var(--color-cta)]">{moeda(predicao.preco_previsto)}</td>
                <td className={`px-4 py-2 ${predicao.variacao_pct >= 0 ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"}`}>
                  {variacao(predicao.variacao_pct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
