"""Gera dados sintéticos no formato do modo --csv, para testar o estudo sem o banco.

Os preços imitam o que se vê na Casa de Leilões: escalas de poucas moedas de cobre a milhões de ouro, sazonalidade
semanal, saltos nos patches, picos de manipulação (RN03), dias sem registro e um apagão de 4 dias em todos os itens.

Uso
    python gerar_sinteticos.py --pasta dados_sinteticos --itens 60
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

SERIE_REINO = "3209"
SERIE_COMMODITIES = "32512"


def eventos_sinteticos() -> pd.DataFrame:
    ev: list[dict[str, object]] = []
    for nome, data in (("Expansão A", "2022-11-28"), ("Expansão B", "2024-08-26"), ("Expansão C", "2026-03-02")):
        ev.append({"tipo": "EXPANSAO", "nome": nome, "versao": None, "data_inicio": data, "data_fim": None})
    ev.append({"tipo": "PATCH", "nome": "Pré-patch B", "versao": "11.0.0", "data_inicio": "2024-07-23", "data_fim": None})
    for i, data in enumerate(pd.date_range("2023-01-24", "2026-09-30", freq="77D")):
        ev.append({"tipo": "PATCH", "nome": f"Patch {i + 1}", "versao": f"x.{i}", "data_inicio": data.date(),
                   "data_fim": None})
    for i, data in enumerate(("2022-12-12", "2023-05-08", "2023-11-14", "2024-04-22", "2024-09-10", "2025-03-04",
                              "2025-08-12", "2026-03-17")):
        ev.append({"tipo": "TEMPORADA", "nome": f"Temporada {i + 1}", "versao": None, "data_inicio": data,
                   "data_fim": None})
    for ano in range(2022, 2027):
        ev.append({"tipo": "EVENTO_SAZONAL", "nome": "Festival de inverno", "versao": None,
                   "data_inicio": f"{ano}-12-16", "data_fim": f"{ano + 1}-01-02"})
        ev.append({"tipo": "EVENTO_SAZONAL", "nome": "Festival de verão", "versao": None,
                   "data_inicio": f"{ano}-06-21", "data_fim": f"{ano}-07-05"})
    for mes in pd.date_range("2022-09-01", "2026-12-01", freq="MS"):
        domingo = mes + pd.Timedelta(days=(6 - mes.dayofweek) % 7)  # primeiro domingo do mês, uma semana
        ev.append({"tipo": "RECORRENTE", "nome": "Darkmoon Faire", "versao": None, "data_inicio": domingo.date(),
                   "data_fim": (domingo + pd.Timedelta(days=6)).date()})
    df = pd.DataFrame(ev)
    df["regiao"] = "GLOBAL"
    return df


def gerar(n_itens: int = 60, inicio: str = "2022-09-01", fim: str = "2026-10-05", semente: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(semente)
    datas = pd.date_range(inicio, fim, freq="D")
    eventos = eventos_sinteticos()
    patches = pd.to_datetime(eventos.loc[eventos["tipo"].isin(["PATCH", "EXPANSAO"]), "data_inicio"])
    eh_patch = datas.isin(patches)
    apagao = (datas >= "2024-05-10") & (datas <= "2024-05-13")  # 4 dias sem dados em todos os itens

    subclasses = [(7, 1), (7, 5), (7, 8), (2, 7), (4, 2), (0, 0)]  # (classe, subclasse) da API da Blizzard
    choque_sub = {s: rng.normal(0, 0.12, len(datas)) * eh_patch for s in subclasses}

    precos: list[pd.DataFrame] = []
    itens: list[dict[str, object]] = []
    for k in range(n_itens):
        item_id = 200_000 + k
        classe, sub = subclasses[k % len(subclasses)]
        equipamento = classe in (2, 4)
        serie = SERIE_REINO if equipamento else SERIE_COMMODITIES
        nivel = 10 ** rng.uniform(1, 10.7)                 # de 10 cobre a ~5 milhões de ouro
        vol = rng.uniform(0.01, 0.07)
        ar = rng.uniform(0.90, 0.99)
        desvio = np.zeros(len(datas))
        ruido = rng.normal(0, vol, len(datas)) + choque_sub[(classe, sub)] + rng.normal(0, 0.05, len(datas)) * eh_patch
        for t in range(1, len(datas)):
            desvio[t] = ar * desvio[t - 1] + ruido[t]
        tendencia = np.cumsum(rng.normal(0, vol / 6, len(datas)))
        semana = 0.03 * np.sin(2 * np.pi * datas.dayofweek.to_numpy() / 7 + rng.uniform(0, 6))
        preco = np.maximum(np.rint(nivel * np.exp(desvio + tendencia + semana)), 1)
        q_base = 10 ** rng.uniform(1.5, 4.7)
        quantidade = np.rint(q_base * np.exp(rng.normal(0, 0.3, len(datas)) - 0.5 * desvio))

        pico = rng.random(len(datas)) < 0.003
        preco = np.where(pico, preco * 8, preco)           # manipulação: deve cair na RN03
        presente = (rng.random(len(datas)) > 0.01) & ~apagao
        comeco = 0 if k % 5 else int(rng.integers(200, 700))  # alguns itens só aparecem depois
        presente[:comeco] = False
        precos.append(pd.DataFrame({"serie": serie, "item_id": item_id, "data": datas[presente].date,
                                    "preco": preco[presente].astype("int64"), "quantidade": quantidade[presente]}))
        conhecido = k % 7 != 6                              # parte dos itens sem atributos (metadata vazia)
        itens.append({
            "item_id": item_id,
            "classe_id": classe if conhecido and classe else None,
            "subclasse_id": sub if conhecido and classe else None,
            "qualidade": int(rng.integers(1, 5)) if conhecido else None,
            "nivel_item": int(rng.integers(500, 700)) if conhecido and equipamento else (1 if conhecido else None),
            "preco_npc": int(nivel * rng.uniform(0.05, 0.6)) if conhecido and k % 3 else None,
            "commodity": not equipamento,
        })
    return {
        "precos": pd.concat(precos, ignore_index=True),
        "itens": pd.DataFrame(itens),
        "eventos": eventos,
        "reinos": pd.DataFrame({"serie": [int(SERIE_REINO)], "regiao": ["US"]}),
        "aptos": pd.DataFrame({"item_id": [200_000 + k for k in range(n_itens) if k != 3]}),
    }


def gravar(dados: dict[str, pd.DataFrame], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, df in dados.items():
        df.to_csv(pasta / f"{nome}.csv", index=False)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--itens", type=int, default=60)
    ap.add_argument("--semente", type=int, default=7)
    args = ap.parse_args(argv)
    gravar(gerar(args.itens, semente=args.semente), args.pasta)
    print(f"Dados sintéticos gravados em {args.pasta.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
