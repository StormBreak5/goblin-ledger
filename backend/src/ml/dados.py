"""CU11-C1 passo 3: leitura da série histórica harmonizada e dos dados que alimentam as variáveis (porte de
`estudos/lstm/io_dados.py`, modo banco).

Só entra a série diária da Undermine Exchange (RN16), sem os volumes marcados como anômalos (RN12). O preço da
Undermine é o menor preço do dia; a série horária da Blizzard (RN06) não entra.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.ml.configuracao import ConfigModelo

logger = logging.getLogger(__name__)

COLUNAS_PRECOS = ["serie", "item_id", "data", "preco", "quantidade"]
COLUNAS_ITENS = ["item_id", "classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc", "commodity"]
COLUNAS_EVENTOS = ["tipo", "nome", "versao", "data_inicio", "data_fim", "regiao"]

# Qualidade do item na API da Blizzard (quality.type).
QUALIDADES = {"POOR": 0, "COMMON": 1, "UNCOMMON": 2, "RARE": 3, "EPIC": 4, "LEGENDARY": 5, "ARTIFACT": 6, "HEIRLOOM": 7}


@dataclass
class Entrada:
    precos: pd.DataFrame             # serie, item_id, data, preco (Cobre, RN01), quantidade
    itens: pd.DataFrame              # atributos fixos; colunas ausentes = desconhecidas
    eventos: pd.DataFrame            # evento_jogo
    regiao_da_serie: dict[str, str]  # serie (historical_item_prices.region) -> 'US' / 'EU'
    aptos: set[int]                  # itens "Apto ao treinamento" (RN15, CU10-C3)


# --------------------------------------------------------------------------------------------- padronização dos quadros
def padronizar_precos(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLUNAS_PRECOS].copy()
    df["serie"] = df["serie"].astype(str)
    df["item_id"] = df["item_id"].astype("int64")
    df["data"] = pd.to_datetime(df["data"]).dt.normalize().astype("datetime64[ns]")
    df["preco"] = pd.to_numeric(df["preco"], errors="coerce").astype("float64")
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").astype("float64")
    # Mais de um ponto no mesmo dia: fica o menor preço (a Undermine guarda o mínimo do dia) e a maior quantidade.
    return df.groupby(["serie", "item_id", "data"], as_index=False).agg(preco=("preco", "min"),
                                                                        quantidade=("quantidade", "max"))


def padronizar_itens(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in COLUNAS_ITENS}).astype({"item_id": "int64"})
    df = df.copy()
    for c in COLUNAS_ITENS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLUNAS_ITENS]
    df["item_id"] = df["item_id"].astype("int64")
    for c in ("classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["commodity"] = df["commodity"].map(lambda v: bool(v) if pd.notna(v) else np.nan)
    return df.drop_duplicates("item_id", keep="last")


def padronizar_eventos(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUNAS_EVENTOS})
    df = df.copy()
    for c in COLUNAS_EVENTOS:
        if c not in df.columns:
            df[c] = None
    df = df[COLUNAS_EVENTOS]
    df["tipo"] = df["tipo"].astype(str).str.upper()
    df["regiao"] = df["regiao"].fillna("GLOBAL").astype(str).str.upper()
    df["data_inicio"] = pd.to_datetime(df["data_inicio"]).dt.normalize().astype("datetime64[ns]")
    df["data_fim"] = pd.to_datetime(df["data_fim"]).dt.normalize().astype("datetime64[ns]")
    return df


def regiao_por_serie(series: list[str], reinos: dict[int, str], cfg: ConfigModelo) -> dict[str, str]:
    """Região (RN11) de cada série: o reino conectado (tabela `reino`) ou o id de commodities da região."""
    commodities = {str(v): k for k, v in cfg.commodities_por_regiao.items()}
    regioes: dict[str, str] = {}
    for s in series:
        if s in commodities:
            regioes[s] = commodities[s]
        elif s.isdigit() and int(s) in reinos:
            regioes[s] = reinos[int(s)]
        elif s.upper() in ("US", "EU"):
            regioes[s] = s.upper()
    return regioes


def _primeiro(meta: dict[str, Any], *chaves: str) -> Any:
    for chave in chaves:
        valor = meta.get(chave)
        if isinstance(valor, dict):  # formato da API da Blizzard: {"id": 7, "name": ...} ou {"type": "EPIC", ...}
            valor = valor.get("id", valor.get("type", valor.get("value")))
        if valor is not None:
            return valor
    return None


def atributos_do_metadata(item_id: int, meta: Optional[dict[str, Any]],
                          ids_commodities: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Atributos fixos gravados em items.metadata_info (populate_item_details): classe, subclasse, qualidade, nível e
    preço de venda ao vendedor (variáveis 15 a 17).

    Commodity (variável 18): sem a chave explícita, vale a origem do arquivo da Undermine (`source_region`, gravada pelo
    CU10-C1). O histórico é gravado sob o reino pedido (3209) também para as commodities, então só a origem distingue
    o item de commodity (arquivo do id de commodities da região, 32512 nos EUA)."""
    meta = meta or {}
    qualidade = _primeiro(meta, "quality", "qualidade")
    if isinstance(qualidade, str):
        qualidade = QUALIDADES.get(qualidade.upper())
    commodity = _primeiro(meta, "is_commodity", "commodity")
    if commodity is None and meta.get("source_region") is not None:
        commodity = str(meta["source_region"]) in ids_commodities
    return {
        "item_id": item_id,
        "classe_id": _primeiro(meta, "item_class_id", "classe_id", "item_class"),
        "subclasse_id": _primeiro(meta, "item_subclass_id", "subclasse_id", "item_subclass"),
        "qualidade": qualidade,
        "nivel_item": _primeiro(meta, "level", "item_level", "nivel_item"),
        "preco_npc": _primeiro(meta, "sell_price", "preco_npc"),
        "commodity": commodity,
    }


