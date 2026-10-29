"""Carga dos dados de entrada do estudo, a partir do banco do Goblin Ledger ou de arquivos CSV.

Os dois caminhos devolvem o mesmo formato (classe `Entrada`), e o restante do estudo não sabe de onde os dados vieram.

Banco: lê somente a série diária da Undermine Exchange (RN16), sem os volumes marcados como anômalos (RN12).
CSV:   uma pasta com precos.csv e, opcionalmente, itens.csv, eventos.csv, reinos.csv e aptos.csv
       (o gerador de dados sintéticos escreve exatamente esse formato).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import Config

logger = logging.getLogger(__name__)

COLUNAS_PRECOS = ["serie", "item_id", "data", "preco", "quantidade"]
COLUNAS_ITENS = ["item_id", "classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc", "commodity"]
COLUNAS_EVENTOS = ["tipo", "nome", "versao", "data_inicio", "data_fim", "regiao"]

# Qualidade do item na API da Blizzard (quality.type).
QUALIDADES = {"POOR": 0, "COMMON": 1, "UNCOMMON": 2, "RARE": 3, "EPIC": 4, "LEGENDARY": 5, "ARTIFACT": 6, "HEIRLOOM": 7}


@dataclass
class Entrada:
    precos: pd.DataFrame            # serie, item_id, data, preco (Cobre, RN01), quantidade
    itens: pd.DataFrame             # atributos fixos; colunas ausentes = desconhecidas
    eventos: pd.DataFrame           # evento_jogo
    regiao_da_serie: dict[str, str]  # serie (historical_item_prices.region) -> 'US' / 'EU'
    aptos: Optional[set[int]]        # itens "Apto ao treinamento" (RN15); None = não filtrar
    origem: str


# --------------------------------------------------------------------------------------------- padronização dos quadros
def _padronizar_precos(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLUNAS_PRECOS].copy()
    df["serie"] = df["serie"].astype(str)
    df["item_id"] = df["item_id"].astype("int64")
    df["data"] = pd.to_datetime(df["data"]).dt.normalize().astype("datetime64[ns]")
    df["preco"] = pd.to_numeric(df["preco"], errors="coerce").astype("float64")
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").astype("float64")
    # Mais de um ponto no mesmo dia: fica o menor preço (a Undermine guarda o mínimo do dia) e a maior quantidade.
    df = df.groupby(["serie", "item_id", "data"], as_index=False).agg(preco=("preco", "min"), quantidade=("quantidade", "max"))
    return df


def _padronizar_itens(df: Optional[pd.DataFrame]) -> pd.DataFrame:
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


def _padronizar_eventos(df: Optional[pd.DataFrame]) -> pd.DataFrame:
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


def _regiao_por_serie(series: list[str], reinos: dict[int, str], cfg: Config) -> dict[str, str]:
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


# ------------------------------------------------------------------------------------------------------------- CSV
def carregar_csv(pasta: Path, cfg: Config) -> Entrada:
    def ler(nome: str) -> Optional[pd.DataFrame]:
        caminho = pasta / nome
        return pd.read_csv(caminho) if caminho.exists() else None

    precos = ler("precos.csv")
    if precos is None:
        raise FileNotFoundError(f"{pasta / 'precos.csv'} não encontrado")
    precos = _padronizar_precos(precos)
    reinos_df = ler("reinos.csv")
    reinos = {} if reinos_df is None else {int(r.serie): str(r.regiao).upper() for r in reinos_df.itertuples()}
    aptos_df = ler("aptos.csv")
    return Entrada(
        precos=precos,
        itens=_padronizar_itens(ler("itens.csv")),
        eventos=_padronizar_eventos(ler("eventos.csv")),
        regiao_da_serie=_regiao_por_serie(sorted(precos["serie"].unique()), reinos, cfg),
        aptos=None if aptos_df is None else set(aptos_df["item_id"].astype(int)),
        origem=f"csv:{pasta}",
    )


def carregar_eventos_csv(pasta: Path) -> pd.DataFrame:
    """Só o eventos.csv (etapa 2h: o calendário futuro não precisa dos preços)."""
    caminho = Path(pasta) / "eventos.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não encontrado")
    return _padronizar_eventos(pd.read_csv(caminho))


# ----------------------------------------------------------------------------------------------------------- banco
def url_do_banco() -> str:
    """Mesma montagem do backend (src/repositories/database.py). A porta padrão aqui é a 5435, a que o
    docker-compose expõe para quem roda fora do container."""
    user = os.getenv("DB_USER", "goblin")
    password = os.getenv("DB_PASS", "goblin_password")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5435")
    nome = os.getenv("DB_NAME", "goblinledger")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{nome}"


def _primeiro(meta: dict[str, Any], *chaves: str) -> Any:
    for chave in chaves:
        valor = meta.get(chave)
        if isinstance(valor, dict):  # formato da API da Blizzard: {"id": 7, "name": ...} ou {"type": "EPIC", ...}
            valor = valor.get("id", valor.get("type", valor.get("value")))
        if valor is not None:
            return valor
    return None


def _atributos_do_metadata(item_id: int, meta: Optional[dict[str, Any]],
                           ids_commodities: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Atributos fixos gravados pelo backend em items.metadata_info (populate_item_details): classe, subclasse,
    qualidade, nível e preço de venda ao vendedor.

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


SQL_EVENTOS = "SELECT tipo, nome, versao, data_inicio, data_fim, regiao FROM evento_jogo"


def carregar_eventos_banco(url: str) -> pd.DataFrame:
    """Só evento_jogo (etapa 2h), com a mesma consulta e a mesma padronização de carregar_banco."""
    from sqlalchemy import create_engine, text

    with create_engine(url).connect() as con:
        return _padronizar_eventos(pd.read_sql_query(text(SQL_EVENTOS), con))


def carregar_banco(url: str, cfg: Config, itens: Optional[list[int]] = None) -> Entrada:
    from sqlalchemy import create_engine, text  # import aqui: o modo CSV não precisa do SQLAlchemy

    engine = create_engine(url)
    filtro = "AND h.item_id = ANY(:itens)" if itens else ""
    sql_precos = text(f"""
        SELECT h.region AS serie, h.item_id, (h."timestamp")::date AS data,
               MIN(h.price) AS preco, MAX(h.quantity) AS quantidade
          FROM historical_item_prices h
         WHERE h.origem = 'UNDERMINE' AND h.granularidade = 'DIARIA' AND NOT h.anomalia {filtro}
         GROUP BY 1, 2, 3
    """)
    params = {"itens": list(itens)} if itens else {}
    with engine.connect() as con:
        logger.info("Lendo historical_item_prices (Undermine, diária)...")
        partes = list(pd.read_sql_query(sql_precos, con, params=params, chunksize=2_000_000))
        precos = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=COLUNAS_PRECOS)

        meta = pd.read_sql_query(text("SELECT external_item_id, metadata_info FROM items WHERE game = 'wow'"), con)
        eventos = pd.read_sql_query(text(SQL_EVENTOS), con)
        reinos = {int(r.id_reino): str(r.regiao) for r in
                  pd.read_sql_query(text("SELECT id_reino, regiao FROM reino"), con).itertuples()}
        aptos_df = pd.read_sql_query(text("SELECT item_id, apto FROM aptidao_treinamento"), con)

    ids_commodities = frozenset(str(v) for v in cfg.commodities_por_regiao.values())
    atributos = pd.DataFrame([
        _atributos_do_metadata(int(r.external_item_id), r.metadata_info, ids_commodities)
        for r in meta.itertuples() if str(r.external_item_id).isdigit()
    ])
    precos = _padronizar_precos(precos)
    aptos = None if aptos_df.empty else set(aptos_df.loc[aptos_df["apto"], "item_id"].astype(int))
    if aptos is None:
        logger.warning("aptidao_treinamento está vazia (CU10-C3 ainda não rodou): nenhum filtro de aptidão (RN15).")
    return Entrada(
        precos=precos,
        itens=_padronizar_itens(atributos),
        eventos=_padronizar_eventos(eventos),
        regiao_da_serie=_regiao_por_serie(sorted(precos["serie"].unique()), reinos, cfg),
        aptos=aptos,
        origem="banco",
    )
