"use client";

import { useState } from "react";
import Dialogo from "@/components/Dialogo";
import { OPCOES_DE_CANAL, ROTULO_DO_TIPO, type DadosDoAlerta, type TipoDeAlerta } from "@/lib/alertasApi";
import { formatarMoeda } from "@/lib/moeda";

interface Props {
  titulo: string;
  itemNome: string;
  iconUrl: string | null;
  valorDeMercado: number | null; // RN06, em Cobre: a referência do C1 passo 4 e do C2 passo 2
  inicial: DadosDoAlerta;
  erro: string | null; // FA3, com o texto do backend
  ocupado: boolean;
  aoSalvar: (dados: DadosDoAlerta) => void;
  aoCancelar: () => void;
}

function referencia(cobre: number | null): string {
  if (cobre === null) return "—";
  try {
    return formatarMoeda(cobre);
  } catch {
    return "—";
  }
}

const TIPOS: TipoDeAlerta[] = ["COMPRA", "VENDA"];
const campoClasse = "w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-[var(--color-text-main)] focus:border-[var(--color-cta)] focus:outline-none";

/**
 * CU07-C1 passo 5 / C2 passo 3 (Figura 16): o tipo de gatilho, o preço-alvo em Ouro, Prata e Cobre e o canal. A
 * validação (FA3) e a conversão para Cobre (RN01) são do backend; o FA3 aparece aqui e o formulário continua aberto.
 */
export default function FormularioDeAlerta({ titulo, itemNome, iconUrl, valorDeMercado, inicial, erro, ocupado, aoSalvar, aoCancelar }: Props) {
  const [dados, setDados] = useState<DadosDoAlerta>(inicial);
  const mudar = (campo: Partial<DadosDoAlerta>) => setDados((atual) => ({ ...atual, ...campo }));

  return (
    <Dialogo titulo={titulo} aoCancelar={aoCancelar} largura="max-w-lg">
      <form
        noValidate
        onSubmit={(evento) => {
          evento.preventDefault();
          aoSalvar(dados);
        }}
      >
        <div className="mb-5 flex items-center gap-3 rounded-lg border border-[var(--color-border)] p-3">
          {iconUrl ? <img src={iconUrl} alt="" className="h-10 w-10 rounded border border-[var(--color-border)]" /> : null}
          <div>
            <p className="font-semibold text-[var(--color-text-title)]">{itemNome}</p>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Valor de mercado atual: <span data-testid="valor-de-referencia" className="font-semibold text-[var(--color-cta)]">{referencia(valorDeMercado)}</span>
            </p>
          </div>
        </div>

        {erro && <p role="alert" className="mb-4 rounded-md border border-[var(--color-negative)]/50 px-3 py-2 text-sm text-[var(--color-negative)]">{erro}</p>}

        <fieldset className="mb-5">
          <legend className="mb-2 text-sm text-[var(--color-text-secondary)]">Tipo de gatilho</legend>
          <div className="grid grid-cols-2 gap-3">
            {TIPOS.map((tipo) => (
              <button
                key={tipo}
                type="button"
                aria-pressed={dados.tipo === tipo}
                onClick={() => mudar({ tipo })}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  dados.tipo === tipo ? "border-[var(--color-cta)] bg-[var(--color-cta)]/10" : "border-[var(--color-border)] hover:border-[var(--color-text-secondary)]"
                }`}
              >
                <span className="block font-semibold text-[var(--color-text-title)]">{ROTULO_DO_TIPO[tipo].nome}</span>
                <span className="block text-xs text-[var(--color-text-secondary)]">{ROTULO_DO_TIPO[tipo].descricao}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="mb-5">
          <legend className="mb-2 text-sm text-[var(--color-text-secondary)]">Preço-alvo</legend>
          <div className="grid grid-cols-3 gap-3">
            {([["ouro", "Ouro"], ["prata", "Prata"], ["cobre", "Cobre"]] as const).map(([campo, rotulo]) => (
              <label key={campo} className="text-xs text-[var(--color-text-secondary)]">
                <input
                  type="text"
                  inputMode="numeric"
                  aria-label={rotulo}
                  value={dados[campo]}
                  onChange={(evento) => mudar({ [campo]: evento.target.value })}
                  className={campoClasse}
                />
                <span className="mt-1 block">{rotulo}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="mb-6">
          <legend className="mb-2 text-sm text-[var(--color-text-secondary)]">Canal de notificação</legend>
          <div className="flex gap-6">
            {OPCOES_DE_CANAL.map((opcao) => (
              <label key={opcao.valor} className="flex items-center gap-2 text-[var(--color-text-main)]">
                <input type="radio" name="canal" value={opcao.valor} checked={dados.canal === opcao.valor}
                  onChange={() => mudar({ canal: opcao.valor })} className="accent-[var(--color-cta)]" />
                {opcao.rotulo}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={aoCancelar} disabled={ocupado}
            className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-main)] hover:bg-white/5">
            Cancelar
          </button>
          <button type="submit" disabled={ocupado}
            className="rounded-md bg-[var(--color-cta)] px-4 py-2 text-sm font-semibold text-[#161124] hover:bg-[var(--color-cta-hover)] disabled:opacity-60">
            Salvar alerta
          </button>
        </div>
      </form>
    </Dialogo>
  );
}
