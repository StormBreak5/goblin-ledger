"""Comparação pareada, item a item, de duas avaliações (etapa 2c).

Pergunta do experimento: o modelo erra mais num item que ele nunca viu? Os mesmos itens reservados são avaliados por
dois modelos: A, treinado SEM eles (não vistos), e B, treinado COM eles (controle). Como os itens e os dias avaliados
são os mesmos, a diferença A − B mede só o efeito de o item ter ficado fora do treino.

Entradas: os arquivos avaliacao_<periodo>_<rotulo>_itens.csv gravados pelo avaliar.py.

Uso
    python comparar.py --a saida/treino2c/avaliacao_validacao_c_sem_s42_itens.csv \\
                       --b saida/treino2c/avaliacao_validacao_c_todos_s42_itens.csv \\
                       --rotulos "não vistos" "vistos" --filtro reservado --saida saida/treino2c/comparacao_s42.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

METRICAS = ("mdape", "mape", "erro_relativo_ingenuo")
TOLERANCIA_PP = 0.01  # 1 ponto percentual


def comparar(a: pd.DataFrame, b: pd.DataFrame, filtro: Optional[str] = None) -> dict[str, Any]:
    """Itens presentes nas duas avaliações (e com `filtro` verdadeiro, se informado)."""
    chave = ["serie", "item_id"]
    a = a.astype({"serie": str})
    b = b.astype({"serie": str})
    if filtro:
        if filtro not in a.columns:
            raise KeyError(f"coluna {filtro!r} não existe na avaliação A (a base tem itens.parquet?)")
        a = a[a[filtro].astype("boolean").fillna(False).to_numpy()]
    m = a.merge(b, on=chave, suffixes=("_a", "_b"))
    if m.empty:
        raise ValueError("nenhum item em comum entre as duas avaliações")
    out: dict[str, Any] = {"itens": int(len(m)), "filtro": filtro}
    for met in METRICAS:
        xa, xb = m[f"{met}_a"].to_numpy(float), m[f"{met}_b"].to_numpy(float)
        ok = np.isfinite(xa) & np.isfinite(xb)
        d = xa[ok] - xb[ok]
        out[met] = {
            "mediana_a": float(np.median(xa[ok])),
            "mediana_b": float(np.median(xb[ok])),
            "mediana_da_diferenca": float(np.median(d)),
            "p25_da_diferenca": float(np.percentile(d, 25)),
            "p75_da_diferenca": float(np.percentile(d, 75)),
            "itens_a_pior_que_b": int((d > 0).sum()),
            "itens_a_melhor_ou_igual": int((d <= 0).sum()),
        }
    d = (m["mdape_a"] - m["mdape_b"]).to_numpy(float)
    out["mdape"]["itens_com_diferenca_ate_1pp"] = int((np.abs(d) <= TOLERANCIA_PP + 1e-9).sum())
    lib_a, lib_b = m["situacao_a"] == "Liberada", m["situacao_b"] == "Liberada"
    out["rn10"] = {"liberados_a": int(lib_a.sum()), "liberados_b": int(lib_b.sum()),
                   "liberados_nos_dois": int((lib_a & lib_b).sum()), "so_a": int((lib_a & ~lib_b).sum()),
                   "so_b": int((~lib_a & lib_b).sum())}
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--rotulos", nargs=2, default=["A", "B"])
    ap.add_argument("--filtro", help="coluna booleana do arquivo A que escolhe os itens (ex.: reservado)")
    ap.add_argument("--saida", type=Path)
    args = ap.parse_args(argv)

    res = comparar(pd.read_csv(args.a), pd.read_csv(args.b), args.filtro)
    res["rotulos"] = {"a": args.rotulos[0], "b": args.rotulos[1]}
    res["arquivos"] = {"a": str(args.a), "b": str(args.b)}
    texto = json.dumps(res, indent=2, ensure_ascii=False)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
