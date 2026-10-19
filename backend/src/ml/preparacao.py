"""CU11-C1 passos 4 a 7: RN03, variáveis de entrada, normalização e separação dos períodos (porte de
`estudos/lstm/preparar_dados.py`, com a configuração final do estudo).

Ordem das etapas
    1. Calendário diário de cada série dos itens elegíveis.
    2. RN03: descarte de outliers pela EMA de 14 dias dos preços anteriores já aceitos (passo 4).
    3. Preenchimento de até 3 dias sem registro com o último valor, marcando a linha como não observada (RN24).
    4. Variáveis de entrada brutas, sempre calculadas item a item (passo 5).
    5. Datas de corte 70/20/10 no calendário, iguais para todos os itens (RN25, passo 7).
    6. Constantes de normalização calculadas SOMENTE com o período de treinamento do conjunto de treinamento (RN24,
       RN25) e aplicadas a todos os itens elegíveis (passo 6).
    7. Amostras (janelas) de treino, validação e teste.

Mecanismo de identificação
    id_linha   liga `originais` a `normalizadas` (mesma linha = mesmo id_linha). É também a posição da linha nos dois
               quadros, que ficam na mesma ordem (série, data).
    id_amostra identifica cada janela de entrada. A amostra guarda id_linha_origem (o último dia de entrada, "hoje");
               o alvo h (1 a 7) é sempre a linha id_linha_origem + h, da mesma série.
    normalizacao guarda as datas de corte e todas as constantes, para desfazer a normalização na avaliação e prever
               com a mesma versão do modelo (artefato normalizacao.json).

Itens fora do conjunto de treinamento (`fora_do_treino`) ficam de fora das constantes, do vocabulário, da escala do
alvo, do treino e da parada antecipada; são previstos e avaliados como os demais (etapa 2c do estudo). Com
`normalizacao_base`, a normalização de outra versão do modelo é aplicada sem recalcular nada.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.ml.configuracao import PERIODOS, VARIAVEIS_CATEGORICAS, VARIAVEIS_ESTATICAS, VARIAVEIS_SEQUENCIA, ConfigModelo
from src.ml.dados import Entrada
from src.ml.dataset import assinatura_das_constantes, assinatura_normalizacao

logger = logging.getLogger(__name__)

EPS = 1e-12
TIPOS_PATCH = ("PATCH", "EXPANSAO")
PADRAO_PRE_PATCH = re.compile(r"pr[ée][\s-]?patch", re.IGNORECASE)
PADRAO_VERSAO = re.compile(r"(\d+)\.")
VERSAO_FORMATO = 1


@dataclass
class BasePreparada:
    originais: pd.DataFrame     # linha a linha, antes da normalização (preço em Cobre, RN01)
    normalizadas: pd.DataFrame  # mesmas linhas, com as variáveis de entrada normalizadas
    janelas: pd.DataFrame       # uma amostra por série e dia "hoje", com o período e os 7 alvos normalizados
    normalizacao: dict[str, Any]
    itens: pd.DataFrame         # um registro por série: fora_do_treino e amostras por período


# ======================================================================================================= 1. calendário
def montar_calendario(precos: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por série e por dia, do primeiro ao último registro; dias sem registro ficam com preço nulo."""
    lim = precos.groupby(["serie", "item_id", "regiao"], as_index=False, observed=True)["data"].agg(inicio="min",
                                                                                                    fim="max")
    n = ((lim["fim"] - lim["inicio"]).dt.days + 1).to_numpy()
    grade = lim.loc[lim.index.repeat(n), ["serie", "item_id", "regiao", "inicio"]].reset_index(drop=True)
    grade["data"] = grade["inicio"] + pd.to_timedelta(grade.groupby(["serie", "item_id"]).cumcount(), unit="D")
    grade = grade.drop(columns="inicio")
    linhas = grade.merge(precos[["serie", "item_id", "data", "preco", "quantidade"]], on=["serie", "item_id", "data"],
                         how="left")
    linhas = linhas.rename(columns={"preco": "preco_bruto", "quantidade": "quantidade_bruta"})
    linhas = linhas.sort_values(["serie", "item_id", "data"], kind="mergesort").reset_index(drop=True)
    linhas["serie_idx"] = linhas.groupby(["serie", "item_id"], sort=False).ngroup().astype("int32")
    linhas["serie"] = linhas["serie"].astype("category")
    linhas["regiao"] = linhas["regiao"].astype("category")
    linhas.insert(0, "id_linha", np.arange(len(linhas), dtype="int64"))
    return linhas


# ============================================================================================== utilitários por série
def _rolling_por_serie(s: pd.Series, chave: pd.Series, janela: int, minimo: int, func: str) -> pd.Series:
    r = getattr(s.groupby(chave, sort=False).rolling(janela, min_periods=minimo), func)()
    return r.droplevel(0).reindex(s.index)


def rolling_zscore(s: pd.Series, chave: pd.Series, cfg: ConfigModelo) -> pd.Series:
    """RN24: padronização pela média e pelo desvio dos últimos 90 dias do próprio item (inclui o dia atual, nunca o
    futuro), limitada a ±3 e dividida por 3."""
    media = _rolling_por_serie(s, chave, cfg.zscore_janela, cfg.zscore_min_periodos, "mean")
    desvio = _rolling_por_serie(s, chave, cfg.zscore_janela, cfg.zscore_min_periodos, "std")
    z = np.where(desvio > 1e-9, (s - media) / desvio.where(desvio > 1e-9, 1.0), 0.0)
    z = pd.Series(z, index=s.index).where(media.notna())
    return z.clip(-cfg.zscore_limite, cfg.zscore_limite) / cfg.zscore_limite


