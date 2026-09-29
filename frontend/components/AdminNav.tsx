import Link from "next/link";

const paginas = [
  { href: "/admin/ingestao", rotulo: "Ingestão de mercado" },
  { href: "/admin/historico", rotulo: "Histórico de preços" },
  { href: "/admin/eventos", rotulo: "Eventos do jogo" },
];

/** Atalhos entre as telas do Admin (CU09-C4 e CU10). */
export default function AdminNav({ atual }: { atual: string }) {
  return (
    <nav aria-label="Funções administrativas" className="mb-6 flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {paginas.map((pagina) =>
        pagina.href === atual ? (
          <span key={pagina.href} aria-current="page" className="font-semibold text-[var(--color-text-title)]">
            {pagina.rotulo}
          </span>
        ) : (
          <Link key={pagina.href} href={pagina.href} className="text-[var(--color-cta)] hover:underline">
            {pagina.rotulo}
          </Link>
        ),
      )}
    </nav>
  );
}
