"""CU11: tensores da LSTM e assinatura da normalização (porte de `estudos/lstm/dataset.py`).

As janelas não são materializadas (com milhões de amostras, [amostras, 30, 16] ocuparia dezenas de GB). Cada amostra
guarda só id_linha_origem; a janela de entrada são as linhas id_linha_origem − 29 ... id_linha_origem, contíguas porque
as linhas estão na ordem (série, data) e id_linha é a posição da linha.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from src.ml.configuracao import PERIODOS

if TYPE_CHECKING:
    from src.ml.preparacao import BasePreparada


def assinatura_normalizacao(normalizacao: dict[str, Any]) -> str:
    """RN24/RN25: identifica a normalização de uma versão do modelo (datas de corte, constantes, vocabulário, nível de
    item, alvo e variáveis). Duas bases com a mesma assinatura alimentam o mesmo modelo exatamente da mesma forma, mesmo
    com itens diferentes (é o que permite prever itens fora do treino com o modelo já treinado)."""
    cfg = normalizacao["config"]
    conteudo = {
        "cortes": {k: normalizacao["cortes"][k] for k in ("corte_validacao", "corte_teste")},
        "constantes": normalizacao["constantes"],
        "vocabulario": normalizacao["vocabulario"],
        "nivel_item": normalizacao["nivel_item"],
        "alvo": normalizacao["alvo"],
        "variaveis": normalizacao["variaveis"],
        "formato": {"janela": cfg["janela"], "horizonte": cfg["horizonte"]},
    }
    _chave_da_subclasse(conteudo, cfg)
    return hashlib.sha256(json.dumps(conteudo, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _chave_da_subclasse(conteudo: dict[str, Any], cfg: dict[str, Any]) -> None:
    """Variáveis 6 e 15 pelo par (classe, subclasse): entra na assinatura só quando ligada, para que as versões
    treinadas com o código da subclasse sozinho (sem o campo) mantenham a assinatura que gravaram."""
    if cfg.get("subclasse_por_classe"):
        conteudo["subclasse_por_classe"] = True


def assinatura_das_constantes(normalizacao: dict[str, Any]) -> str:
    """CU11-C2 (RN26): a assinatura sem as datas de corte. O modelo vigente é avaliado no período de teste novo com as
    constantes, o vocabulário, a faixa de nível, a escala do alvo e as variáveis dele; só os cortes mudam."""
    cfg = normalizacao["config"]
    conteudo = {
        "constantes": normalizacao["constantes"],
        "vocabulario": normalizacao["vocabulario"],
        "nivel_item": normalizacao["nivel_item"],
        "alvo": normalizacao["alvo"],
        "variaveis": normalizacao["variaveis"],
        "formato": {"janela": cfg["janela"], "horizonte": cfg["horizonte"]},
    }
    _chave_da_subclasse(conteudo, cfg)
    return hashlib.sha256(json.dumps(conteudo, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def conferir_compatibilidade(norm_modelo: dict[str, Any], norm_base: dict[str, Any]) -> None:
    """A base precisa ter sido normalizada exatamente como a versão do modelo (porte de `prever.py`)."""
    a, b = assinatura_normalizacao(norm_modelo), assinatura_normalizacao(norm_base)
    if a != b:
        raise ValueError(f"normalização incompatível (modelo {a}, base {b}): prepare a base com a normalização da "
                         "versão do modelo")


class DadosPreparados:
    """A base preparada em memória, no formato que a rede e a avaliação usam."""

    def __init__(self, base: "BasePreparada") -> None:
        self.normalizacao: dict[str, Any] = base.normalizacao
        cfg = self.normalizacao["config"]
        self.janela: int = int(cfg["janela"])
        self.horizonte: int = int(cfg["horizonte"])
        var = self.normalizacao["variaveis"]
        self.var_seq: list[str] = var["sequencia"]
        self.var_est: list[str] = var["estaticas"]
        self.var_cat: list[str] = var["categoricas"]

        ln = base.normalizadas
        if not np.array_equal(ln["id_linha"].to_numpy(), np.arange(len(ln))):
            raise ValueError("linhas normalizadas fora de ordem: id_linha deve ser igual à posição da linha")
        self.seq = ln[self.var_seq].to_numpy(dtype=np.float32)
        self.est = ln[self.var_est].to_numpy(dtype=np.float32)
        self.cat = ln[self.var_cat].to_numpy(dtype=np.int32)
        self.originais: pd.DataFrame = base.originais
        self._janelas = {p: base.janelas[base.janelas["periodo"] == p].reset_index(drop=True) for p in PERIODOS}

    def janelas(self, periodo: str) -> pd.DataFrame:
        if periodo not in PERIODOS:
            raise ValueError(f"período deve ser um de {PERIODOS}")
        return self._janelas[periodo]

    def colunas_alvo(self) -> list[str]:
        return [f"y_{h}" for h in range(1, self.horizonte + 1)]

    def tensores(self, jan: pd.DataFrame) -> dict[str, np.ndarray]:
        """X_seq [n, 30, 16], X_est [n, 4], X_cat [n, 2], y [n, 7] (normalizado) e id_amostra [n], que acompanha as
        previsões até a avaliação."""
        origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
        idx = origem[:, None] + np.arange(-self.janela + 1, 1)[None, :]
        return {
            "id_amostra": jan["id_amostra"].to_numpy(dtype=np.int64),
            "X_seq": self.seq[idx],
            "X_est": self.est[origem],
            "X_cat": self.cat[origem],
            "y": jan[self.colunas_alvo()].to_numpy(dtype=np.float32),
        }
