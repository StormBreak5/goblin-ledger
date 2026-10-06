"""Avaliação das estimativas: desfaz a normalização, volta para o preço em Cobre e confronta com a linha original.

Caminho de uma previsão até o erro
    yhat normalizado (saída da Dense(7))
      → log-retorno: r = yhat · desvio_h + media_h            (normalizacao.json → "alvo")
      → preço:       p̂ = preco_base · exp(r), arredondado     (Cobre, RN01)
      → real:        linhas_originais[id_linha_origem + h]     (só dias observados; preenchidos e RN03 ficam de fora)

Arquivo de previsões: parquet ou csv com id_amostra e yhat_1 ... yhat_7 na escala normalizada (use salvar_previsoes).

Uso
    python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes previsoes_validacao.parquet
    python avaliar.py --pasta saida/estudo01 --periodo validacao --ingenuo     # modelo ingênuo (amanhã = hoje)
    python avaliar.py --pasta saida/estudo01 --periodo validacao --verificar   # ida e volta: tem de dar erro zero
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import PERIODOS
from dataset import DadosPreparados

COBRE_POR_OURO = 10_000  # RN01


@dataclass
class Avaliacao:
    detalhe: pd.DataFrame       # uma linha por amostra e por dia do horizonte
    por_item: pd.DataFrame
    por_horizonte: pd.DataFrame
    resumo: dict[str, Any]


def salvar_previsoes(id_amostra: np.ndarray, yhat_normalizado: np.ndarray, caminho: Path) -> None:
    """Grava a saída do modelo com o id de cada amostra, que é o que liga a previsão à linha original."""
    df = pd.DataFrame(yhat_normalizado, columns=[f"yhat_{h}" for h in range(1, yhat_normalizado.shape[1] + 1)])
    df.insert(0, "id_amostra", np.asarray(id_amostra, dtype=np.int64))
    if str(caminho).endswith(".csv"):
        df.to_csv(caminho, index=False)
    else:
        df.to_parquet(caminho, index=False)


def desnormalizar(yhat: np.ndarray, normalizacao: dict[str, Any]) -> np.ndarray:
    media = np.asarray(normalizacao["alvo"]["media"], dtype=np.float64)
    desvio = np.asarray(normalizacao["alvo"]["desvio"], dtype=np.float64)
    return np.asarray(yhat, dtype=np.float64) * desvio + media


def para_cobre(preco_base: np.ndarray, log_retorno: np.ndarray) -> np.ndarray:
    return np.rint(preco_base[:, None].astype(np.float64) * np.exp(log_retorno)).astype(np.int64)


def avaliar(dados: DadosPreparados, periodo: str, id_amostra: np.ndarray, yhat: np.ndarray,
            limiar_mape: Optional[float] = None) -> Avaliacao:
    H = dados.horizonte
    limiar = float(limiar_mape if limiar_mape is not None else dados.normalizacao["config"]["limiar_mape"])
    jan = dados.janelas(periodo).set_index("id_amostra")
    faltando = np.setdiff1d(id_amostra, jan.index.to_numpy())
    if faltando.size:
        raise KeyError(f"{faltando.size} id_amostra não pertencem a janelas_{periodo} (ex.: {faltando[:5].tolist()})")
    jan = jan.loc[id_amostra]

    base = jan["preco_base"].to_numpy(dtype=np.int64)
    previsto = para_cobre(base, desnormalizar(yhat, dados.normalizacao))
    origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
    alvo = origem[:, None] + np.arange(1, H + 1)[None, :]

    orig = dados.originais
    serie_o = orig["serie"].to_numpy()
    if not (serie_o[alvo] == serie_o[origem][:, None]).all():
        raise AssertionError("alvo fora da série da amostra: a ordem dos arquivos foi alterada")
    real = orig["preco_cobre"].to_numpy(dtype="float64", na_value=np.nan)[alvo]
    avaliavel = orig["observado"].to_numpy()[alvo] & np.isfinite(real)

    det = pd.DataFrame({
        "id_amostra": np.repeat(id_amostra, H),
        "id_linha_origem": np.repeat(origem, H),
        "serie": np.repeat(jan["serie"].to_numpy(), H),
        "item_id": np.repeat(jan["item_id"].to_numpy(), H),
        "data_origem": np.repeat(jan["data_origem"].to_numpy(), H),
        "h": np.tile(np.arange(1, H + 1), len(id_amostra)),
        "id_linha_alvo": alvo.ravel(),
        "data_alvo": orig["data"].to_numpy()[alvo].ravel(),
        "preco_base": np.repeat(base, H),
        "preco_real": real.ravel(),
        "preco_previsto": previsto.ravel(),
        "avaliavel": avaliavel.ravel(),
    })
    det["preco_ingenuo"] = det["preco_base"]
    det["erro_abs"] = (det["preco_previsto"] - det["preco_real"]).abs()
    det["erro_pct"] = det["erro_abs"] / det["preco_real"]
    det["erro_pct_ingenuo"] = (det["preco_ingenuo"] - det["preco_real"]).abs() / det["preco_real"]
    det.loc[~det["avaliavel"], ["erro_abs", "erro_pct", "erro_pct_ingenuo"]] = np.nan

    ok = det[det["avaliavel"]]
    por_item = ok.groupby(["serie", "item_id"]).agg(
        n=("erro_pct", "size"),
        mape=("erro_pct", "mean"),
        mape_ingenuo=("erro_pct_ingenuo", "mean"),
        mae_ouro=("erro_abs", lambda e: e.mean() / COBRE_POR_OURO),
        rmse_ouro=("erro_abs", lambda e: float(np.sqrt((e ** 2).mean())) / COBRE_POR_OURO),
    ).reset_index()
    # RN10: projeção liberada se o MAPE do item ficar no limiar e abaixo do modelo ingênuo.
    por_item["supera_ingenuo"] = por_item["mape"] < por_item["mape_ingenuo"]
    por_item["situacao"] = np.where((por_item["mape"] <= limiar) & por_item["supera_ingenuo"], "Liberada", "Bloqueada")

    por_h = ok.groupby("h").agg(n=("erro_pct", "size"), mape=("erro_pct", "mean"),
                                mape_ingenuo=("erro_pct_ingenuo", "mean"),
                                mediana_erro_pct=("erro_pct", "median")).reset_index()
    resumo = {
        "periodo": periodo,
        "amostras": int(len(id_amostra)),
        "alvos_avaliados": int(len(ok)),
        "alvos_ignorados_nao_observados": int((~det["avaliavel"]).sum()),
        "itens": int(len(por_item)),
        "mape_medio_por_item": float(por_item["mape"].mean()) if len(por_item) else None,
        "mape_ingenuo_medio_por_item": float(por_item["mape_ingenuo"].mean()) if len(por_item) else None,
        "mape_geral": float(ok["erro_pct"].mean()) if len(ok) else None,
        "itens_que_superam_ingenuo": int(por_item["supera_ingenuo"].sum()),
        "limiar_mape_rn10": limiar,
        "itens_liberados_rn10": int((por_item["situacao"] == "Liberada").sum()),
    }
    return Avaliacao(det, por_item, por_h, resumo)


def gravar(av: Avaliacao, pasta: Path, rotulo: str) -> None:
    base = pasta / f"avaliacao_{av.resumo['periodo']}_{rotulo}"
    av.detalhe.to_parquet(f"{base}_detalhe.parquet", index=False)
    av.por_item.to_csv(f"{base}_itens.csv", index=False)
    av.por_horizonte.to_csv(f"{base}_horizontes.csv", index=False)
    Path(f"{base}_resumo.json").write_text(json.dumps(av.resumo, indent=2, ensure_ascii=False), encoding="utf-8")


def ler_previsoes(caminho: Path, horizonte: int) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(caminho) if str(caminho).endswith(".csv") else pd.read_parquet(caminho)
    cols = [f"yhat_{h}" for h in range(1, horizonte + 1)]
    return df["id_amostra"].to_numpy(dtype=np.int64), df[cols].to_numpy(dtype=np.float64)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--periodo", choices=PERIODOS, default="validacao")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--previsoes", type=Path, help="parquet/csv com id_amostra e yhat_1..yhat_7 (normalizados)")
    modo.add_argument("--ingenuo", action="store_true", help="avalia o modelo ingênuo (preço de hoje para os 7 dias)")
    modo.add_argument("--verificar", action="store_true", help="usa o próprio y verdadeiro: confere o mecanismo")
    ap.add_argument("--limiar-mape", type=float, help="RN10; padrão: o de normalizacao.json")
    ap.add_argument("--rotulo", help="sufixo dos arquivos de saída")
    args = ap.parse_args(argv)

    dados = DadosPreparados(args.pasta)
    jan = dados.janelas(args.periodo)
    if args.previsoes:
        ids, yhat = ler_previsoes(args.previsoes, dados.horizonte)
        rotulo = args.rotulo or args.previsoes.stem
    elif args.ingenuo:
        ids = jan["id_amostra"].to_numpy(dtype=np.int64)
        alvo = dados.normalizacao["alvo"]
        zero = (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"])  # log-retorno 0, já normalizado
        yhat = np.tile(zero, (len(ids), 1))
        rotulo = args.rotulo or "ingenuo"
    else:
        ids = jan["id_amostra"].to_numpy(dtype=np.int64)
        yhat = jan[dados.colunas_alvo()].to_numpy(dtype=np.float64)
        rotulo = args.rotulo or "verificacao"

    av = avaliar(dados, args.periodo, ids, yhat, args.limiar_mape)
    gravar(av, args.pasta, rotulo)
    print(json.dumps(av.resumo, indent=2, ensure_ascii=False))
    print(av.por_horizonte.to_string(index=False))
    if args.verificar:
        ok = av.detalhe[av.detalhe["avaliavel"]]
        pior = float(ok["erro_pct"].max()) if len(ok) else 0.0
        print(f"\nVerificação de ida e volta: maior erro relativo = {pior:.2e} "
              f"({'OK' if pior < 1e-5 else 'FALHOU'}; o resto vem do y gravado em float32)")
        return 0 if pior < 1e-5 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
