"""Erro nas amostras com e sem evento conhecido nos dias previstos (etapa 2h).

"Com evento" é ter, entre D+1 e D+7, um patch, um marco de expansão, um início de temporada ou um início ou fim de
evento sazonal (a coluna com_evento_no_horizonte do calendario_futuro.py). É onde o calendário dos dias previstos
deveria ajudar, se ajudar. Lê o arquivo *_detalhe.parquet do avaliar.py, de qualquer modelo (com ou sem o calendário).

Uso
    python eventos_no_horizonte.py --pasta saida/treino01_agr --calendario saida/calendario2h/calendario_futuro.parquet \\
        --detalhe saida/treino01_agr/avaliacao_validacao_gelu_s42_detalhe.parquet --rotulo gelu_s42
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from calendario_futuro import CalendarioFuturo

COLUNAS = ["id_amostra", "serie", "item_id", "data_origem", "avaliavel", "erro_pct", "erro_pct_ingenuo"]
GRUPOS = ("com evento", "sem evento", "todos")


def _razao(a: float, b: float) -> Optional[float]:
    return a / b if b > 0 else None


def analisar(det: pd.DataFrame, com_evento: np.ndarray) -> pd.DataFrame:
    """Etapa 2h: uma linha por grupo, com a mediana do MdAPE por item (a medida principal), o MAPE e as razões contra o
    ingênuo nos mesmos alvos. `com_evento` tem uma posição por linha de `det`."""
    avaliavel = det["avaliavel"].to_numpy(dtype=bool)
    com_evento = np.asarray(com_evento, dtype=bool)
    linhas: list[dict[str, Any]] = []
    for grupo, sel in (("com evento", com_evento), ("sem evento", ~com_evento), ("todos", np.ones_like(com_evento))):
        g = det[avaliavel & sel]
        if g.empty:
            linhas.append({"grupo": grupo, "amostras": 0, "alvos": 0, "itens": 0})
            continue
        pi = g.groupby(["serie", "item_id"]).agg(mdape=("erro_pct", "median"),
                                                 mdape_ingenuo=("erro_pct_ingenuo", "median"))
        md, md_i = float(pi["mdape"].median()), float(pi["mdape_ingenuo"].median())
        mape, mape_i = float(g["erro_pct"].mean()), float(g["erro_pct_ingenuo"].mean())
        linhas.append({"grupo": grupo, "amostras": int(g["id_amostra"].nunique()), "alvos": int(len(g)),
                       "itens": int(len(pi)), "mediana_mdape_por_item": md, "mediana_mdape_ingenuo_por_item": md_i,
                       "razao_mdape": _razao(md, md_i), "mape": mape, "mape_ingenuo": mape_i,
                       "razao_mape": _razao(mape, mape_i)})
    return pd.DataFrame(linhas)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True, help="a base avaliada (região de cada série e horizonte)")
    ap.add_argument("--calendario", type=Path, required=True, help="calendario_futuro.parquet")
    ap.add_argument("--detalhe", type=Path, required=True, help="avaliacao_<periodo>_<rotulo>_detalhe.parquet")
    ap.add_argument("--rotulo", required=True)
    args = ap.parse_args(argv)

    normalizacao = json.loads((args.pasta / "normalizacao.json").read_text(encoding="utf-8"))
    cal = CalendarioFuturo.carregar(args.calendario, args.pasta, int(normalizacao["config"]["horizonte"]))
    det = pd.read_parquet(args.detalhe, columns=COLUNAS)
    amostras = det.drop_duplicates("id_amostra")[["id_amostra", "serie", "data_origem"]]
    por_amostra = pd.Series(cal.com_evento(amostras["serie"], amostras["data_origem"]),
                            index=amostras["id_amostra"].to_numpy())
    tabela = analisar(det, det["id_amostra"].map(por_amostra).to_numpy(dtype=bool))
    tabela.insert(0, "rotulo", args.rotulo)
    destino = args.detalhe.parent / f"eventos_horizonte_{args.rotulo}.csv"
    tabela.to_csv(destino, index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(tabela.round(4).to_string(index=False))
    print(f"\nGravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
