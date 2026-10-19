"""Dados sintéticos para os testes do CU11 (porte de `estudos/lstm/gerar_sinteticos.py`).

Os preços imitam o que se vê na Casa de Leilões: escalas de poucas moedas de cobre a milhões de ouro, sazonalidade
semanal, saltos nos patches, picos de manipulação (RN03), dias sem registro e um apagão de 4 dias em todos os itens.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

from src.models.cobertura import AptidaoTreinamento
from src.models.evento import EventoJogo
from src.models.item import Item
from src.models.mercado import Reino
from src.scraper.models import HistoricalItemPrice

SERIE_REINO = "3209"
SERIE_COMMODITIES = "32512"
QUALIDADES = ["POOR", "COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]


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


def gerar(n_itens: int = 60, inicio: str = "2022-09-01", fim: str = "2026-10-05",
          semente: int = 7) -> dict[str, pd.DataFrame]:
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


def serie_constante(item_id: int, inicio: str, fim: str, preco: float = 10_000.0, quantidade: float = 500.0,
                    ruido: float = 0.0, semente: int = 0, a_cada: int = 1, serie: str = SERIE_COMMODITIES) -> pd.DataFrame:
    """Um item com preço quase constante (ruído relativo `ruido`), registrado a cada `a_cada` dias até `fim`."""
    datas = pd.date_range(inicio, fim, freq="D")[::-1][::a_cada][::-1]
    rng = np.random.default_rng(semente)
    p = np.rint(preco * np.exp(rng.normal(0, ruido, len(datas)))) if ruido else np.full(len(datas), preco)
    return pd.DataFrame({"serie": serie, "item_id": item_id, "data": datas.date, "preco": p.astype("int64"),
                         "quantidade": quantidade})


def _valor(v: object) -> Optional[object]:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v


def metadata_do_item(linha: dict[str, object]) -> dict[str, object]:
    """Atributos no formato que o populate_item_details grava em items.metadata_info (e a origem do arquivo)."""
    meta: dict[str, object] = {"source_region": SERIE_COMMODITIES if linha.get("commodity") else SERIE_REINO}
    for chave, coluna in (("item_class_id", "classe_id"), ("item_subclass_id", "subclasse_id"),
                          ("level", "nivel_item"), ("sell_price", "preco_npc")):
        valor = _valor(linha.get(coluna))
        if valor is not None:
            meta[chave] = int(valor)  # type: ignore[call-overload]
    qualidade = _valor(linha.get("qualidade"))
    if qualidade is not None:
        meta["quality"] = {"type": QUALIDADES[int(qualidade)]}  # type: ignore[call-overload]
    return meta


def gravar_no_banco(sessao: Session, dados: dict[str, pd.DataFrame], aptos: Optional[set[int]] = None) -> None:
    """Grava os dados sintéticos como o sistema os teria: série diária da Undermine (CU10-C1), atributos dos itens,
    eventos (CU10-C2), reino (CU09) e aptidão ao treinamento (CU10-C3, RN15). `aptos=None` = os de dados["aptos"]."""
    p = dados["precos"]
    sessao.execute(insert(HistoricalItemPrice), [
        {"item_id": int(i), "region": str(s), "timestamp": datetime.combine(pd.Timestamp(d).date(), datetime.min.time()),
         "price": int(v), "quantity": int(q), "origem": "UNDERMINE", "granularidade": "DIARIA", "anomalia": False}
        for s, i, d, v, q in zip(p["serie"], p["item_id"], p["data"], p["preco"], p["quantidade"])
    ])
    for linha in dados["itens"].to_dict("records"):
        sessao.add(Item(game="wow", external_item_id=str(int(linha["item_id"])), name=f"Item {int(linha['item_id'])}",
                        metadata_info=metadata_do_item(linha)))
    for e in dados["eventos"].to_dict("records"):
        sessao.add(EventoJogo(tipo=e["tipo"], nome=e["nome"], versao=_valor(e["versao"]),
                              data_inicio=pd.Timestamp(e["data_inicio"]).date(),
                              data_fim=None if _valor(e["data_fim"]) is None else pd.Timestamp(e["data_fim"]).date(),
                              regiao="GLOBAL", origem="MANUAL"))
    sessao.add(Reino(id_reino=int(SERIE_REINO), nome="Azralon", regiao="US"))
    aptos = set(dados["aptos"]["item_id"].astype(int)) if aptos is None else aptos
    for item_id in sorted(set(p["item_id"].astype(int))):
        sessao.add(AptidaoTreinamento(item_id=item_id, apto=item_id in aptos, periodo_continuo_dias=400,
                                      dias_com_dados=400))
    sessao.commit()