def percentil_treino(s: pd.Series, treino: pd.Series, cfg: ConfigModelo, simetrico: bool) -> float:
    """RN24/RN25: constante global = percentil 99 do treino (do módulo, se simétrica). Só enxerga o treino."""
    v = s[treino & s.notna()].to_numpy(dtype="float64")
    if simetrico:
        v = np.abs(v)
    if v.size == 0:
        return 1.0
    return float(max(np.percentile(v, cfg.percentil_constante), EPS))


def escalar(s: pd.Series, c: float, simetrico: bool) -> pd.Series:
    return (s / c).clip(-1.0 if simetrico else 0.0, 1.0)


def limitar_dias(dias: np.ndarray, limite: int) -> np.ndarray:
    return np.minimum(np.asarray(dias, dtype="float64"), limite) / limite


# ============================================================================================ 2 e 3. RN03 e preenchimento
def rn03_por_serie(preco: np.ndarray, inicio_de_serie: np.ndarray,
                   cfg: ConfigModelo) -> tuple[np.ndarray, np.ndarray]:
    """CU11-C1 passo 4 / RN03: EMA de 14 dias calculada só com os preços anteriores **já aceitos**, para que o preço
    absurdo não inflacione a média que deveria barrá-lo. Devolve a EMA anterior a cada dia e se o dia foi descartado.

    - Preço fora da faixa (> EMA·4 ou < EMA·0,1) é descartado.
    - `rn03_confirmacao` (7) preços seguidos fora da faixa, do mesmo lado, são uma mudança real de patamar. O novo
      patamar é a mediana da sequência: os preços da sequência dentro da faixa dessa mediana são aceitos, os demais
      (um pico no meio da mudança) continuam descartados, e a EMA recomeça nos aceitos.
    - Salto absurdo: se a mediana da sequência estiver a `rn03_salto_absurdo` (1.000×) ou mais do patamar confirmado,
      para cima ou para baixo, a confirmação exige `rn03_confirmacao_absurdo` (28) preços seguidos.
    - O primeiro preço de cada série não tem com o que ser comparado e é aceito. O patamar inicial só fica confirmado
      com `rn03_confirmacao` preços aceitos; se outro patamar for confirmado antes disso, os preços do inicial são
      descartados (o placeholder de um item novo).

    A decisão sobre um dia usa registros posteriores só para confirmar um patamar; a EMA usa só os anteriores. Dias
    sem registro (NaN) não contam; preço ≤ 0 nunca é aceito.
    """
    n = len(preco)
    ema_anterior = np.full(n, np.nan)
    descartado = np.zeros(n, dtype=bool)
    alfa = 2.0 / (cfg.ema_span + 1)
    sup, inf = 1.0 + cfg.rn03_acima, 1.0 - cfg.rn03_abaixo
    k = max(int(cfg.rn03_confirmacao), 2)
    k_absurdo = max(int(cfg.rn03_confirmacao_absurdo), k)
    salto = float(cfg.rn03_salto_absurdo)
    ema = np.nan
    patamar: list[int] = []    # preços aceitos do patamar atual
    confirmado = False         # o patamar atual já tem k preços aceitos (ou nasceu de uma confirmação)
    sequencia: list[int] = []  # preços seguidos fora da faixa, todos do mesmo lado
    lado_da_sequencia = 0
    for i in range(n):
        if inicio_de_serie[i]:
            ema, patamar, confirmado, sequencia, lado_da_sequencia = np.nan, [], False, [], 0
        ema_anterior[i] = ema
        p = preco[i]
        if p != p:  # dia sem registro
            continue
        if p <= 0:
            descartado[i] = True
            continue
        if ema != ema:  # primeiro preço da série
            ema, patamar = p, [i]
            continue
        lado = 1 if p > ema * sup else (-1 if p < ema * inf else 0)
        if lado == 0:
            ema = alfa * p + (1.0 - alfa) * ema
            patamar.append(i)
            confirmado = confirmado or len(patamar) >= k
            sequencia, lado_da_sequencia = [], 0
            continue
        if lado != lado_da_sequencia:
            sequencia, lado_da_sequencia = [], lado
        sequencia.append(i)
        descartado[i] = True
        if len(sequencia) < k:
            continue
        centro = float(np.median(preco[sequencia]))
        if confirmado and not 1.0 / salto < centro / ema < salto and len(sequencia) < k_absurdo:
            continue  # salto absurdo: ainda não confirmado
        # Novo patamar confirmado: os preços da sequência próximos da mediana.
        aceitos = [j for j in sequencia if inf * centro <= preco[j] <= sup * centro]
        descartado[aceitos] = False
        if not confirmado:
            descartado[patamar] = True  # o patamar inicial nunca chegou a ser confirmado
        ema = preco[aceitos[0]]
        for j in aceitos[1:]:
            ema = alfa * preco[j] + (1.0 - alfa) * ema
        patamar, confirmado, sequencia, lado_da_sequencia = aceitos, True, [], 0
    return ema_anterior, descartado


