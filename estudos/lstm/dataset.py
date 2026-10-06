"""Leitura dos dados preparados: monta os tensores da LSTM a partir dos ids e mostra a linha original ao lado da
normalizada.

As janelas não são gravadas prontas (com milhões de amostras, [amostras, 30, 16] ocuparia dezenas de GB). Cada amostra
guarda só id_linha_origem; a janela de entrada são as linhas id_linha_origem − 29 ... id_linha_origem, que estão
contíguas porque linhas_normalizadas.parquet está na ordem (série, data) e id_linha é a posição da linha.

Uso
    python dataset.py exportar --pasta saida/estudo01 --periodo treino --max-amostras 50000 --arquivo treino.npz
    python dataset.py amostra --pasta saida/estudo01 --id-amostra 123
    python dataset.py inspecionar --pasta saida/estudo01 --item 210796 --de 2026-03-01 --ate 2026-03-10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

import numpy as np
import pandas as pd

from config import PERIODOS


class DadosPreparados:
    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.normalizacao: dict[str, Any] = json.loads((self.pasta / "normalizacao.json").read_text(encoding="utf-8"))
        cfg = self.normalizacao["config"]
        self.janela: int = int(cfg["janela"])
        self.horizonte: int = int(cfg["horizonte"])
        var = self.normalizacao["variaveis"]
        self.var_seq: list[str] = var["sequencia"]
        self.var_est: list[str] = var["estaticas"]
        self.var_cat: list[str] = var["categoricas"]

        ln = pd.read_parquet(self.pasta / "linhas_normalizadas.parquet")
        if not np.array_equal(ln["id_linha"].to_numpy(), np.arange(len(ln))):
            raise ValueError("linhas_normalizadas.parquet fora de ordem: id_linha deve ser igual à posição da linha")
        self.seq = ln[self.var_seq].to_numpy(dtype=np.float32)
        self.est = ln[self.var_est].to_numpy(dtype=np.float32)
        self.cat = ln[self.var_cat].to_numpy(dtype=np.int32)
        self._normalizadas = ln
        self._originais: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------------------------------------- leitura
    @property
    def originais(self) -> pd.DataFrame:
        if self._originais is None:
            self._originais = pd.read_parquet(self.pasta / "linhas_originais.parquet")
        return self._originais

    @property
    def normalizadas(self) -> pd.DataFrame:
        return self._normalizadas

    def janelas(self, periodo: str) -> pd.DataFrame:
        if periodo not in PERIODOS:
            raise ValueError(f"período deve ser um de {PERIODOS}")
        return pd.read_parquet(self.pasta / f"janelas_{periodo}.parquet")

    def colunas_alvo(self) -> list[str]:
        return [f"y_{h}" for h in range(1, self.horizonte + 1)]

    # ------------------------------------------------------------------------------------------------ tensores
    def tensores(self, jan: pd.DataFrame) -> dict[str, np.ndarray]:
        """X_seq [n, 30, 16], X_est [n, 4], X_cat [n, 2], y [n, 7] (normalizado), mascara [n, 7] (alvo observado) e
        id_amostra [n], que acompanha as previsões até a avaliação."""
        origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
        idx = origem[:, None] + np.arange(-self.janela + 1, 1)[None, :]
        return {
            "id_amostra": jan["id_amostra"].to_numpy(dtype=np.int64),
            "X_seq": self.seq[idx],
            "X_est": self.est[origem],
            "X_cat": self.cat[origem],
            "y": jan[self.colunas_alvo()].to_numpy(dtype=np.float32),
            "mascara": jan[[f"obs_{h}" for h in range(1, self.horizonte + 1)]].to_numpy(dtype=bool),
        }

    def lotes(self, periodo: str, tamanho: int = 512, embaralhar: bool = True,
              semente: int = 42) -> Iterator[dict[str, np.ndarray]]:
        """Gera lotes sob demanda, para treinar sem materializar todas as janelas (ex.: tf.data.from_generator)."""
        jan = self.janelas(periodo)
        ordem = np.random.default_rng(semente).permutation(len(jan)) if embaralhar else np.arange(len(jan))
        for ini in range(0, len(ordem), tamanho):
            yield self.tensores(jan.iloc[ordem[ini:ini + tamanho]])

    # ---------------------------------------------------------------------------------------------- inspeção
    def lado_a_lado(self, ids_linha: np.ndarray) -> pd.DataFrame:
        """Linha original e linha normalizada juntas, pelo id_linha."""
        o = self.originais.iloc[ids_linha]
        n = self._normalizadas.iloc[ids_linha].drop(columns=["serie", "item_id", "data", "periodo"])
        return o.merge(n, on="id_linha")

    def amostra(self, id_amostra: int) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
        """A amostra completa: as 30 linhas de entrada (original + normalizada) e os 7 alvos."""
        for periodo in PERIODOS:
            jan = self.janelas(periodo)
            linha = jan.loc[jan["id_amostra"] == id_amostra]
            if not linha.empty:
                break
        else:
            raise KeyError(f"id_amostra {id_amostra} não existe em nenhum dos arquivos de janelas")
        a = linha.iloc[0]
        o = int(a["id_linha_origem"])
        entrada = self.lado_a_lado(np.arange(o - self.janela + 1, o + 1))
        alvos = self.originais.iloc[o + 1:o + self.horizonte + 1][["id_linha", "data", "preco_cobre", "observado"]].copy()
        alvos.insert(0, "h", range(1, self.horizonte + 1))
        alvos["y_normalizado"] = [a[f"y_{h}"] for h in range(1, self.horizonte + 1)]
        return a, entrada, alvos


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    ex = sub.add_parser("exportar", help="grava X_seq, X_est, X_cat, y, mascara e id_amostra num .npz")
    ex.add_argument("--pasta", type=Path, required=True)
    ex.add_argument("--periodo", choices=PERIODOS, required=True)
    ex.add_argument("--max-amostras", type=int)
    ex.add_argument("--arquivo", type=Path, required=True)
    ex.add_argument("--semente", type=int, default=42)
    am = sub.add_parser("amostra", help="mostra as 30 linhas de entrada e os 7 alvos de uma amostra")
    am.add_argument("--pasta", type=Path, required=True)
    am.add_argument("--id-amostra", type=int, required=True)
    ins = sub.add_parser("inspecionar", help="linha original x linha normalizada de um item")
    ins.add_argument("--pasta", type=Path, required=True)
    ins.add_argument("--item", type=int, required=True)
    ins.add_argument("--serie")
    ins.add_argument("--de")
    ins.add_argument("--ate")
    args = ap.parse_args(argv)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.float_format", lambda v: f"{v:.4f}")
    dados = DadosPreparados(args.pasta)

    if args.comando == "exportar":
        jan = dados.janelas(args.periodo)
        if args.max_amostras and len(jan) > args.max_amostras:
            jan = jan.sample(args.max_amostras, random_state=args.semente).sort_values("id_amostra")
        t = dados.tensores(jan)
        np.savez_compressed(args.arquivo, **t)
        print({k: v.shape for k, v in t.items()})
    elif args.comando == "amostra":
        a, entrada, alvos = dados.amostra(args.id_amostra)
        print(f"Amostra {a['id_amostra']} ({a['periodo']}) | série {a['serie']} | item {a['item_id']} | "
              f"hoje = {a['data_origem']:%Y-%m-%d} | preço base {a['preco_base']} cobre")
        print("\nEntrada (original ao lado da normalizada):")
        print(entrada.to_string(index=False))
        print("\nAlvos:")
        print(alvos.to_string(index=False))
    else:
        o = dados.originais
        m = o["item_id"] == args.item
        if args.serie:
            m &= o["serie"] == args.serie
        if args.de:
            m &= o["data"] >= pd.Timestamp(args.de)
        if args.ate:
            m &= o["data"] <= pd.Timestamp(args.ate)
        print(dados.lado_a_lado(np.flatnonzero(m.to_numpy())).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
