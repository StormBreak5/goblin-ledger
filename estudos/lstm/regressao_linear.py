"""Regressão linear (ridge) sobre as mesmas amostras da LSTM: segunda referência de comparação (R02 do TC) e exemplo
de como uma estimativa volta para a avaliação pelo id_amostra.

O ajuste acumula XᵀX e Xᵀy lote a lote, então usa todas as amostras de treino sem montar todas as janelas na memória.

Uso
    python regressao_linear.py --pasta saida/estudo01 --periodo validacao
    python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes saida/estudo01/previsoes_validacao_linear.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from avaliar import salvar_previsoes
from config import PERIODOS
from dataset import DadosPreparados


def matriz(t: dict[str, np.ndarray]) -> np.ndarray:
    n = len(t["id_amostra"])
    return np.hstack([t["X_seq"].reshape(n, -1), t["X_est"], np.ones((n, 1), dtype=np.float32)]).astype(np.float64)


def ajustar(dados: DadosPreparados, lam: float = 1.0, lote: int = 20_000) -> np.ndarray:
    xtx: Optional[np.ndarray] = None
    xty: Optional[np.ndarray] = None
    for t in dados.lotes("treino", tamanho=lote, embaralhar=False):
        x = matriz(t)
        xtx = x.T @ x if xtx is None else xtx + x.T @ x
        xty = x.T @ t["y"] if xty is None else xty + x.T @ t["y"]
    if xtx is None or xty is None:
        raise ValueError("não há amostras de treino")
    reg = lam * np.eye(xtx.shape[0])
    reg[-1, -1] = 0.0  # não penaliza o intercepto
    return np.linalg.solve(xtx + reg, xty)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--periodo", choices=PERIODOS[1:], default="validacao")
    ap.add_argument("--lambda", dest="lam", type=float, default=1.0)
    args = ap.parse_args(argv)

    dados = DadosPreparados(args.pasta)
    w = ajustar(dados, args.lam)
    t = dados.tensores(dados.janelas(args.periodo))
    yhat = matriz(t) @ w                          # saída na escala normalizada, como a da Dense(7)
    destino = args.pasta / f"previsoes_{args.periodo}_linear.parquet"
    salvar_previsoes(t["id_amostra"], yhat, destino)
    print(f"{len(yhat)} previsões gravadas em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
