import { formatarMoeda } from "@/lib/moeda";
import type { PrecoAtual } from "@/lib/historicoDoItem";

/**
 * CU04-C1 passo 3 (RN06): o destaque é o valor de mercado (1º quartil dos leilões ativos); o menor preço de compra fica como
 * informação secundária. Sem valor de mercado (item sem preço de compra), o menor preço passa a ser o destaque.
 */
export default function PrecoAtualDoItem({ preco }: { preco: PrecoAtual }) {
  const destaque = preco.market_value ?? preco.min_price;
  const mostraMenorPreco = preco.market_value !== null && preco.min_price > 0 && preco.min_price !== preco.market_value;
  return (
    <div className="text-right">
      {preco.total_quantity !== null && (
        <p className="mb-1 font-medium text-[var(--color-text-secondary)]">{preco.total_quantity.toLocaleString("pt-BR")} leilões ativos</p>
      )}
      <p className="text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
        {preco.market_value !== null ? "Valor de mercado" : "Menor preço"}
      </p>
      <p className="text-2xl font-bold text-[var(--color-cta)]" data-testid="valor-em-destaque">
        {formatarMoeda(destaque)}
      </p>
      {mostraMenorPreco && (
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]" data-testid="menor-preco">
          Menor preço: {formatarMoeda(preco.min_price)}
        </p>
      )}
    </div>
  );
}
