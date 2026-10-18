"""Análises da generalização do modelo (etapas 2c e 2f), a partir das avaliações já gravadas pelo avaliar.py.

liquidez   Erro do modelo pela liquidez do item: quantidade média ofertada no período avaliado, em faixas. Mostra
           onde o modelo passa a superar o ingênuo, em itens do treino e fora dele (base derivada com
           --normalizacao-de). Foi o que mostrou que a fronteira de uso do modelo é a liquidez (RN02), e não o item
           ter entrado no treino.
novos      Itens avaliados que não têm nenhuma amostra de treino na base (em geral, itens lançados depois do corte do
           treino), comparados com os demais, e com a reserva da etapa 2c quando existir.

A base de cada avaliação é a pasta onde o arquivo *_itens.csv está (o avaliar.py grava as avaliações na base).

Uso
    python generalizacao.py liquidez --avaliacao saida/treino2c/avaliacao_validacao_m_todos_s42_itens.csv \\
        --avaliacao saida/fora2c/avaliacao_validacao_m_todos_s42_itens.csv --saida saida/liquidez_m_todos_s42.csv
    python generalizacao.py novos --avaliacao saida/treino2c/avaliacao_validacao_m_sem_s42_itens.csv \\
        --saida saida/novos_m_sem_s42.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

FAIXAS_LIQUIDEZ: tuple[tuple[float, float, str], ...] = (
    (0, 5, "menos de 5"), (5, 20, "5 a 20"), (20, 50, "20 a 50"), (50, 200, "50 a 200"), (200, 1000, "200 a 1.000"),
    (1000, 10000, "1.000 a 10.000"), (10000, np.inf, "10.000 ou mais"))


def medidas(pi: pd.DataFrame) -> dict[str, Any]:
    """As medidas por grupo de itens usadas nos relatórios das etapas 2c a 2f."""
    n = int(len(pi))
    if not n:
        return {"itens": 0}
    rel = pi["erro_relativo_ingenuo"]
    out: dict[str, Any] = {
        "itens": n,
        "mediana_mdape": float(pi["mdape"].median()),
        "mediana_mdape_ingenuo": float(pi["mdape_ingenuo"].median()),
        "mediana_erro_relativo": float(rel.median()) if rel.notna().any() else None,
        "pct_erro_relativo_menor_que_1": round(float((rel < 1).mean()), 4),
        "liberados_rn10": int((pi["situacao"] == "Liberada").sum()),
        "pct_liberados_rn10": round(float((pi["situacao"] == "Liberada").mean()), 4),
    }
    if "dias_avaliados" in pi.columns:
        out["mediana_dias_avaliados"] = float(pi["dias_avaliados"].median())
    return out


def _periodo_da_avaliacao(caminho: Path) -> str:
    nome = caminho.name
    for p in ("treino", "validacao", "teste"):
        if nome.startswith(f"avaliacao_{p}_"):
            return p
    raise ValueError(f"não reconheço o período no nome {nome} (esperado avaliacao_<periodo>_<rotulo>_itens.csv)")


def quantidade_media(base: Path, periodo: str) -> pd.Series:
    """Quantidade média ofertada de cada item nos dias observados do período."""
    o = pd.read_parquet(base / "linhas_originais.parquet", columns=["item_id", "periodo", "quantidade_bruta"])
    o = o[o["periodo"].astype(str) == periodo]
    return o.groupby("item_id")["quantidade_bruta"].mean().rename("quantidade_media")


def faixa_de_liquidez(q: pd.Series) -> pd.Series:
    rotulo = pd.Series("sem quantidade", index=q.index, dtype=object)
    for ini, fim, nome in FAIXAS_LIQUIDEZ:
        rotulo[(q >= ini) & (q < fim)] = nome
    return rotulo


def por_liquidez(itens: pd.DataFrame) -> pd.DataFrame:
    """`itens` = resultado por item com as colunas do avaliar.py, mais quantidade_media e base."""
    ordem = [f[2] for f in FAIXAS_LIQUIDEZ] + ["sem quantidade"]
    itens = itens.assign(faixa=faixa_de_liquidez(itens["quantidade_media"]))
    linhas: list[dict[str, Any]] = []
    grupos = [(b, itens[itens["base"] == b]) for b in sorted(itens["base"].unique())]
    if len(grupos) > 1:
        grupos.append(("todas", itens))
    for base, d in grupos:
        for faixa in ordem:
            g = d[d["faixa"] == faixa]
            if len(g):
                linhas.append({"base": base, "faixa": faixa, **medidas(g)})
    return pd.DataFrame(linhas)


def por_novidade(itens: pd.DataFrame, com_treino: set[int]) -> pd.DataFrame:
    """Itens com e sem amostras de treino (e reservados ou não, se a base tiver reserva)."""
    itens = itens.assign(tem_amostra_de_treino=itens["item_id"].isin(com_treino))
    chaves = ["tem_amostra_de_treino"] + (["reservado"] if "reservado" in itens.columns else [])
    linhas: list[dict[str, Any]] = []
    for k, g in itens.groupby(chaves, dropna=False):
        k = k if isinstance(k, tuple) else (k,)
        linhas.append({**dict(zip(chaves, k)), **medidas(g)})
    linhas.append({**{c: "todos" for c in chaves}, **medidas(itens)})
    return pd.DataFrame(linhas)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    li = sub.add_parser("liquidez", help="erro por faixa de quantidade média ofertada")
    li.add_argument("--avaliacao", type=Path, action="append", required=True, help="*_itens.csv (pode repetir)")
    li.add_argument("--saida", type=Path, required=True)
    no = sub.add_parser("novos", help="itens sem nenhuma amostra de treino x demais")
    no.add_argument("--avaliacao", type=Path, required=True, help="*_itens.csv")
    no.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args(argv)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    if args.comando == "liquidez":
        partes = []
        for arq in args.avaliacao:
            base = arq.parent
            itens = pd.read_csv(arq)
            q = quantidade_media(base, _periodo_da_avaliacao(arq))
            partes.append(itens.merge(q, left_on="item_id", right_index=True, how="left").assign(base=base.name))
        tab = por_liquidez(pd.concat(partes, ignore_index=True))
    else:
        base = args.avaliacao.parent
        com_treino = set(pd.read_parquet(base / "janelas_treino.parquet", columns=["item_id"])["item_id"].unique())
        tab = por_novidade(pd.read_csv(args.avaliacao), com_treino)
    tab.to_csv(args.saida, index=False)
    print(tab.to_string(index=False))
    print(f"\nGravado em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