def higienizar(linhas: pd.DataFrame, cfg: ConfigModelo) -> pd.DataFrame:
    """CU11-C1 passo 4 (RN03) e preenchimento de até 3 dias com o último valor (RN24)."""
    chave = linhas["serie_idx"]
    sid = linhas["serie_idx"].to_numpy()
    inicio = np.r_[True, sid[1:] != sid[:-1]] if len(sid) else np.zeros(0, dtype=bool)
    ema_anterior, descartado = rn03_por_serie(linhas["preco_bruto"].to_numpy(dtype="float64"), inicio, cfg)
    linhas["ema14_anterior"] = ema_anterior
    linhas["descartado_rn03"] = descartado

    preco_valido = linhas["preco_bruto"].where(~linhas["descartado_rn03"] & (linhas["preco_bruto"] > 0))
    linhas["observado"] = preco_valido.notna()
    linhas["preco"] = preco_valido.groupby(chave, sort=False).ffill(limit=cfg.preenchimento_max_dias)
    linhas["preenchido"] = linhas["preco"].notna() & ~linhas["observado"]
    linhas["quantidade"] = linhas["quantidade_bruta"].groupby(chave, sort=False).ffill(limit=cfg.preenchimento_max_dias)
    return linhas


# ===================================================================================================== 4. variáveis
def _versao_maior(versao: Any) -> Optional[int]:
    m = PADRAO_VERSAO.match(str(versao or "").strip())
    return int(m.group(1)) if m else None


