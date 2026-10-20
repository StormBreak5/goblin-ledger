"""CU11-C3 passo 7: as predições dos próximos 7 dias de cada item com projeção liberada, com o modelo vigente.

- RN25: só os dados até o dia de referência D; e só o trecho de histórico necessário (MODELO_PREVISAO_HISTORICO_DIAS,
  200 dias: a janela de 30, a padronização de 90 e o aquecimento da EMA e do patamar da RN03), não a base inteira.
- As variáveis são calculadas como no treinamento, com a normalização da versão vigente (o normalizacao.json dela). A
  variável 6 (índice da subclasse) usa todos os itens elegíveis do dia, não só os liberados.
- RN01: preço previsto em Cobre = preço de D × exp(log-retorno previsto), a mesma conversão da avaliação.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from src.ml.artefatos import ARQUIVO_MODELO, ARQUIVO_NORMALIZACAO
from src.ml.avaliacao import desnormalizar, para_cobre
from src.ml.configuracao import ConfigModelo
from src.ml.dados import carregar_banco
from src.ml.dataset import DadosPreparados
from src.ml.preparacao import BasePreparada, aplicar_versao, preparar_brutas
from src.ml.rede import Treinador
from src.ml.selecao import precos_da_regiao, selecionar

logger = logging.getLogger(__name__)


@dataclass
class VersaoParaPrever:
    versao: int
    caminho: Path
    normalizacao: dict[str, Any]

    @classmethod
    def da_pasta(cls, versao: int, caminho: str) -> "VersaoParaPrever":
        pasta = Path(caminho)
        return cls(versao, pasta, json.loads((pasta / ARQUIVO_NORMALIZACAO).read_text(encoding="utf-8")))


@dataclass
class PrevisoesDoDia:
    linhas: list[dict[str, Any]]  # prontas para predicao_diaria
    itens_previstos: int
    itens_sem_janela: int  # liberados sem os 30 dias de entrada válidos que terminam em D


def janelas_de_previsao(base: BasePreparada, dia: date, itens: set[tuple[str, int]]) -> pd.DataFrame:
    """A janela de entrada que termina no dia de referência (30 dias aptos da mesma série) de cada item, com o preço de
    D (o último preço conhecido, em Cobre) como base. Sem alvos: o futuro ainda não aconteceu."""
    n, o = base.normalizadas, base.originais
    J = int(base.normalizacao["config"]["janela"])
    H = int(base.normalizacao["config"]["horizonte"])
    apta = n["apta"].to_numpy()
    acumulado = np.concatenate([[0], np.cumsum(apta)])
    serie = n["serie"].astype(str).to_numpy()
    item = n["item_id"].to_numpy()
    pos = np.flatnonzero(n["data"].to_numpy() == np.datetime64(pd.Timestamp(dia)))
    pos = pos[pos >= J - 1]
    preco = o["preco_cobre"].to_numpy(dtype="float64", na_value=np.nan)[pos]
    ok = ((acumulado[pos + 1] - acumulado[pos + 1 - J]) == J) & (serie[pos - J + 1] == serie[pos]) & \
         (item[pos - J + 1] == item[pos]) & np.isfinite(preco) & (preco > 0)
    ok &= np.array([(s, int(i)) in itens for s, i in zip(serie[pos], item[pos])], dtype=bool)
    pos, preco = pos[ok], preco[ok]
    jan = pd.DataFrame({
        "id_amostra": np.arange(pos.size, dtype="int64"),
        "id_linha_origem": pos.astype("int64"),
        "serie": serie[pos],
        "item_id": item[pos].astype("int64"),
        "data_origem": np.datetime64(pd.Timestamp(dia)),
        "preco_base": np.rint(preco).astype("int64"),
    })
    for h in range(1, H + 1):
        jan[f"y_{h}"] = np.float32(0.0)  # sem alvo: só para o formato dos tensores
    return jan


def prever_dia(engine: Engine, cfg: ConfigModelo, regiao: str, vigente: VersaoParaPrever,
               liberados: set[tuple[str, int]], dia: date, treinador: Treinador, agora: Any) -> PrevisoesDoDia:
    """CU11-C3 passo 7: as predições de D+1 a D+7 dos itens liberados, a partir da janela que termina em D."""
    if not liberados:
        return PrevisoesDoDia([], 0, 0)
    cfg_da_versao = ConfigModelo.de_dict(vigente.normalizacao["config"])
    desde = dia - timedelta(days=cfg.previsao_historico_dias - 1)
    with engine.connect() as conexao:
        entrada = carregar_banco(conexao, cfg_da_versao, ate=dia + timedelta(days=1), desde=desde)
    selecao = selecionar(entrada, cfg, regiao)  # os elegíveis do dia (variável 6)
    itens = set(zip(selecao.elegiveis["serie"].astype(str), selecao.elegiveis["item_id"].astype(int))) | liberados
    precos = precos_da_regiao(entrada, regiao)
    chaves = pd.DataFrame(sorted(itens), columns=["serie", "item_id"]).astype({"item_id": "int64"})
    precos = precos.merge(chaves, on=["serie", "item_id"])
    if precos.empty:
        return PrevisoesDoDia([], 0, len(liberados))
    brutas = preparar_brutas(entrada, precos, cfg_da_versao, frozenset())
    base = aplicar_versao(brutas, vigente.normalizacao)
    del entrada, brutas, precos
    jan = janelas_de_previsao(base, dia, liberados)
    if jan.empty:
        return PrevisoesDoDia([], 0, len(liberados))
    dados = DadosPreparados(base)
    ids, yhat = treinador.prever(treinador.carregar(vigente.caminho / ARQUIVO_MODELO), dados, jan)
    jan = jan.set_index("id_amostra").loc[ids]
    previsto = para_cobre(jan["preco_base"].to_numpy(dtype=np.int64), desnormalizar(yhat, base.normalizacao))
    linhas = [
        {"data_previsao": dia, "serie": str(s), "item_id": int(i), "versao": vigente.versao, "h": h,
         "data_prevista": dia + timedelta(days=h), "preco_previsto": int(previsto[k, h - 1]), "criado_em": agora}
        for k, (s, i) in enumerate(zip(jan["serie"], jan["item_id"]))
        for h in range(1, previsto.shape[1] + 1)
    ]
    logger.info("CU11-C3 passo 7: %d itens de %s previstos para %s a %s com a versão %s (%d liberados sem janela).",
                len(jan), regiao, dia + timedelta(days=1), dia + timedelta(days=previsto.shape[1]), vigente.versao,
                len(liberados) - len(jan))
    return PrevisoesDoDia(linhas, int(len(jan)), int(len(liberados) - len(jan)))
