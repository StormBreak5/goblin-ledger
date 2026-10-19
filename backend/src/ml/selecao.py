"""CU11-C1 passo 2: itens elegíveis à projeção e conjunto de treinamento (porte de `selecionar_series` e
`criterios_dos_itens` de `estudos/lstm/preparar_dados.py`, com a separação da v4).

- Elegíveis à projeção: RN02 (quantidade média > 50 nos últimos 7 dias), RN27 (ao menos 60 dias de histórico diário) e
  RN07 (equipamento com nível de item abaixo do mínimo fica de fora; desligada enquanto o mínimo não for definido).
- Conjunto de treinamento: os elegíveis que estão como "Apto ao treinamento" (RN15, tabela `aptidao_treinamento`).

Os elegíveis fora do conjunto de treinamento fazem o papel dos itens "reservados" do estudo (etapa 2c): ficam fora de
tudo o que o modelo aprende, mas são avaliados no período de teste.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.configuracao import ConfigModelo
from src.ml.dados import Entrada

logger = logging.getLogger(__name__)

CLASSES_EQUIPAMENTO = (2, 4)  # classes de item da Blizzard: 2 = arma, 4 = armadura (RN07)


@dataclass
class Selecao:
    precos: pd.DataFrame  # registros diários dos itens elegíveis, com a coluna `regiao`
    itens: pd.DataFrame   # um registro por série e item da região: critérios, `elegivel` e `integra_treino`
    rn07_ativa: bool
    ultimo_dia: Optional[date] = None  # RN25: último dia encerrado da série da região

    @property
    def elegiveis(self) -> pd.DataFrame:
        return self.itens[self.itens["elegivel"]].reset_index(drop=True)

    @property
    def fora_do_treino(self) -> frozenset[tuple[str, int]]:
        """Elegíveis que não integram o conjunto de treinamento."""
        return _chaves(self.itens[self.itens["elegivel"] & ~self.itens["integra_treino"]])

    @property
    def conjunto_de_treinamento(self) -> frozenset[tuple[str, int]]:
        return _chaves(self.itens[self.itens["integra_treino"]])


def _chaves(itens: pd.DataFrame) -> frozenset[tuple[str, int]]:
    return frozenset(zip(itens["serie"].astype(str).tolist(), itens["item_id"].astype(int).tolist()))


def precos_da_regiao(entrada: Entrada, regiao: str) -> pd.DataFrame:
    """Registros das séries da região (RN11). Série sem região conhecida fica de fora."""
    precos = entrada.precos.assign(regiao=entrada.precos["serie"].map(entrada.regiao_da_serie))
    sem_regiao = precos["regiao"].isna()
    if sem_regiao.any():
        logger.warning("CU11: séries sem região conhecida ignoradas: %s",
                       sorted(precos.loc[sem_regiao, "serie"].unique()))
    return precos[precos["regiao"] == regiao].reset_index(drop=True)


def criterios_dos_itens(entrada: Entrada, precos: pd.DataFrame, cfg: ConfigModelo) -> pd.DataFrame:
    """CU11-C1 passo 2 (RN02, RN27, RN07 e RN15), por série e item da região."""
    out = precos.groupby(["serie", "item_id"], as_index=False, observed=True)["data"].agg(
        primeiro_registro="min", ultimo_registro="max", dias_com_registro="count")
    if out.empty:
        for coluna in ("quantidade_media_recente", "dias_de_historico", "liquido_rn02", "historico_rn27",
                       "equipamento_obsoleto_rn07", "elegivel", "apto_rn15", "integra_treino"):
            out[coluna] = pd.Series(dtype="float64" if coluna in ("quantidade_media_recente", "dias_de_historico")
                                    else "bool")
        return out
    fim = precos["data"].max()

    # RN02: quantidade média ofertada nos últimos 7 dias da base.
    recentes = precos[precos["data"] > fim - pd.Timedelta(days=cfg.liquidez_dias)]
    media = recentes.groupby(["serie", "item_id"], observed=True)["quantidade"].mean()
    chaves = pd.MultiIndex.from_arrays([out["serie"], out["item_id"]])
    out["quantidade_media_recente"] = media.reindex(chaves).to_numpy()
    out["liquido_rn02"] = (out["quantidade_media_recente"] > cfg.liquidez_min_quantidade).to_numpy()

    # RN27: dias de histórico diário, do primeiro registro do item até a data mais recente da base.
    out["dias_de_historico"] = (fim - out["primeiro_registro"]).dt.days + 1
    out["historico_rn27"] = out["dias_de_historico"] >= cfg.historico_minimo_dias

    # RN07: equipamento (arma ou armadura) com nível de item abaixo do mínimo da temporada vigente.
    if cfg.ilvl_minimo is not None and len(entrada.itens):
        atributos = entrada.itens.set_index("item_id")
        classe = out["item_id"].map(atributos["classe_id"])
        nivel = out["item_id"].map(atributos["nivel_item"])
        out["equipamento_obsoleto_rn07"] = (classe.isin(CLASSES_EQUIPAMENTO) & (nivel < cfg.ilvl_minimo)).to_numpy()
    else:
        out["equipamento_obsoleto_rn07"] = np.zeros(len(out), dtype=bool)

    out["elegivel"] = out["liquido_rn02"] & out["historico_rn27"] & ~out["equipamento_obsoleto_rn07"]
    out["apto_rn15"] = out["item_id"].isin(entrada.aptos)
    out["integra_treino"] = out["elegivel"] & out["apto_rn15"]
    return out


def selecionar(entrada: Entrada, cfg: ConfigModelo, regiao: str) -> Selecao:
    """CU11-C1 passo 2: itens elegíveis à projeção e, entre eles, o conjunto de treinamento."""
    precos = precos_da_regiao(entrada, regiao)
    itens = criterios_dos_itens(entrada, precos, cfg)
    elegiveis = itens.loc[itens["elegivel"], ["serie", "item_id"]]
    precos = precos.merge(elegiveis, on=["serie", "item_id"])
    logger.info("CU11-C1 passo 2: %d séries na região %s; RN02: %d líquidas; RN27: %d com %d dias ou mais; "
                "RN07: %s; elegíveis: %d; conjunto de treinamento (RN15): %d.",
                len(itens), regiao, int(itens["liquido_rn02"].sum()), int(itens["historico_rn27"].sum()),
                cfg.historico_minimo_dias,
                "desligada" if cfg.ilvl_minimo is None else f"{int(itens['equipamento_obsoleto_rn07'].sum())} obsoletos",
                len(elegiveis), int(itens["integra_treino"].sum()))
    ultimo = precos["data"].max() if len(precos) else None
    return Selecao(precos=precos, itens=itens, rn07_ativa=cfg.ilvl_minimo is not None,
                   ultimo_dia=None if ultimo is None or pd.isna(ultimo) else pd.Timestamp(ultimo).date())
