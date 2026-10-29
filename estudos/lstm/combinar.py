"""Etapa 2g: combinações das previsões já gravadas, sem treino novo.

- media: a média de vários arquivos de previsões da mesma base, na escala normalizada. Na mesma base, todos usam a
  mesma escala do alvo (RN24), então a média normalizada é a média dos log-retornos previstos.
- encolher: log-retorno final = α_h × log-retorno previsto, com um α_h entre 0 e 1 por horizonte (α = 0 é o ingênuo).
  A validação é dividida ao meio pela data. α_h é escolhido na 1ª metade: a menor mediana, entre os itens, do MdAPE do
  item no horizonte h (empate: o maior α, o mais perto do modelo). As previsões são gravadas só para a 2ª metade, onde
  são medidas. Como na RN25, as amostras cujos dias previstos atravessam o meio ficam fora das duas metades.
  Grava, para a 2ª metade, <nome>.parquet (encolhidas), ref2<...>.parquet (as mesmas, sem encolher) e ing2.parquet (o
  ingênuo), mais <nome>.json com os α_h e o MdAPE da 1ª metade para cada α.

Uso
    python combinar.py media --nome ens3 --saida saida/base/combinadas --previsoes a.parquet b.parquet c.parquet
    python combinar.py encolher --pasta saida/base --nome enc_s42 --saida saida/base/combinadas --previsoes a.parquet
    python avaliar.py --pasta saida/base --periodo validacao --previsoes saida/base/combinadas/enc_s42.parquet --rotulo enc_s42
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from avaliar import desnormalizar, ler_previsoes, salvar_previsoes
from dataset import DadosPreparados

GRADE = tuple(round(0.05 * k, 2) for k in range(21))  # 0, 0,05, ..., 1


def _ler(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho) if str(caminho).endswith(".csv") else pd.read_parquet(caminho)
    return df.sort_values("id_amostra").reset_index(drop=True)


def media(arquivos: list[Path]) -> tuple[np.ndarray, np.ndarray]:
    """A média das previsões normalizadas. Todos os arquivos precisam ter as mesmas amostras e horizontes."""
    if len(arquivos) < 2:
        raise ValueError("a média precisa de pelo menos dois arquivos de previsões")
    tabelas = [_ler(a) for a in arquivos]
    cols = [c for c in tabelas[0].columns if c.startswith("yhat_")]
    ids = tabelas[0]["id_amostra"].to_numpy(dtype=np.int64)
    for arquivo, t in zip(arquivos[1:], tabelas[1:]):
        if [c for c in t.columns if c.startswith("yhat_")] != cols or \
                not np.array_equal(t["id_amostra"].to_numpy(dtype=np.int64), ids):
            raise ValueError(f"{arquivo} não tem as mesmas amostras e horizontes de {arquivos[0]}")
    return ids, np.mean([t[cols].to_numpy(dtype=np.float64) for t in tabelas], axis=0)


def encolher(yhat: np.ndarray, alfa: list[float] | np.ndarray, normalizacao: dict[str, Any]) -> np.ndarray:
    """log-retorno encolhido = α_h × log-retorno previsto, devolvido na escala normalizada (a que o avaliar.py lê)."""
    media_alvo = np.asarray(normalizacao["alvo"]["media"], dtype=np.float64)
    desvio = np.asarray(normalizacao["alvo"]["desvio"], dtype=np.float64)
    r = desnormalizar(yhat, normalizacao)
    return (np.asarray(alfa, dtype=np.float64)[None, :] * r - media_alvo) / desvio


def meio_da_validacao(normalizacao: dict[str, Any]) -> pd.Timestamp:
    cv = pd.Timestamp(normalizacao["cortes"]["corte_validacao"])
    ct = pd.Timestamp(normalizacao["cortes"]["corte_teste"])
    return cv + pd.Timedelta(days=(ct - cv).days // 2)


def metades(jan: pd.DataFrame, meio: pd.Timestamp, horizonte: int) -> tuple[np.ndarray, np.ndarray]:
    """1ª metade: todos os dias previstos antes do meio. 2ª: todos a partir do meio. As que atravessam o meio ficam de
    fora das duas (como as amostras que atravessam uma data de corte, RN25). O calendário de cada série é diário e
    contínuo, então o dia previsto h é data_origem + h dias."""
    origem = pd.to_datetime(jan["data_origem"])
    primeira = (origem + pd.Timedelta(days=horizonte)) < meio
    segunda = (origem + pd.Timedelta(days=1)) >= meio
    return primeira.to_numpy(), segunda.to_numpy()


def escolher_alfas(dados: DadosPreparados, jan: pd.DataFrame, yhat: np.ndarray,
                   grade: tuple[float, ...] = GRADE) -> tuple[list[float], dict[str, dict[str, float]]]:
    """Para cada horizonte, o α da grade com a menor mediana, entre os itens, do MdAPE do item nesse horizonte, só nos
    dias com preço observado (os mesmos que o avaliar.py avalia). Empate: o maior α."""
    H = dados.horizonte
    origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
    alvo = origem[:, None] + np.arange(1, H + 1)[None, :]
    orig = dados.originais
    real = orig["preco_cobre"].to_numpy(dtype="float64", na_value=np.nan)[alvo]
    avaliavel = orig["observado"].to_numpy()[alvo] & np.isfinite(real)
    base = jan["preco_base"].to_numpy(dtype=np.float64)
    r = desnormalizar(yhat, dados.normalizacao)
    item = pd.factorize(pd.MultiIndex.from_arrays([jan["serie"].astype(str).to_numpy(),
                                                   jan["item_id"].to_numpy()]))[0]
    alfas: list[float] = []
    tabela: dict[str, dict[str, float]] = {}
    for h in range(H):
        ok = avaliavel[:, h]
        b, rr, re, k = base[ok], r[ok, h], real[ok, h], item[ok]
        melhor, melhor_alfa = np.inf, 1.0
        tabela[str(h + 1)] = {}
        for a in grade:
            erro = np.abs(np.rint(b * np.exp(a * rr)) - re) / re
            valor = float(pd.Series(erro).groupby(k).median().median())
            tabela[str(h + 1)][f"{a:.2f}"] = valor
            if valor <= melhor:  # a grade é crescente: no empate, fica o maior α
                melhor, melhor_alfa = valor, float(a)
        alfas.append(melhor_alfa)
    return alfas, tabela


def nome_da_referencia(nome: str) -> str:
    return "ref2" + nome[3:] if nome.startswith("enc") else f"{nome}_ref2"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    me = sub.add_parser("media", help="média de vários arquivos de previsões da mesma base")
    me.add_argument("--previsoes", type=Path, nargs="+", required=True)
    me.add_argument("--nome", required=True)
    me.add_argument("--saida", type=Path, required=True)
    en = sub.add_parser("encolher", help="α por horizonte na 1ª metade da validação, previsões da 2ª metade")
    en.add_argument("--pasta", type=Path, required=True, help="a base das previsões")
    en.add_argument("--previsoes", type=Path, required=True, help="previsões de validação de um modelo")
    en.add_argument("--nome", required=True)
    en.add_argument("--saida", type=Path, required=True)
    en.add_argument("--nome-ref", help="previsões da 2ª metade sem encolher; padrão: ref2_<sufixo> de enc_<sufixo>")
    en.add_argument("--nome-ingenuo", default="ing2", help="o ingênuo na 2ª metade")
    args = ap.parse_args(argv)
    args.saida.mkdir(parents=True, exist_ok=True)

    if args.comando == "media":
        ids, yhat = media(args.previsoes)
        salvar_previsoes(ids, yhat, args.saida / f"{args.nome}.parquet")
        print(f"{args.nome}: média de {len(args.previsoes)} arquivos, {len(ids):,} amostras -> "
              f"{args.saida / f'{args.nome}.parquet'}")
        return 0

    dados = DadosPreparados(args.pasta)
    H = dados.horizonte
    ids, yhat = ler_previsoes(args.previsoes, H)
    jan = dados.janelas("validacao").set_index("id_amostra")
    faltando = np.setdiff1d(ids, jan.index.to_numpy())
    if faltando.size:
        raise KeyError(f"{faltando.size} id_amostra não pertencem a janelas_validacao (ex.: {faltando[:5].tolist()})")
    jan = jan.loc[ids].reset_index()
    meio = meio_da_validacao(dados.normalizacao)
    primeira, segunda = metades(jan, meio, H)
    alfas, tabela = escolher_alfas(dados, jan[primeira], yhat[primeira])

    nome_ref = args.nome_ref or nome_da_referencia(args.nome)
    zero = (0.0 - np.asarray(dados.normalizacao["alvo"]["media"])) / np.asarray(dados.normalizacao["alvo"]["desvio"])
    ids2, yhat2 = ids[segunda], yhat[segunda]
    salvar_previsoes(ids2, encolher(yhat2, alfas, dados.normalizacao), args.saida / f"{args.nome}.parquet")
    salvar_previsoes(ids2, yhat2, args.saida / f"{nome_ref}.parquet")
    salvar_previsoes(ids2, np.tile(zero, (len(ids2), 1)), args.saida / f"{args.nome_ingenuo}.parquet")
    info = {
        "previsoes": str(args.previsoes),
        "meio": meio.date().isoformat(),
        "amostras": {"primeira_metade": int(primeira.sum()), "segunda_metade": int(segunda.sum()),
                     "atravessam_o_meio": int((~primeira & ~segunda).sum())},
        "alfa": alfas,
        "mdape_primeira_metade": tabela,
        "arquivos": {"encolhidas": f"{args.nome}.parquet", "sem_encolher": f"{nome_ref}.parquet",
                     "ingenuo": f"{args.nome_ingenuo}.parquet"},
    }
    (args.saida / f"{args.nome}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: info[k] for k in ("meio", "amostras", "alfa")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