def datas_de_patch_e_marcos(eventos: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """RN17: datas dos patches e expansões (variáveis 10 e 11) e dos marcos de expansão (variável 12), ordenadas.

    - Versão repetida: a mesma versão de patch com mais de uma data conta só na primeira (as seguintes são atualizações
      de conteúdo da mesma versão, nos inícios de temporada, que a variável 13 já cobre).
    - Pré-patch: o primeiro patch de cada versão maior (4.0.1, 5.0.4, ..., 12.0.0) é o pré-patch da expansão seguinte.
      O nome nem sempre diz isso; o nome continua valendo também.
    """
    ev = eventos[eventos["tipo"].isin(TIPOS_PATCH)].sort_values("data_inicio", kind="mergesort")
    vistas: set[str] = set()
    maior_ate_agora: Optional[int] = None
    patches: list[np.datetime64] = []
    marcos: list[np.datetime64] = []
    for tipo, nome, versao, data in zip(ev["tipo"], ev["nome"].fillna("").astype(str), ev["versao"], ev["data_inicio"]):
        dia = np.datetime64(pd.Timestamp(data).date(), "D")
        if tipo == "EXPANSAO":
            patches.append(dia)
            marcos.append(dia)
            continue
        chave = str(versao).strip() if isinstance(versao, str) and versao.strip() else None
        if chave is not None:
            if chave in vistas:
                continue
            vistas.add(chave)
        patches.append(dia)
        maior = _versao_maior(chave)
        nova_versao_maior = maior is not None and maior_ate_agora is not None and maior > maior_ate_agora
        if maior is not None:
            maior_ate_agora = maior if maior_ate_agora is None else max(maior_ate_agora, maior)
        if nova_versao_maior or PADRAO_PRE_PATCH.search(nome):
            marcos.append(dia)
    vazio = np.array([], dtype="datetime64[D]")
    return (np.unique(np.array(patches, dtype="datetime64[D]")) if patches else vazio,
            np.unique(np.array(marcos, dtype="datetime64[D]")) if marcos else vazio)


def variaveis_de_calendario(datas: pd.DatetimeIndex, eventos: pd.DataFrame, cfg: ConfigModelo) -> pd.DataFrame:
    """CU11-C1 passo 5: variáveis 9 a 14 (calendário e eventos, conhecidas antecipadamente). RN25: um patch só é
    considerado conhecido a partir de `antecedencia_anuncio_dias` antes da data, pois evento_jogo não guarda a data do
    anúncio. Variável 14 agregada: algum evento sazonal ativo no dia."""
    d = datas.values.astype("datetime64[D]")
    um_dia = np.timedelta64(1, "D")
    a = cfg.antecedencia_anuncio_dias
    lim = cfg.limite_dias
    out = pd.DataFrame(index=datas)
    dow = datas.dayofweek.to_numpy()
    out["f_dia_sin"] = np.sin(2 * np.pi * dow / 7)
    out["f_dia_cos"] = np.cos(2 * np.pi * dow / 7)

    ini = eventos["data_inicio"].values.astype("datetime64[D]")
    fim = eventos["data_fim"].values.astype("datetime64[D]")
    tipo = eventos["tipo"].to_numpy()

    patches, marcos = datas_de_patch_e_marcos(eventos)
    pos = np.searchsorted(patches, d, side="right") - 1
    desde = np.where(pos >= 0, (d - patches[np.clip(pos, 0, None)]) / um_dia if patches.size else np.inf, np.inf)
    out["f_dias_desde_patch"] = limitar_dias(desde, lim)

    prox = np.searchsorted(patches, d, side="right")
    ate = np.where(prox < patches.size,
                   (patches[np.clip(prox, 0, max(patches.size - 1, 0))] - d) / um_dia if patches.size else np.inf,
                   np.inf)
    out["f_dias_ate_patch"] = np.where(ate <= a, ate / a, 1.0)

    p = np.searchsorted(marcos, d, side="left")
    out["f_expansao"] = ((p < marcos.size) & (marcos[np.clip(p, 0, max(marcos.size - 1, 0))] <= d + a * um_dia)
                         if marcos.size else np.zeros(len(d), dtype=bool)).astype("float64")

    temp = eventos[eventos["tipo"] == "TEMPORADA"].sort_values("data_inicio")
    t_ini = temp["data_inicio"].values.astype("datetime64[D]")
    t_fim = temp["data_fim"].values.astype("datetime64[D]")
    prox_ini = np.append(t_ini[1:] - um_dia, np.datetime64("NaT", "D"))
    t_fim = np.where(np.isnat(t_fim), prox_ini, t_fim)  # sem data de fim: vai até a véspera da próxima temporada
    q = np.searchsorted(t_ini, d, side="right") - 1
    if t_ini.size:
        qi = np.clip(q, 0, None)
        ativa = (q >= 0) & (np.isnat(t_fim[qi]) | (d <= np.where(np.isnat(t_fim[qi]), d, t_fim[qi])))
        dias = np.where(ativa, (d - t_ini[qi]) / um_dia, 0)
    else:
        ativa, dias = np.zeros(len(d), dtype=bool), np.zeros(len(d))
    out["f_temporada_ativa"] = ativa.astype("float64")
    out["f_dias_temporada"] = np.where(ativa, limitar_dias(dias, lim), 0.0)

    sazonal = tipo == "EVENTO_SAZONAL"
    s_ini, s_fim = ini[sazonal], np.where(np.isnat(fim[sazonal]), ini[sazonal], fim[sazonal])
    ativo = np.zeros(len(d), dtype=bool)
    for i0, f0 in zip(s_ini, s_fim):
        ativo |= (d >= i0) & (d <= f0)
    out["f_evento"] = ativo.astype("float64")
    return out


def calcular_variaveis_brutas(linhas: pd.DataFrame, entrada: Entrada, cfg: ConfigModelo) -> pd.DataFrame:
    """CU11-C1 passo 5: variáveis antes das constantes globais. Tudo que usa shift/rolling/EMA é feito por série
    (groupby). A variável 6 usa todos os itens elegíveis do dia, não só o conjunto de treinamento."""
    chave = linhas["serie_idx"]
    linhas["log_preco"] = np.log(linhas["preco"])
    linhas["log_return"] = linhas["log_preco"] - linhas["log_preco"].groupby(chave, sort=False).shift(1)
    linhas["f_nivel_preco"] = rolling_zscore(linhas["log_preco"], chave, cfg).astype("float32")
    linhas["f_quantidade"] = rolling_zscore(np.log1p(linhas["quantidade"].clip(lower=0)), chave, cfg).astype("float32")
    linhas["log_preco_ema14"] = (linhas["log_preco"] - np.log(linhas["ema14_anterior"])).astype("float32")
    linhas["volatilidade_7d"] = _rolling_por_serie(linhas["log_return"], chave, cfg.volatilidade_janela,
                                                   cfg.volatilidade_min_periodos, "std").astype("float32")

    itens = entrada.itens.set_index("item_id")
    for col in ("classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc", "commodity"):
        linhas[col] = linhas["item_id"].map(itens[col]) if len(itens) else np.nan
    commod_ids = {str(v) for v in cfg.commodities_por_regiao.values()}
    informado = linhas["commodity"].notna().to_numpy()
    linhas["commodity"] = np.where(informado, linhas["commodity"].to_numpy() == True,  # noqa: E712
                                   linhas["serie"].isin(commod_ids).to_numpy())

    # Variável 6: média dos log-retornos da subclasse no dia, ponderada pela quantidade, sem o próprio item.
    m = linhas["observado"] & linhas["log_return"].notna() & linhas["subclasse_id"].notna() & (linhas["quantidade"] > 0)
    w = linhas["quantidade"].where(m, 0.0)
    rw = (linhas["log_return"] * w).where(m, 0.0)
    grupo = [linhas["regiao"], linhas["subclasse_id"], linhas["data"]]
    soma_rw = rw.groupby(grupo, observed=True).transform("sum")
    soma_w = w.groupby(grupo, observed=True).transform("sum")
    resto = soma_w - w
    linhas["retorno_subclasse"] = ((soma_rw - rw) / resto.where(resto > 0)).astype("float32")
    del m, w, rw, soma_rw, soma_w, resto

    tem_piso = linhas["preco_npc"].fillna(0) > 0
    linhas["f_tem_piso"] = tem_piso.astype("float32")
    linhas["log_preco_npc"] = (linhas["log_preco"] - np.log(linhas["preco_npc"].where(tem_piso))).where(tem_piso)
    linhas["log_return"] = linhas["log_return"].astype("float32")

    # Variáveis 9 a 14: calculadas uma vez por região e dia e copiadas para as linhas (sem merge, que duplicaria o quadro).
    regioes = linhas["regiao"].astype(str).to_numpy()
    for regiao in np.unique(regioes):
        pos = np.flatnonzero(regioes == regiao)
        ev = entrada.eventos[entrada.eventos["regiao"].isin(["GLOBAL", regiao])]
        datas = linhas["data"].to_numpy()[pos]
        cal = variaveis_de_calendario(pd.DatetimeIndex(np.unique(datas)), ev, cfg)
        valores = cal.reindex(pd.DatetimeIndex(datas)).to_numpy(dtype="float32")
        for k, col in enumerate(cal.columns):
            if col not in linhas:
                linhas[col] = np.full(len(linhas), np.nan, dtype="float32")
            linhas.iloc[pos, linhas.columns.get_loc(col)] = valores[:, k]
    return linhas


# ================================================================================================ 5. datas de corte
def calcular_cortes(linhas: pd.DataFrame, cfg: ConfigModelo, corte_validacao: Optional[str] = None,
                    corte_teste: Optional[str] = None) -> dict[str, pd.Timestamp]:
    """CU11-C1 passo 7 / RN25: divisão cronológica 70/20/10 sobre o calendário, igual para todos os itens (HYNDMAN;
    ATHANASOPOULOS, 2018, seção 3.4)."""
    inicio, fim = linhas["data"].min(), linhas["data"].max()
    dias = (fim - inicio).days + 1
    cv = pd.Timestamp(corte_validacao) if corte_validacao else \
        inicio + pd.Timedelta(days=round(dias * cfg.proporcao_treino))
    ct = pd.Timestamp(corte_teste) if corte_teste else \
        inicio + pd.Timedelta(days=round(dias * (cfg.proporcao_treino + cfg.proporcao_validacao)))
    if not inicio < cv < ct <= fim:
        raise ValueError(f"Datas de corte inválidas: início {inicio.date()}, validação {cv.date()}, "
                         f"teste {ct.date()}, fim {fim.date()}")
    return {"inicio": inicio, "corte_validacao": cv, "corte_teste": ct, "fim": fim}


def periodo_da_data(datas: pd.Series, cortes: dict[str, pd.Timestamp]) -> pd.Series:
    rotulo = np.where(datas < cortes["corte_validacao"], PERIODOS[0],
                      np.where(datas < cortes["corte_teste"], PERIODOS[1], PERIODOS[2]))
    return pd.Series(rotulo, index=datas.index)


# ======================================================================================== 6. normalização (só treino)
CONSTANTES_GLOBAIS: tuple[tuple[str, str, bool], ...] = (  # (variável bruta, variável final, simétrica)
    ("log_return", "f_log_return", True),
    ("log_preco_ema14", "f_preco_ema14", True),
    ("volatilidade_7d", "f_volatilidade_7d", False),
    ("retorno_subclasse", "f_retorno_subclasse", True),
    ("log_preco_npc", "f_preco_npc", True),
)


def ajustar(linhas: pd.DataFrame, treino: pd.Series, cfg: ConfigModelo) -> dict[str, Any]:
    """RN24 + RN25: constantes globais, faixa do nível de item e vocabulário das categorias, só com as linhas de
    `treino` (o período de treinamento do conjunto de treinamento)."""
    const = {final: percentil_treino(linhas[bruto], treino, cfg, simetrico)
             for bruto, final, simetrico in CONSTANTES_GLOBAIS}
    niveis = linhas.loc[treino, ["item_id", "nivel_item"]].drop_duplicates("item_id")["nivel_item"].dropna()
    nmin, nmax = (float(niveis.min()), float(niveis.max())) if len(niveis) else (0.0, 1.0)
    vocab: dict[str, dict[str, int]] = {}
    for col in ("classe_id", "subclasse_id"):
        valores = sorted(int(v) for v in linhas.loc[treino, col].dropna().unique())
        vocab[col] = {str(v): i + 1 for i, v in enumerate(valores)}  # 0 = desconhecida
    return {"constantes": const, "nivel_item": {"min": nmin, "max": nmax}, "vocabulario": vocab}


VARIAVEIS_JA_FINAIS = ("f_nivel_preco", "f_quantidade", "f_tem_piso", "f_dia_sin", "f_dia_cos", "f_dias_desde_patch",
                       "f_dias_ate_patch", "f_expansao", "f_temporada_ativa", "f_dias_temporada", "f_evento")


def aplicar(linhas: pd.DataFrame, ajuste: dict[str, Any], cfg: ConfigModelo,
            variaveis: Optional[list[str]] = None) -> pd.DataFrame:
    """CU11-C1 passo 6 / RN24: aplica a normalização (desta versão ou de outra versão do modelo) às linhas e devolve as
    variáveis normalizadas, sem alterar as brutas (o CU11-C2 aplica duas normalizações às mesmas variáveis brutas).
    Categoria fora do vocabulário, como a de um item de uma subclasse nunca vista no treino, vira 0 (desconhecida)."""
    norm = pd.DataFrame(index=linhas.index)
    const = ajuste["constantes"]
    for bruto, final, simetrico in CONSTANTES_GLOBAIS:
        norm[final] = escalar(linhas[bruto], const[final], simetrico).astype("float32")
    # Sem pares na subclasse no dia, ou item sem preço de venda ao vendedor: 0.
    norm["f_retorno_subclasse"] = norm["f_retorno_subclasse"].fillna(0.0)
    norm["f_preco_npc"] = norm["f_preco_npc"].fillna(0.0)
    norm["f_observado"] = linhas["observado"].astype("float32")

    qualidade = linhas["qualidade"].clip(0, cfg.qualidade_max) / cfg.qualidade_max
    norm["f_qualidade"] = qualidade.fillna(0.0).astype("float32")
    nmin, nmax = ajuste["nivel_item"]["min"], ajuste["nivel_item"]["max"]
    nivel = ((linhas["nivel_item"] - nmin) / max(nmax - nmin, EPS)).clip(0, 1)
    norm["f_nivel_item"] = nivel.fillna(0.0).astype("float32")
    norm["f_commodity"] = linhas["commodity"].astype("float32")
    for col in VARIAVEIS_JA_FINAIS:  # já normalizadas no cálculo (z-score móvel, calendário, indicadores)
        norm[col] = linhas[col]

    for col, idx_col in (("classe_id", "classe_idx"), ("subclasse_id", "subclasse_idx")):
        mapa = {float(v): i for v, i in ajuste["vocabulario"][col].items()}
        norm[idx_col] = linhas[col].map(mapa).fillna(0).astype("int32")
    if variaveis is not None:
        faltando = [v for v in variaveis if v not in norm]
        if faltando:
            raise ValueError(f"variáveis da versão do modelo que esta base não calcula: {faltando}")
        norm = norm[variaveis + VARIAVEIS_CATEGORICAS]
    return norm


# ============================================================================================== 7. janelas e separação
def montar_janelas(linhas: pd.DataFrame, apta: np.ndarray, cortes: dict[str, pd.Timestamp],
                   cfg: ConfigModelo) -> pd.DataFrame:
    """Uma amostra para cada dia "hoje" (id_linha_origem) com 30 dias de entrada válidos e 7 dias de alvo com preço.
    O período da amostra é o dos seus alvos; amostras cujos alvos atravessam uma data de corte são descartadas (RN25),
    para que nenhum alvo de treino caia na validação (e nenhum da validação, no teste)."""
    J, H = cfg.janela, cfg.horizonte
    n = len(linhas)
    colunas = ["id_amostra", "id_linha_origem", "serie", "item_id", "data_origem", "periodo", "preco_base",
               "dias_de_historico", "fora_do_treino"] + [f"{p}_{h}" for h in range(1, H + 1) for p in ("y", "obs")]
    if n < J + H:
        return pd.DataFrame(columns=colunas)
    alvo_ok = linhas["preco"].notna().to_numpy()
    sid = linhas["serie_idx"].to_numpy()
    c_apta = np.concatenate([[0], np.cumsum(apta)])
    c_alvo = np.concatenate([[0], np.cumsum(alvo_ok)])
    i = np.arange(J - 1, n - H)
    ok = ((c_apta[i + 1] - c_apta[i + 1 - J]) == J) & (sid[i - J + 1] == sid[i]) & (sid[i + H] == sid[i]) & \
         ((c_alvo[i + H + 1] - c_alvo[i + 1]) == H)
    o = i[ok]

    datas = linhas["data"].to_numpy()
    d_ini, d_fim = datas[o + 1], datas[o + H]
    cv, ct = np.datetime64(cortes["corte_validacao"]), np.datetime64(cortes["corte_teste"])
    periodo = np.full(o.size, "", dtype=object)
    periodo[d_fim < cv] = PERIODOS[0]
    periodo[(d_ini >= cv) & (d_fim < ct)] = PERIODOS[1]
    periodo[d_ini >= ct] = PERIODOS[2]
    manter = periodo != ""
    logger.info("Amostras descartadas por terem alvos dos dois lados de uma data de corte: %d", int((~manter).sum()))
    o, periodo = o[manter], periodo[manter]

    lp = linhas["log_preco"].to_numpy()
    obs = linhas["observado"].to_numpy()
    # Idade do item no dia da previsão: dias desde o primeiro registro da série (o calendário começa nele).
    primeiro = linhas.groupby("serie_idx", sort=False)["data"].transform("min").to_numpy()
    jan = pd.DataFrame({
        "id_amostra": np.arange(o.size, dtype="int64"),
        "id_linha_origem": o.astype("int64"),
        "serie": linhas["serie"].to_numpy()[o],
        "item_id": linhas["item_id"].to_numpy()[o],
        "data_origem": datas[o],
        "periodo": periodo,
        "preco_base": linhas["preco"].to_numpy()[o].round().astype("int64"),  # último preço conhecido "hoje" (Cobre)
        "dias_de_historico": ((datas[o] - primeiro[o]) / np.timedelta64(1, "D")).astype("int32") + 1,
        "fora_do_treino": linhas["fora_do_treino"].to_numpy()[o],
    })
    for h in range(1, H + 1):
        jan[f"y_{h}"] = lp[o + h] - lp[o]          # log-retorno de hoje até o dia h (ainda sem normalizar)
        jan[f"obs_{h}"] = obs[o + h]               # o alvo do dia h foi observado (e não preenchido)?
    return jan


def normalizar_alvo(jan: pd.DataFrame, cfg: ConfigModelo,
                    alvo: Optional[dict[str, list[float]]] = None) -> dict[str, list[float]]:
    """RN24: a saída do modelo é padronizada pela média e pelo desvio de cada dia do horizonte, calculados nas
    amostras de treino do conjunto de treinamento. Com `alvo` (normalização de outra versão do modelo), só aplica."""
    cols = [f"y_{h}" for h in range(1, cfg.horizonte + 1)]
    if alvo is None:
        treino = (jan["periodo"] == PERIODOS[0]) & ~jan["fora_do_treino"].astype(bool)
        if not treino.any():
            raise SemAmostrasDeTreino("Nenhuma amostra de treino: histórico curto demais para a janela, o horizonte e "
                                      "o corte.")
        media = jan.loc[treino, cols].mean().to_numpy(dtype="float64")
        desvio = jan.loc[treino, cols].std(ddof=0).to_numpy(dtype="float64")
        desvio = np.where(desvio > EPS, desvio, 1.0)
    else:
        media = np.asarray(alvo["media"], dtype="float64")
        desvio = np.asarray(alvo["desvio"], dtype="float64")
    if len(jan):
        jan[cols] = ((jan[cols].to_numpy(dtype="float64") - media) / desvio).astype("float32")
    return {"media": media.tolist(), "desvio": desvio.tolist()}


class SemAmostrasDeTreino(ValueError):
    """Nenhum item do conjunto de treinamento tem amostra no período de treinamento (CU11-C1-FA1 depois do FA3)."""


# ======================================================================================================= orquestração
@dataclass
class VariaveisBrutas:
    """CU11-C1 passos 4, 5 e 7 antes da normalização: calendário, RN03, variáveis brutas, datas de corte e períodos.
    O CU11-C2 aplica a elas a normalização do modelo novo e a do vigente, sem ler nem higienizar a base duas vezes."""
    linhas: pd.DataFrame
    cortes: dict[str, pd.Timestamp]
    cfg: ConfigModelo
    series: pd.DataFrame  # serie_idx, serie, item_id
    fora: np.ndarray      # por série (na ordem de `series`): fora do conjunto de treinamento
    cobertura: dict[str, float]
    itens_commodity: int


# Parâmetros que definem as variáveis brutas e as janelas: duas configurações que concordam neles podem dividir as
# mesmas variáveis brutas (as constantes, o vocabulário e a escala do alvo vêm depois, de cada versão).
PARAMETROS_DAS_BRUTAS = ("janela", "horizonte", "zscore_janela", "zscore_min_periodos", "zscore_limite", "limite_dias",
                         "preenchimento_max_dias", "volatilidade_janela", "volatilidade_min_periodos", "qualidade_max",
                         "ema_span", "rn03_acima", "rn03_abaixo", "rn03_confirmacao", "rn03_salto_absurdo",
                         "rn03_confirmacao_absurdo", "antecedencia_anuncio_dias", "commodities_por_regiao")


def mesmas_brutas(a: ConfigModelo, b: ConfigModelo) -> bool:
    return all(getattr(a, p) == getattr(b, p) for p in PARAMETROS_DAS_BRUTAS)


def preparar_brutas(entrada: Entrada, precos: pd.DataFrame, cfg: ConfigModelo,
                    fora_do_treino: frozenset[tuple[str, int]] = frozenset(), corte_validacao: Optional[str] = None,
                    corte_teste: Optional[str] = None) -> VariaveisBrutas:
    """CU11-C1 passos 4, 5 e 7 para os itens de `precos` (os elegíveis à projeção, com a coluna `regiao`): RN03,
    variáveis brutas item a item e divisão 70/20/10 do calendário (ou as datas de corte informadas)."""
    if precos.empty:
        raise ValueError("Nenhuma série para preparar.")
    linhas = montar_calendario(precos)
    logger.info("CU11: %d séries, %d linhas (série × dia).", linhas["serie_idx"].nunique(), len(linhas))
    series = linhas.drop_duplicates("serie_idx")[["serie_idx", "serie", "item_id"]].reset_index(drop=True)
    fora = np.array([(str(s), int(i)) in fora_do_treino for s, i in zip(series["serie"], series["item_id"])],
                    dtype=bool)
    linhas["fora_do_treino"] = fora[linhas["serie_idx"].to_numpy()]

    linhas = higienizar(linhas, cfg)
    linhas = calcular_variaveis_brutas(linhas, entrada, cfg)
    cortes = calcular_cortes(linhas, cfg, corte_validacao, corte_teste)
    linhas["periodo"] = periodo_da_data(linhas["data"], cortes).astype("category")
    unicos = linhas.drop_duplicates("item_id")
    cobertura = {c: float(unicos[c].notna().mean())
                 for c in ("classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc")}
    itens_commodity = int(unicos["commodity"].sum())
    return VariaveisBrutas(linhas, cortes, cfg, series, fora, cobertura, itens_commodity)


def normalizar(brutas: VariaveisBrutas, versao_de_origem: Optional[dict[str, Any]] = None,
               somente_teste: bool = False) -> BasePreparada:
    """CU11-C1 passo 6 e a montagem das amostras. Sem `versao_de_origem`, as constantes, o vocabulário, a faixa do nível
    de item e a escala do alvo são calculados só com o treino do conjunto de treinamento (RN24, RN25). Com ela (o
    normalizacao.json de outra versão), são os dela. `somente_teste` guarda só as amostras do período de teste (a
    avaliação do modelo vigente no CU11-C2)."""
    linhas, cfg, cortes = brutas.linhas, brutas.cfg, brutas.cortes
    if versao_de_origem is None:
        treino = (linhas["periodo"] == PERIODOS[0]) & ~linhas["fora_do_treino"]
        ajuste = ajustar(linhas, treino, cfg)
        variaveis_seq = list(VARIAVEIS_SEQUENCIA)
        alvo_da_origem = None
    else:
        ajuste = {k: versao_de_origem[k] for k in ("constantes", "nivel_item", "vocabulario")}
        variaveis_seq = list(versao_de_origem["variaveis"]["sequencia"])
        alvo_da_origem = versao_de_origem["alvo"]
    variaveis = variaveis_seq + VARIAVEIS_ESTATICAS
    norm = aplicar(linhas, ajuste, cfg, variaveis)

    apta = (linhas["preco"].notna() & np.isfinite(norm[variaveis].to_numpy(dtype="float32")).all(axis=1)).to_numpy()
    jan = montar_janelas(linhas, apta, cortes, cfg)
    if somente_teste and len(jan):
        jan = jan[jan["periodo"] == PERIODOS[2]].reset_index(drop=True)
    alvo = normalizar_alvo(jan, cfg, alvo_da_origem)

    originais = linhas[["id_linha", "serie", "item_id", "regiao", "data", "periodo", "preco_bruto", "quantidade_bruta",
                        "descartado_rn03", "observado", "preenchido", "preco", "quantidade"]].copy()
    originais["preco_bruto"] = originais["preco_bruto"].round().astype("Int64")
    originais["preco"] = originais["preco"].round().astype("Int64")
    originais = originais.rename(columns={"preco": "preco_cobre"})

    normalizadas = linhas[["id_linha", "serie", "item_id", "data", "periodo"]].copy()
    normalizadas["apta"] = apta
    for col in variaveis:
        normalizadas[col] = norm[col].astype("float32")
    for col in VARIAVEIS_CATEGORICAS:
        normalizadas[col] = norm[col]
    del norm

    itens = brutas.series[["serie", "item_id"]].astype({"serie": str}).reset_index(drop=True)
    itens["fora_do_treino"] = brutas.fora
    por_periodo = (jan.groupby([jan["serie"].astype(str), "item_id", "periodo"]).size().unstack(fill_value=0)
                   if len(jan) else pd.DataFrame())
    itens = itens.merge(por_periodo.reset_index(), on=["serie", "item_id"], how="left") if len(por_periodo) else itens
    for p in PERIODOS:
        itens[f"amostras_{p}"] = itens.pop(p).fillna(0).astype("int64") if p in itens else 0

    regioes = sorted(set(linhas["regiao"].astype(str).unique()))
    contagens: dict[str, Any] = {
        "series": int(len(brutas.series)),
        "series_fora_do_treino": int(brutas.fora.sum()),
        "linhas": int(len(linhas)),
        "linhas_aptas": int(apta.sum()),
        "descartadas_rn03": int(linhas["descartado_rn03"].sum()),
        "preenchidas": int(linhas["preenchido"].sum()),
        "amostras": {p: int((jan["periodo"] == p).sum()) if len(jan) else 0 for p in PERIODOS},
        "amostras_fora_do_treino": {p: int((jan["fora_do_treino"] & (jan["periodo"] == p)).sum()) if len(jan) else 0
                                    for p in PERIODOS},
        "cobertura_atributos": brutas.cobertura,
        "itens_commodity": brutas.itens_commodity,
    }
    normalizacao: dict[str, Any] = {
        "versao_formato": VERSAO_FORMATO,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regiao": regioes[0] if len(regioes) == 1 else regioes,
        "config": cfg.como_dict(),
        "cortes": {k: v.date().isoformat() for k, v in cortes.items()},
        **ajuste,
        "alvo": alvo,
        "variaveis": {"sequencia": variaveis_seq, "estaticas": VARIAVEIS_ESTATICAS,
                      "categoricas": VARIAVEIS_CATEGORICAS},
        "contagens": contagens,
    }
    if versao_de_origem is not None:
        normalizacao["normalizacao_de"] = {"assinatura": assinatura_normalizacao(versao_de_origem),
                                           "assinatura_das_constantes": assinatura_das_constantes(versao_de_origem)}
    normalizacao["assinatura"] = assinatura_normalizacao(normalizacao)
    return BasePreparada(originais, normalizadas, jan, normalizacao, itens)


def preparar(entrada: Entrada, precos: pd.DataFrame, cfg: ConfigModelo,
             fora_do_treino: frozenset[tuple[str, int]] = frozenset(),
             normalizacao_base: Optional[dict[str, Any]] = None, corte_validacao: Optional[str] = None,
             corte_teste: Optional[str] = None) -> BasePreparada:
    """CU11-C1 passos 4 a 7 para os itens de `precos` (os elegíveis à projeção, com a coluna `regiao`).

    `fora_do_treino`: séries (serie, item_id) dos elegíveis que não integram o conjunto de treinamento; ficam fora das
    constantes, do vocabulário e da escala do alvo (RN24, RN25). `normalizacao_base`: aplica a normalização de outra
    versão do modelo inteira, inclusive as datas de corte e a configuração (o caminho da previsão de um item qualquer com
    uma versão já treinada); a assinatura tem de ser a mesma."""
    if normalizacao_base is not None:
        cfg = ConfigModelo.de_dict(normalizacao_base["config"])
        corte_validacao = normalizacao_base["cortes"]["corte_validacao"]
        corte_teste = normalizacao_base["cortes"]["corte_teste"]
    brutas = preparar_brutas(entrada, precos, cfg, fora_do_treino, corte_validacao, corte_teste)
    base = normalizar(brutas, normalizacao_base)
    if normalizacao_base is not None and base.normalizacao["assinatura"] != assinatura_normalizacao(normalizacao_base):
        raise AssertionError("a normalização aplicada difere da versão do modelo de origem")
    return base


def aplicar_versao(brutas: VariaveisBrutas, normalizacao_da_versao: dict[str, Any]) -> BasePreparada:
    """CU11-C2 passo 6 / RN26: o modelo vigente é avaliado no período de teste novo com as **próprias** constantes,
    vocabulário, faixa de nível e escala do alvo (o normalizacao.json da versão dele), aplicados às variáveis brutas e
    às datas de corte novas. Por isso a conferência é só a das constantes (`assinatura_das_constantes`), sem os cortes.
    Só as amostras do período de teste são guardadas."""
    if not mesmas_brutas(brutas.cfg, ConfigModelo.de_dict(normalizacao_da_versao["config"])):
        raise ValueError("as variáveis brutas desta base não correspondem à configuração da versão do modelo")
    base = normalizar(brutas, normalizacao_da_versao, somente_teste=True)
    if assinatura_das_constantes(base.normalizacao) != assinatura_das_constantes(normalizacao_da_versao):
        raise AssertionError("as constantes aplicadas diferem das da versão do modelo")
    return base