# ----------------------------------------------------------------------------------------------------------- banco
SQL_PRECOS = text("""
    SELECT h.region AS serie, h.item_id, (h."timestamp")::date AS data,
           MIN(h.price) AS preco, MAX(h.quantity) AS quantidade
      FROM historical_item_prices h
     WHERE h.origem = 'UNDERMINE' AND h.granularidade = 'DIARIA' AND NOT h.anomalia
     GROUP BY 1, 2, 3
""")


def carregar_banco(conexao: Connection, cfg: ConfigModelo) -> Entrada:
    """CU11-C1 passo 3 (RN16): a série diária da Undermine, os atributos dos itens, os eventos do jogo (RN17), os
    reinos (RN11) e a aptidão ao treinamento (RN15). Uma falha de banco aqui é o CU11-C1-FE2."""
    logger.info("CU11: lendo historical_item_prices (Undermine, diária)...")
    partes = list(pd.read_sql_query(SQL_PRECOS, conexao, chunksize=2_000_000))
    precos = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=COLUNAS_PRECOS)
    meta = pd.read_sql_query(text("SELECT external_item_id, metadata_info FROM items WHERE game = 'wow'"), conexao)
    eventos = pd.read_sql_query(text("SELECT tipo, nome, versao, data_inicio, data_fim, regiao FROM evento_jogo"),
                                conexao)
    reinos = {int(r.id_reino): str(r.regiao) for r in
              pd.read_sql_query(text("SELECT id_reino, regiao FROM reino"), conexao).itertuples()}
    aptos_df = pd.read_sql_query(text("SELECT item_id FROM aptidao_treinamento WHERE apto"), conexao)

    ids_commodities = frozenset(str(v) for v in cfg.commodities_por_regiao.values())
    atributos = pd.DataFrame([
        atributos_do_metadata(int(r.external_item_id), r.metadata_info, ids_commodities)
        for r in meta.itertuples() if str(r.external_item_id).isdigit()
    ])
    precos = padronizar_precos(precos)
    return Entrada(
        precos=precos,
        itens=padronizar_itens(atributos),
        eventos=padronizar_eventos(eventos),
        regiao_da_serie=regiao_por_serie(sorted(precos["serie"].unique()), reinos, cfg),
        aptos=set(aptos_df["item_id"].astype(int)),
    )
