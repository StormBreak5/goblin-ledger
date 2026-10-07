"""Erro na troca de expansão (etapa 2d).

Quando sai uma expansão nova, os itens da expansão que estava vigente tendem a perder valor (obsolescência, RN17).
Este script mede, numa avaliação já feita (o arquivo *_detalhe.parquet do avaliar.py), o erro do modelo e o do
ingênuo por grupo de itens e por janela de tempo.

Grupos, em relação ao lançamento avaliado:
    expansão que sai       a vigente antes do lançamento (ex.: The War Within, na troca para Midnight)
    expansão que entra     a do próprio lançamento
    anteriores             as demais, inclusive itens que já existiam quando os dados começam (expansão desconhecida)
Janelas:
    troca                  previsões feitas de --antes dias antes até --depois dias depois do lançamento
    resto                  o restante do período avaliado

A expansão de cada item vem da coluna "expansao" do itens.parquet de uma base preparada com o código da etapa 2d
(pelo primeiro registro do item). Os itens dessa base precisam ser os da avaliação; por exemplo, para avaliar a base
da etapa 2b, use o itens.parquet da base da etapa 2d, que tem os mesmos itens.

Uso
    python transicao.py --base saida/treino2d_exp \\
        --detalhe saida/treino01_agr/avaliacao_validacao_treino01_agr_semmascara_s42_detalhe.parquet --rotulo base_s42
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

COLUNAS = ["item_id", "data_origem", "h", "preco_real", "preco_previsto", "preco_base", "avaliavel", "erro_pct",
           "erro_pct_ingenuo"]
SAI, ENTRA, ANTERIORES = "expansão que sai", "expansão que entra", "anteriores ou desconhecida"


def _medidas(g: pd.DataFrame) -> dict[str, Any]:
    if g.empty:
        return {"alvos": 0}
    md, md_ing = float(g["erro_pct"].median()), float(g["erro_pct_ingenuo"].median())
    return {"alvos": int(len(g)), "itens": int(g["item_id"].nunique()), "mdape": md, "mdape_ingenuo": md_ing,
            "razao": md / md_ing if md_ing > 0 else None,
            "vies_mediano": float(np.expm1(g["vies"].median())),          # > 0: previu acima do preço real
            "variacao_real_mediana": float(np.expm1(g["variacao_real"].median()))}


def analisar(det: pd.DataFrame, expansao_do_item: pd.Series, expansoes: list[str], lancamentos: list[str],
             lancamento: pd.Timestamp, antes: int = 21, depois: int = 30, horizonte: Optional[int] = None) -> pd.DataFrame:
    """Uma linha por janela, grupo e horizonte ("todos" ou o último dia previsto)."""
    datas = [pd.Timestamp(d) for d in lancamentos]
    if lancamento not in datas:
        raise ValueError(f"{lancamento.date()} não é um lançamento registrado ({', '.join(lancamentos)})")
    i = datas.index(lancamento)
    entra, sai = expansoes[i], (expansoes[i - 1] if i > 0 else None)

    d = det[det["avaliavel"]].copy()
    exp = d["item_id"].map(expansao_do_item)
    if exp.isna().any():
        raise KeyError(f"{d.loc[exp.isna(), 'item_id'].nunique()} itens da avaliação não estão no itens.parquet")
    d["grupo"] = np.where(exp == entra, ENTRA, np.where(exp == sai, SAI, ANTERIORES))
    origem = pd.to_datetime(d["data_origem"])
    na_troca = (origem >= lancamento - pd.Timedelta(days=antes)) & (origem < lancamento + pd.Timedelta(days=depois))
    d["janela"] = np.where(na_troca, "troca", "resto")
    d["vies"] = np.log(d["preco_previsto"].astype("float64") / d["preco_real"].astype("float64"))
    d["variacao_real"] = np.log(d["preco_real"].astype("float64") / d["preco_base"].astype("float64"))
    H = int(horizonte or d["h"].max())

    linhas: list[dict[str, Any]] = []
    for janela in ("troca", "resto"):
        for grupo in (SAI, ENTRA, ANTERIORES, "todos"):
            sel = d[(d["janela"] == janela) & ((d["grupo"] == grupo) if grupo != "todos" else True)]
            for rot_h, g in (("todos", sel), (f"h{H}", sel[sel["h"] == H])):
                linhas.append({"janela": janela, "grupo": grupo,
                               "expansao": {SAI: sai, ENTRA: entra}.get(grupo, ""), "horizonte": rot_h, **_medidas(g)})
    return pd.DataFrame(linhas)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True,
                    help="base preparada com o código da etapa 2d (itens.parquet e normalizacao.json)")
    ap.add_argument("--detalhe", type=Path, required=True, help="avaliacao_<periodo>_<rotulo>_detalhe.parquet")
    ap.add_argument("--lancamento", help="AAAA-MM-DD; padrão: o último lançamento dentro do período avaliado")
    ap.add_argument("--antes", type=int, default=21)
    ap.add_argument("--depois", type=int, default=30)
    ap.add_argument("--rotulo", required=True)
    args = ap.parse_args(argv)

    norm = json.loads((args.base / "normalizacao.json").read_text(encoding="utf-8"))
    ciclo = norm.get("ciclo_do_item")
    if not ciclo:
        ap.error(f"{args.base} foi preparada antes da etapa 2d (sem ciclo_do_item no normalizacao.json)")
    itens = pd.read_parquet(args.base / "itens.parquet", columns=["item_id", "expansao"])
    det = pd.read_parquet(args.detalhe, columns=COLUNAS)
    if args.lancamento:
        lancamento = pd.Timestamp(args.lancamento)
    else:
        ini, fim = pd.to_datetime(det["data_origem"]).min(), pd.to_datetime(det["data_origem"]).max()
        dentro = [pd.Timestamp(x) for x in ciclo["lancamentos"] if ini <= pd.Timestamp(x) <= fim]
        if not dentro:
            ap.error("nenhum lançamento de expansão dentro do período avaliado; informe --lancamento")
        lancamento = dentro[-1]
    tab = analisar(det, itens.set_index("item_id")["expansao"], ciclo["expansoes"], ciclo["lancamentos"], lancamento,
                   args.antes, args.depois)
    destino = args.detalhe.parent / f"transicao_{args.rotulo}.csv"
    tab.to_csv(destino, index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.float_format", lambda v: f"{v:.4f}")
    print(f"Lançamento avaliado: {lancamento.date()} | troca: de {args.antes} dias antes a {args.depois} dias depois")
    print(tab.to_string(index=False))
    print(f"\nGravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
