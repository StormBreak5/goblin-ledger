"""CU11-C1 passos 9 e 10: avaliação no período de teste e RN10 (porte de `estudos/lstm/avaliar.py`).

Caminho de uma previsão até o erro
    yhat normalizado (saída da Dense(7))
      → log-retorno: r = yhat · desvio_h + media_h            (normalizacao["alvo"], RN24)
      → preço:       p̂ = preco_base · exp(r), arredondado     (Cobre, RN01)
      → real:        originais[id_linha_origem + h]            (só dias observados; preenchidos e RN03 ficam de fora)

O modelo ingênuo repete o último preço conhecido (preco_base).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.ml.dataset import DadosPreparados
from src.models.modelo import (MOTIVO_ACIMA_DO_LIMIAR, MOTIVO_AVALIACAO_INSUFICIENTE, MOTIVO_NAO_SUPERA_INGENUO,
                               SITUACAO_BLOQUEADA, SITUACAO_LIBERADA)


@dataclass
class Avaliacao:
    detalhe: pd.DataFrame   # uma linha por amostra e por dia do horizonte
    por_item: pd.DataFrame  # métricas, situação e motivo de cada série avaliada
    resumo: dict[str, Any]


def desnormalizar(yhat: np.ndarray, normalizacao: dict[str, Any]) -> np.ndarray:
    """RN24: desfaz a padronização do alvo (média e desvio de cada dia do horizonte, do treino)."""
    media = np.asarray(normalizacao["alvo"]["media"], dtype=np.float64)
    desvio = np.asarray(normalizacao["alvo"]["desvio"], dtype=np.float64)
    return np.asarray(yhat, dtype=np.float64) * desvio + media


def para_cobre(preco_base: np.ndarray, log_retorno: np.ndarray) -> np.ndarray:
    """RN01: preço previsto em Cobre = preço de hoje × exp(log-retorno previsto)."""
    return np.rint(preco_base[:, None].astype(np.float64) * np.exp(log_retorno)).astype(np.int64)


def classificar_rn10(por_item: pd.DataFrame, metrica: str, limiar: float, minimo_dias: int) -> pd.DataFrame:
    """CU11-C1 passo 10 / RN10: projeção liberada se a métrica do item (MdAPE) ficar no limiar e abaixo da do modelo
    ingênuo, com ao menos `minimo_dias` dias de previsões avaliadas. FA4: acima do limiar ou não supera o ingênuo;
    FA5: avaliação insuficiente (o motivo que vale primeiro)."""
    supera = por_item[metrica] < por_item[f"{metrica}_ingenuo"]
    no_limiar = por_item[metrica] <= limiar
    suficiente = por_item["dias_avaliados"] >= minimo_dias
    por_item["supera_ingenuo"] = supera
    por_item["situacao"] = np.where(no_limiar & supera & suficiente, SITUACAO_LIBERADA, SITUACAO_BLOQUEADA)
    motivo = np.select([~suficiente, ~no_limiar, ~supera],
                       [MOTIVO_AVALIACAO_INSUFICIENTE, MOTIVO_ACIMA_DO_LIMIAR, MOTIVO_NAO_SUPERA_INGENUO], default="")
    por_item["motivo"] = pd.Series(motivo, index=por_item.index).replace("", None)
    return por_item


def avaliar(dados: DadosPreparados, periodo: str, id_amostra: np.ndarray, yhat: np.ndarray,
            limiar: Optional[float] = None, metrica: Optional[str] = None,
            minimo_dias: Optional[int] = None) -> Avaliacao:
    """CU11-C1 passo 9: erro das predições e do modelo ingênuo de cada item no `periodo`, só sobre os dias com preço
    observado. Passo 10: situação de cada item pela RN10."""
    H = dados.horizonte
    cfg = dados.normalizacao["config"]
    limiar = float(limiar if limiar is not None else cfg["limiar_rn10"])
    metrica = metrica or cfg["metrica_rn10"]
    minimo_dias = int(minimo_dias if minimo_dias is not None else cfg["minimo_dias_rn10"])
    if metrica not in ("mdape", "mape"):
        raise ValueError("metrica deve ser 'mdape' ou 'mape'")
    id_amostra = np.asarray(id_amostra, dtype=np.int64)
    jan = dados.janelas(periodo).set_index("id_amostra")
    faltando = np.setdiff1d(id_amostra, jan.index.to_numpy())
    if faltando.size:
        raise KeyError(f"{faltando.size} id_amostra não pertencem às janelas de {periodo} (ex.: {faltando[:5].tolist()})")
    jan = jan.loc[id_amostra]

    base = jan["preco_base"].to_numpy(dtype=np.int64)
    previsto = para_cobre(base, desnormalizar(yhat, dados.normalizacao)) if len(jan) else np.zeros((0, H), np.int64)
    origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
    alvo = origem[:, None] + np.arange(1, H + 1)[None, :]

    orig = dados.originais
    serie_o = orig["serie"].to_numpy()
    if len(jan) and not (serie_o[alvo] == serie_o[origem][:, None]).all():
        raise AssertionError("alvo fora da série da amostra: a ordem das linhas foi alterada")
    real = orig["preco_cobre"].to_numpy(dtype="float64", na_value=np.nan)[alvo]
    avaliavel = orig["observado"].to_numpy()[alvo] & np.isfinite(real)

    det = pd.DataFrame({
        "id_amostra": np.repeat(id_amostra, H),
        "id_linha_origem": np.repeat(origem, H),
        "serie": np.repeat(jan["serie"].astype(str).to_numpy(), H),
        "item_id": np.repeat(jan["item_id"].to_numpy(), H),
        "data_origem": np.repeat(jan["data_origem"].to_numpy(), H),
        "h": np.tile(np.arange(1, H + 1), len(id_amostra)),
        "data_alvo": orig["data"].to_numpy()[alvo].ravel(),
        "preco_base": np.repeat(base, H),
        "preco_real": real.ravel(),
        "preco_previsto": previsto.ravel(),
        "avaliavel": avaliavel.ravel(),
    })
    det["erro_abs"] = (det["preco_previsto"] - det["preco_real"]).abs()
    det["erro_pct"] = det["erro_abs"] / det["preco_real"]
    det["erro_abs_ingenuo"] = (det["preco_base"] - det["preco_real"]).abs()
    det["erro_pct_ingenuo"] = det["erro_abs_ingenuo"] / det["preco_real"]
    det.loc[~det["avaliavel"], ["erro_abs", "erro_pct", "erro_abs_ingenuo", "erro_pct_ingenuo"]] = np.nan

    ok = det[det["avaliavel"]]
    por_item = ok.groupby(["serie", "item_id"]).agg(
        alvos_avaliados=("erro_pct", "size"),
        dias_avaliados=("data_origem", "nunique"),
        mape=("erro_pct", "mean"),
        mape_ingenuo=("erro_pct_ingenuo", "mean"),
        mdape=("erro_pct", "median"),
        mdape_ingenuo=("erro_pct_ingenuo", "median"),
        mae_cobre=("erro_abs", "mean"),
        mae_ingenuo_cobre=("erro_abs_ingenuo", "mean"),
        rmse_cobre=("erro_abs", lambda e: float(np.sqrt((e ** 2).mean()))),
        rmse_ingenuo_cobre=("erro_abs_ingenuo", lambda e: float(np.sqrt((e ** 2).mean()))),
    ).reset_index()
    # Erro relativo ao ingênuo (MAE do modelo ÷ MAE do ingênuo nos mesmos dias): < 1 = melhor que o ingênuo. É livre de
    # escala, como o erro escalado de Hyndman e Athanasopoulos (2018, seção 3.4).
    por_item["erro_relativo_ingenuo"] = por_item["mae_cobre"] / por_item["mae_ingenuo_cobre"].where(
        por_item["mae_ingenuo_cobre"] > 0)
    por_item = classificar_rn10(por_item, metrica, limiar, minimo_dias)

    def mediana(coluna: str) -> Optional[float]:
        return float(por_item[coluna].median()) if len(por_item) else None

    resumo: dict[str, Any] = {
        "periodo": periodo,
        "amostras": int(len(id_amostra)),
        "alvos_avaliados": int(len(ok)),
        "alvos_ignorados_nao_observados": int((~det["avaliavel"]).sum()),
        "itens": int(len(por_item)),
        "rn10": {"metrica": metrica, "limiar": limiar, "minimo_dias": minimo_dias},
        "itens_liberados_rn10": int((por_item["situacao"] == SITUACAO_LIBERADA).sum()),
        "itens_com_avaliacao_insuficiente": int((por_item["motivo"] == MOTIVO_AVALIACAO_INSUFICIENTE).sum()),
        "itens_que_superam_ingenuo": int(por_item["supera_ingenuo"].sum()),
        "itens_que_superam_ingenuo_no_mape": int((por_item["mape"] < por_item["mape_ingenuo"]).sum()),
        "mediana_mdape_por_item": mediana("mdape"),
        "mediana_mdape_ingenuo_por_item": mediana("mdape_ingenuo"),
        "mediana_mape_por_item": mediana("mape"),
        "mediana_mape_ingenuo_por_item": mediana("mape_ingenuo"),
        "mediana_rmse_cobre_por_item": mediana("rmse_cobre"),
        "mediana_rmse_ingenuo_cobre_por_item": mediana("rmse_ingenuo_cobre"),
        "mediana_erro_relativo_ingenuo": mediana("erro_relativo_ingenuo"),
    }
    return Avaliacao(det, por_item, resumo)


@dataclass
class Comparacao:
    """CU11-C2 passos 6 e 7 (RN26): o modelo novo e o vigente no mesmo período de teste, nos mesmos itens e dias."""
    metrica: str
    itens_comparados: int
    mediana_novo: Optional[float]
    mediana_vigente: Optional[float]
    por_item: pd.DataFrame

    @property
    def novo_e_melhor(self) -> bool:
        """RN26: o novo substitui o vigente só se a mediana for estritamente menor."""
        return self.mediana_novo is not None and self.mediana_vigente is not None and             self.mediana_novo < self.mediana_vigente

    def como_dict(self) -> dict[str, Any]:
        return {"metrica": self.metrica, "itens_comparados": self.itens_comparados,
                "mediana_novo": self.mediana_novo, "mediana_vigente": self.mediana_vigente,
                "novo_e_melhor": self.novo_e_melhor}


def comparar_modelos(novo: Avaliacao, vigente: Avaliacao, metrica: str = "mdape") -> Comparacao:
    """CU11-C2 passos 6 e 7 / RN26: a métrica da RN10 por item (MdAPE por padrão), calculada só nos alvos avaliados
    pelos dois modelos (mesmo item, mesmo dia de origem, mesmo dia do horizonte), e a mediana dela entre os itens."""
    chaves = ["serie", "item_id", "data_origem", "h"]
    a = novo.detalhe.loc[novo.detalhe["avaliavel"], chaves + ["erro_pct"]]
    b = vigente.detalhe.loc[vigente.detalhe["avaliavel"], chaves + ["erro_pct"]]
    comuns = a.merge(b, on=chaves, suffixes=("_novo", "_vigente"))
    funcao = "median" if metrica == "mdape" else "mean"
    por_item = comuns.groupby(["serie", "item_id"]).agg(
        alvos=("erro_pct_novo", "size"), novo=("erro_pct_novo", funcao), vigente=("erro_pct_vigente", funcao),
    ).reset_index()
    vazio = por_item.empty
    return Comparacao(
        metrica=metrica, itens_comparados=int(len(por_item)),
        mediana_novo=None if vazio else float(por_item["novo"].median()),
        mediana_vigente=None if vazio else float(por_item["vigente"].median()),
        por_item=por_item,
    )
