"""Estudo preliminar do modelo LSTM global (CU11): aplica a normalização e depois separa os dados.

Ordem das etapas
    1. Seleção dos itens (RN15 aptidão, RN02 liquidez, RN07 nível de item) e calendário diário de cada série.
    2. RN03: descarte de outliers pela EMA de 14 dias calculada só com os dias anteriores.
    3. Preenchimento de até 3 dias sem registro com o último valor, marcando a linha como não observada (RN24).
    4. Variáveis de entrada brutas, sempre calculadas item a item (groupby da série).
    5. Datas de corte 70/20/10 no calendário, iguais para todos os itens (RN25).
    6. Constantes de normalização calculadas SOMENTE com o período de treinamento (RN25) e aplicadas a todas as linhas.
    7. Separação: cada linha recebe o seu período e as amostras (janelas) vão para treino, validação ou teste.

Mecanismo de identificação
    id_linha   liga linhas_originais.parquet a linhas_normalizadas.parquet (mesma linha = mesmo id_linha). É também a
               posição da linha nos dois arquivos, que ficam na mesma ordem (série, data).
    id_amostra identifica cada janela de entrada. A amostra guarda id_linha_origem (o último dia de entrada, "hoje");
               o alvo h (1 a 7) é sempre a linha id_linha_origem + h, da mesma série.
    normalizacao.json guarda as datas de corte e todas as constantes, para desfazer a normalização na avaliação.
    itens.parquet  um registro por série e item: atributos, critérios de seleção (RN15, RN02), primeiro registro e
               se o item foi reservado (etapa 2c).

Generalização para itens fora do treino (etapa 2c)
    --reservar-itens 0.2   sorteia 20% dos itens (estratificado pela classe) e os marca como reservados. Eles ficam
                           de fora de tudo o que o modelo aprende: constantes, vocabulário, escala do alvo e treino.
                           Servem para medir o erro em itens que o modelo nunca viu.
    --normalizacao-de P    aplica a normalização já calculada na base P (cortes, constantes, vocabulário, alvo e
                           variáveis), sem recalcular nada. É o caminho da previsão de um item qualquer com um modelo
                           já treinado. Use com --excluir-itens-de P para pegar só itens que não estão em P.

Ciclo de vida do item (etapa 2d, desligadas por padrão)
    --variavel-expansao-item   variável 19: o item é da expansão vigente no dia?
    --variavel-idade-item      variável 20: idade do item (dias desde o primeiro registro, até 180)

Uso
    python preparar_dados.py --banco --regiao US --saida saida/estudo01 [--max-itens 500]
    python preparar_dados.py --csv dados_sinteticos --saida saida/sintetico
    python preparar_dados.py --banco --regiao US --saida saida/fora2c --normalizacao-de saida/treino2c \\
        --excluir-itens-de saida/treino2c --ignorar-aptidao --sem-filtro-liquidez --max-itens 3000
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import (PERIODOS, PREFIXO_FESTIVAL, SUFIXO_PROXIMOS, VARIAVEIS_CATEGORICAS, VARIAVEIS_ESTATICAS,
                    VARIAVEIS_SEQUENCIA, VARIAVEL_EXPANSAO_ITEM, VARIAVEL_FEIRA, VARIAVEL_IDADE_ITEM, Config)
from dataset import assinatura_normalizacao
from io_dados import Entrada, carregar_banco, carregar_csv, url_do_banco

logger = logging.getLogger("preparar_dados")

EPS = 1e-12
TIPOS_PATCH = ("PATCH", "EXPANSAO")
PADRAO_PRE_PATCH = re.compile(r"pr[ée][\s-]?patch", re.IGNORECASE)
PADRAO_VERSAO = re.compile(r"(\d+)\.")
CLASSES_EQUIPAMENTO = (2, 4)  # classes de item da Blizzard: 2 = arma, 4 = armadura (RN07)
VERSAO_FORMATO = 1
FATOR_CLASSE = 1000  # etapa 2i: chave do par = classe × 1000 + subclasse
# Variável 15: (nome no vocabulário, coluna de onde vem o código, coluna do índice).
CATEGORICAS: tuple[tuple[str, str, str], ...] = (("classe_id", "classe_id", "classe_idx"),
                                                 ("subclasse_id", "subclasse_chave", "subclasse_idx"))


@dataclass
class Resultado:
    linhas_originais: pd.DataFrame
    linhas_normalizadas: pd.DataFrame
    janelas: pd.DataFrame
    normalizacao: dict[str, Any]
    itens: Optional[pd.DataFrame] = None


# ================================================================================================ 1. seleção e calendário
def _precos_da_regiao(entrada: Entrada, regiao: Optional[str]) -> pd.DataFrame:
    precos = entrada.precos
    precos = precos.assign(regiao=precos["serie"].map(entrada.regiao_da_serie))
    if regiao:
        sem_regiao = precos["regiao"].isna()
        if sem_regiao.any():
            logger.warning("Séries sem região conhecida ignoradas: %s", sorted(precos.loc[sem_regiao, "serie"].unique()))
        return precos[precos["regiao"] == regiao]
    return precos.assign(regiao=precos["regiao"].fillna("GLOBAL"))


def selecionar_series(entrada: Entrada, cfg: Config, regiao: Optional[str], ignorar_aptidao: bool,
                      filtro_liquidez: bool, ilvl_minimo: Optional[float], max_itens: Optional[int],
                      semente: int, excluir_itens: Optional[set[int]] = None) -> pd.DataFrame:
    """CU11-C1 passo 2: itens aptos (RN15), com liquidez (RN02) e equipamentos relevantes (RN07).
    `excluir_itens` (etapa 2c) tira da seleção os itens de outra base antes do sorteio de --max-itens."""
    precos = _precos_da_regiao(entrada, regiao)

    if excluir_itens:
        antes = precos["item_id"].nunique()
        precos = precos[~precos["item_id"].isin(excluir_itens)]
        logger.info("Excluídos %d itens de outra base: restam %d de %d.", antes - precos["item_id"].nunique(),
                    precos["item_id"].nunique(), antes)

    if entrada.aptos is not None and not ignorar_aptidao:
        antes = precos["item_id"].nunique()
        precos = precos[precos["item_id"].isin(entrada.aptos)]
        logger.info("RN15: %d de %d itens aptos ao treinamento.", precos["item_id"].nunique(), antes)

    if ilvl_minimo is not None:
        it = entrada.itens.set_index("item_id")
        equip = it["classe_id"].isin(CLASSES_EQUIPAMENTO) & (it["nivel_item"] < ilvl_minimo)
        precos = precos[~precos["item_id"].isin(it.index[equip])]

    if filtro_liquidez and not precos.empty:
        fim = precos["data"].max()
        recentes = precos[precos["data"] > fim - pd.Timedelta(days=cfg.liquidez_dias)]
        media = recentes.groupby(["serie", "item_id"])["quantidade"].mean()
        liquidas = media[media > cfg.liquidez_min_quantidade].index
        total = precos.groupby(["serie", "item_id"]).ngroups
        precos = precos.set_index(["serie", "item_id"]).loc[lambda d: d.index.isin(liquidas)].reset_index()
        logger.info("RN02: %d de %d séries com quantidade média > %s nos últimos %d dias.",
                    len(liquidas), total, cfg.liquidez_min_quantidade, cfg.liquidez_dias)

    if max_itens:
        chaves = precos[["serie", "item_id"]].drop_duplicates()
        if len(chaves) > max_itens:
            chaves = chaves.sample(max_itens, random_state=semente)
            precos = precos.merge(chaves, on=["serie", "item_id"])
    return precos


def criterios_dos_itens(entrada: Entrada, cfg: Config, regiao: Optional[str]) -> pd.DataFrame:
    """Por série e item da região: apto pela RN15 (nulo sem a tabela de aptidão) e líquido pela RN02 (quantidade média
    acima do mínimo nos últimos dias da base). Só registra; quem filtra é selecionar_series."""
    precos = _precos_da_regiao(entrada, regiao)
    out = precos.groupby(["serie", "item_id"], as_index=False, observed=True)["data"].agg(
        primeiro_registro="min", ultimo_registro="max", dias_com_registro="count")
    if len(precos):
        fim = precos["data"].max()
        recentes = precos[precos["data"] > fim - pd.Timedelta(days=cfg.liquidez_dias)]
        media = recentes.groupby(["serie", "item_id"], observed=True)["quantidade"].mean()
        liquidas = set(media[media > cfg.liquidez_min_quantidade].index)
    else:
        liquidas = set()
    out["liquido_rn02"] = [(s, i) in liquidas for s, i in zip(out["serie"], out["item_id"])]
    if entrada.aptos is not None:
        out["apto_rn15"] = out["item_id"].isin(entrada.aptos)
    else:
        out["apto_rn15"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    return out


def sortear_reservados(itens: pd.DataFrame, fracao: float, semente: int) -> set[int]:
    """Etapa 2c: sorteia `fracao` dos itens para ficarem fora do treino, estratificado pela classe (classe
    desconhecida é um estrato), para que os reservados tenham a mesma composição dos demais. Reprodutível pela semente."""
    if not 0 < fracao < 1:
        raise ValueError("a fração reservada deve estar entre 0 e 1")
    rng = np.random.default_rng(semente)
    ids = itens[["item_id", "classe_id"]].drop_duplicates("item_id")
    reservados: list[int] = []
    for _, g in ids.groupby(ids["classe_id"].fillna(-1), sort=True):
        n = int(round(len(g) * fracao))
        if n:
            reservados += rng.choice(np.sort(g["item_id"].to_numpy()), size=n, replace=False).tolist()
    return {int(x) for x in reservados}


def montar_calendario(precos: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por série e por dia, do primeiro ao último registro; dias sem registro ficam com preço nulo."""
    lim = precos.groupby(["serie", "item_id", "regiao"], as_index=False)["data"].agg(inicio="min", fim="max")
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
def _ewm_por_serie(s: pd.Series, chave: pd.Series, span: int) -> pd.Series:
    r = s.groupby(chave, sort=False).ewm(span=span, adjust=False, ignore_na=True).mean()
    return r.droplevel(0).reindex(s.index)


def _rolling_por_serie(s: pd.Series, chave: pd.Series, janela: int, minimo: int, func: str) -> pd.Series:
    r = getattr(s.groupby(chave, sort=False).rolling(janela, min_periods=minimo), func)()
    return r.droplevel(0).reindex(s.index)


def rolling_zscore(s: pd.Series, chave: pd.Series, cfg: Config) -> pd.Series:
    """RN24: padronização pela média e pelo desvio dos últimos 90 dias do próprio item (inclui o dia atual, nunca o
    futuro), limitada a ±3 e dividida por 3."""
    media = _rolling_por_serie(s, chave, cfg.zscore_janela, cfg.zscore_min_periodos, "mean")
    desvio = _rolling_por_serie(s, chave, cfg.zscore_janela, cfg.zscore_min_periodos, "std")
    z = np.where(desvio > 1e-9, (s - media) / desvio.where(desvio > 1e-9, 1.0), 0.0)
    z = pd.Series(z, index=s.index).where(media.notna())
    return z.clip(-cfg.zscore_limite, cfg.zscore_limite) / cfg.zscore_limite


def percentil_treino(s: pd.Series, treino: pd.Series, cfg: Config, simetrico: bool) -> float:
    """Constante global = percentil 99 do treino (do módulo, se simétrica). Só enxerga o período de treinamento."""
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
def rn03_por_serie(preco: np.ndarray, inicio_de_serie: np.ndarray, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """RN03 com a EMA de 14 dias calculada só com os preços anteriores **já aceitos**, para que o preço absurdo não
    inflacione a média que deveria barrá-lo. Devolve a EMA anterior a cada dia e se o dia foi descartado.

    - Preço fora da faixa (> EMA·4 ou < EMA·0,1) é descartado.
    - `rn03_confirmacao` (7) preços seguidos fora da faixa, do mesmo lado, são uma mudança real de patamar (sem isso, a
      série ficaria travada depois de uma mudança real). O novo patamar é a mediana da sequência: os preços da
      sequência dentro da faixa dessa mediana são aceitos, os demais (um pico no meio da mudança) continuam
      descartados, e a EMA recomeça nos aceitos.
    - Salto absurdo: se a mediana da sequência estiver a `rn03_salto_absurdo` (1.000×) ou mais do patamar confirmado,
      para cima ou para baixo, a confirmação exige `rn03_confirmacao_absurdo` (28) preços seguidos. Assim o anúncio de
      1 milhão de ouro que fica sozinho por duas semanas não vira patamar, mas uma mudança que dura um mês não trava a
      série.
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
    patamar: list[int] = []   # preços aceitos do patamar atual
    confirmado = False        # o patamar atual já tem k preços aceitos (ou nasceu de uma confirmação)
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


def higienizar(linhas: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """RN03: descarta o preço maior que EMA·(1+3,00) ou menor que EMA·(1−0,90), com a EMA de 14 dias calculada
    somente com os registros anteriores ao dia avaliado (ver `rn03_por_serie`). RN24: preenche até 3 dias com o último
    valor."""
    chave = linhas["serie_idx"]
    if cfg.rn03_ema_so_aceitos:
        inicio = np.r_[True, linhas["serie_idx"].to_numpy()[1:] != linhas["serie_idx"].to_numpy()[:-1]]
        ema_anterior, descartado = rn03_por_serie(linhas["preco_bruto"].to_numpy(dtype="float64"), inicio, cfg)
        linhas["ema14_anterior"] = ema_anterior
        linhas["descartado_rn03"] = descartado
    else:  # EMA de todos os preços do banco (comportamento anterior)
        ema = _ewm_por_serie(linhas["preco_bruto"], chave, cfg.ema_span)
        linhas["ema14_anterior"] = ema.groupby(chave, sort=False).shift(1)
        acima = linhas["preco_bruto"] > linhas["ema14_anterior"] * (1 + cfg.rn03_acima)
        abaixo = linhas["preco_bruto"] < linhas["ema14_anterior"] * (1 - cfg.rn03_abaixo)
        linhas["descartado_rn03"] = (acima | abaixo).fillna(False).astype(bool)

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
    """Datas dos patches e expansões (variáveis 10 e 11) e dos marcos de expansão (variável 12), já ordenadas.

    - Versão repetida: a mesma versão de patch com mais de uma data conta só na primeira. As datas seguintes são
      atualizações de conteúdo da mesma versão (em evento_jogo: 9.2.5 e 10.2.6, nos inícios de temporada, que a
      variável 13 já cobre).
    - Pré-patch: o primeiro patch de cada versão maior (4.0.1, 5.0.4, ..., 10.0.0, 11.0.0, 12.0.0) é o pré-patch da
      expansão seguinte. O nome nem sempre diz isso (só o 12.0.0 traz "pre-patch"); o nome continua valendo também.
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


def _nome_do_festival(nome: Any) -> str:
    """Nome do festival sem a marca "(aproximado)" das datas geradas por regra (Noblegarden, Lunar Festival)."""
    return re.sub(r"\s*\(aproximado\)\s*$", "", str(nome or ""), flags=re.IGNORECASE).strip()


def _slug(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


def festivais_do_calendario(eventos: pd.DataFrame) -> dict[str, str]:
    """Variável 14 detalhada: coluna -> nome de cada festival (EVENTO_SAZONAL) do banco, em ordem alfabética."""
    nomes = sorted({_nome_do_festival(n) for n in eventos.loc[eventos["tipo"] == "EVENTO_SAZONAL", "nome"]} - {""})
    return {PREFIXO_FESTIVAL + _slug(n): n for n in nomes}


def _ativo_e_proximos(d: np.ndarray, inicios: np.ndarray, fins: np.ndarray, horizonte: int) -> tuple[np.ndarray, np.ndarray]:
    """Para cada dia de `d`: o evento está ativo hoje (0/1) e em que fração dos próximos `horizonte` dias estará."""
    um_dia = np.timedelta64(1, "D")
    grade = np.arange(d.min(), d.max() + (horizonte + 1) * um_dia, um_dia)
    ativo = np.zeros(len(grade), dtype=bool)
    for i0, f0 in zip(inicios, fins):
        ativo |= (grade >= i0) & (grade <= f0)
    acum = np.concatenate([[0], np.cumsum(ativo)])
    pos = ((d - grade[0]) / um_dia).astype(int)
    proximos = (acum[pos + horizonte + 1] - acum[pos + 1]) / horizonte
    return ativo[pos].astype("float64"), proximos.astype("float64")


def variaveis_de_calendario(datas: pd.DatetimeIndex, eventos: pd.DataFrame, cfg: Config,
                            festivais: Optional[dict[str, str]] = None) -> pd.DataFrame:
    """Variáveis 9 a 14 (calendário e eventos, conhecidas antecipadamente). RN25: um patch só é considerado
    conhecido a partir de `antecedencia_anuncio_dias` antes da data, pois evento_jogo não guarda a data do anúncio."""
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

    if cfg.eventos_detalhados and len(d):
        # Feira de Negrilua (evento recorrente gerado por regra no CU10-C2): uma semana por mês.
        tem_darkmoon = np.array(["darkmoon" in str(n).lower() for n in eventos["nome"].fillna("")], dtype=bool)
        feira = (tipo == "RECORRENTE") & tem_darkmoon
        f_ini, f_fim = ini[feira], np.where(np.isnat(fim[feira]), ini[feira], fim[feira])
        out[VARIAVEL_FEIRA], out[VARIAVEL_FEIRA + SUFIXO_PROXIMOS] = _ativo_e_proximos(d, f_ini, f_fim, cfg.horizonte)
        # Um par de colunas por festival.
        festivais = festivais_do_calendario(eventos) if festivais is None else festivais
        nome_norm = np.array([_nome_do_festival(n) for n in eventos["nome"]], dtype=object)
        for col, nome in festivais.items():
            m = sazonal & (nome_norm == nome)
            e_ini, e_fim = ini[m], np.where(np.isnat(fim[m]), ini[m], fim[m])
            out[col], out[col + SUFIXO_PROXIMOS] = _ativo_e_proximos(d, e_ini, e_fim, cfg.horizonte)
    return out


# =============================================================================== variáveis 19 e 20: ciclo do item
SEM_EXPANSAO = "anterior aos dados ou desconhecida"


def lancamentos_de_expansao(eventos: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Datas de lançamento das expansões (evento EXPANSAO), em ordem, com o nome de cada uma."""
    ex = eventos[eventos["tipo"] == "EXPANSAO"].dropna(subset=["data_inicio"]).sort_values("data_inicio")
    ex = ex.drop_duplicates("data_inicio")
    return ex["data_inicio"].values.astype("datetime64[D]"), [str(n) for n in ex["nome"]]


def expansao_do_item(primeiro: np.ndarray, lancamentos: np.ndarray, inicio_dados: np.datetime64,
                     tolerancia_dias: int) -> np.ndarray:
    """Índice (em `lancamentos`) da expansão de cada item: a do último lançamento até o primeiro registro do item,
    com `tolerancia_dias` de folga para o acesso antecipado. -1 = desconhecida: o item já existia quando os dados
    começam (não dá para saber de que expansão ele é) ou é anterior a todos os lançamentos registrados."""
    tol = np.timedelta64(tolerancia_dias, "D")
    primeiro = primeiro.astype("datetime64[D]")
    idx = np.searchsorted(lancamentos, primeiro + tol, side="right") - 1
    idx[(primeiro <= np.datetime64(inicio_dados, "D") + tol) | np.isnat(primeiro)] = -1
    return idx


def variaveis_do_ciclo_do_item(datas: np.ndarray, primeiro: np.ndarray, lancamentos: np.ndarray,
                               inicio_dados: np.datetime64, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """Variáveis 19 e 20, por linha (item × dia). Só usam o que se sabe no dia (RN25): o item já tem o seu primeiro
    registro e os lançamentos considerados são os que já aconteceram.
    19: 1 se a expansão do item é a vigente no dia (último lançamento até o dia), senão 0.
    20: idade do item em dias, limitada a `idade_limite_dias` e dividida por ele; 1 para itens que já existiam."""
    d = datas.astype("datetime64[D]")
    exp_item = expansao_do_item(primeiro, lancamentos, inicio_dados, cfg.acesso_antecipado_dias)
    vigente = np.searchsorted(lancamentos, d, side="right") - 1
    f_vig = ((exp_item >= 0) & (exp_item == vigente)).astype("float32")
    lim = cfg.idade_limite_dias
    idade = (d - primeiro.astype("datetime64[D]")) / np.timedelta64(1, "D")
    censurado = primeiro.astype("datetime64[D]") <= np.datetime64(inicio_dados, "D") + np.timedelta64(
        cfg.acesso_antecipado_dias, "D")
    f_idade = np.where(censurado, 1.0, np.clip(idade, 0, lim) / lim).astype("float32")
    return f_vig, f_idade


def chave_da_subclasse(classe: pd.Series, subclasse: pd.Series, cfg: Config) -> pd.Series:
    """Variáveis 6 e 15: o código que identifica a subclasse. Com `subclasse_por_classe` (etapa 2i), é o par
    classe × 1000 + subclasse, porque o código da subclasse só é único dentro da classe; sem a classe, o par fica
    desconhecido. Sem a opção, é o código da subclasse sozinho, como nas bases até a etapa 2h."""
    subclasse = subclasse.astype("float64")
    if not cfg.subclasse_por_classe:
        return subclasse.rename("subclasse_chave")
    if (subclasse >= FATOR_CLASSE).any():
        raise ValueError(f"código de subclasse maior que {FATOR_CLASSE}: a chave do par não seria única")
    return (classe.astype("float64") * FATOR_CLASSE + subclasse).rename("subclasse_chave")


def retorno_da_subclasse(linhas: pd.DataFrame, chave: pd.Series) -> pd.Series:
    """Variável 6: média dos log-retornos da subclasse (`chave_da_subclasse`) no dia, ponderada pela quantidade, sem o
    próprio item. Usa `regiao`, `data`, `observado`, `log_return` e `quantidade`."""
    m = linhas["observado"] & linhas["log_return"].notna() & chave.notna() & (linhas["quantidade"] > 0)
    w = linhas["quantidade"].where(m, 0.0)
    rw = (linhas["log_return"] * w).where(m, 0.0)
    grupo = [linhas["regiao"], chave, linhas["data"]]
    soma_rw = rw.groupby(grupo, observed=True).transform("sum")
    soma_w = w.groupby(grupo, observed=True).transform("sum")
    resto = soma_w - w
    return ((soma_rw - rw) / resto.where(resto > 0)).astype("float32")


def calcular_variaveis_brutas(linhas: pd.DataFrame, entrada: Entrada, cfg: Config,
                              festivais: Optional[dict[str, str]] = None,
                              ciclo: Optional[dict[str, Any]] = None) -> pd.DataFrame:
    """Variáveis antes das constantes globais. Tudo que usa shift/rolling/EMA é feito por série (groupby)."""
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

    linhas["subclasse_chave"] = chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], cfg)
    linhas["retorno_subclasse"] = retorno_da_subclasse(linhas, linhas["subclasse_chave"])

    tem_piso = linhas["preco_npc"].fillna(0) > 0
    linhas["f_tem_piso"] = tem_piso.astype("float32")
    linhas["log_preco_npc"] = (linhas["log_preco"] - np.log(linhas["preco_npc"].where(tem_piso))).where(tem_piso)
    linhas["log_return"] = linhas["log_return"].astype("float32")

    # Variáveis 19 e 20 (etapa 2d), por item e dia.
    if ciclo is not None and (cfg.variavel_expansao_item or cfg.variavel_idade_item):
        primeiro = linhas.groupby("serie_idx", sort=False)["data"].transform("min").to_numpy()
        f_vig, f_idade = variaveis_do_ciclo_do_item(linhas["data"].to_numpy(), primeiro, ciclo["lancamentos"],
                                                    ciclo["inicio_dados"], cfg)
        if cfg.variavel_expansao_item:
            linhas[VARIAVEL_EXPANSAO_ITEM] = f_vig
        if cfg.variavel_idade_item:
            linhas[VARIAVEL_IDADE_ITEM] = f_idade
        del primeiro, f_vig, f_idade

    # Variáveis 9 a 14: calculadas uma vez por região e dia e copiadas para as linhas (sem merge, que duplicaria o quadro).
    regioes = linhas["regiao"].astype(str).to_numpy()
    for regiao in np.unique(regioes):
        pos = np.flatnonzero(regioes == regiao)
        ev = entrada.eventos[entrada.eventos["regiao"].isin(["GLOBAL", regiao])]
        datas = linhas["data"].to_numpy()[pos]
        cal = variaveis_de_calendario(pd.DatetimeIndex(np.unique(datas)), ev, cfg, festivais)
        valores = cal.reindex(pd.DatetimeIndex(datas)).to_numpy(dtype="float32")
        for k, col in enumerate(cal.columns):
            if col not in linhas:
                linhas[col] = np.full(len(linhas), np.nan, dtype="float32")
            linhas.iloc[pos, linhas.columns.get_loc(col)] = valores[:, k]
    return linhas


# ================================================================================================ 5. datas de corte
def calcular_cortes(linhas: pd.DataFrame, cfg: Config, corte_validacao: Optional[str],
                    corte_teste: Optional[str]) -> dict[str, pd.Timestamp]:
    """RN25: divisão cronológica 70/20/10 sobre o calendário, igual para todos os itens. Hyndman e Athanasopoulos
    (2018, seção 3.4): o tamanho do teste depende do comprimento da série e do horizonte, e deve ser ao menos igual ao
    horizonte; com ~4 anos diários e horizonte de 7 dias, 10% (~150 dias) atende com folga."""
    inicio, fim = linhas["data"].min(), linhas["data"].max()
    dias = (fim - inicio).days + 1
    cv = pd.Timestamp(corte_validacao) if corte_validacao else inicio + pd.Timedelta(days=round(dias * cfg.proporcao_treino))
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


def ajustar(linhas: pd.DataFrame, treino: pd.Series, cfg: Config) -> dict[str, Any]:
    """RN24 + RN25: constantes globais, faixa do nível de item e vocabulário das categorias, só com as linhas de
    `treino` (o período de treinamento, sem os itens reservados da etapa 2c)."""
    const = {final: percentil_treino(linhas[bruto], treino, cfg, simetrico)
             for bruto, final, simetrico in CONSTANTES_GLOBAIS}
    niveis = linhas.loc[treino, ["item_id", "nivel_item"]].drop_duplicates("item_id")["nivel_item"].dropna()
    nmin, nmax = (float(niveis.min()), float(niveis.max())) if len(niveis) else (0.0, 1.0)
    vocab = {nome: montar_vocabulario(linhas.loc[treino, origem]) for nome, origem, _ in CATEGORICAS}
    return {"constantes": const, "nivel_item": {"min": nmin, "max": nmax}, "vocabulario": vocab}


def montar_vocabulario(codigos: pd.Series) -> dict[str, int]:
    """Variável 15: um índice por código visto no treino, a partir de 1 (0 = desconhecida)."""
    valores = sorted(int(v) for v in codigos.dropna().unique())
    return {str(v): i + 1 for i, v in enumerate(valores)}


def indices_do_vocabulario(codigos: pd.Series, vocab: dict[str, int]) -> pd.Series:
    """Variável 15: o índice de cada código; código fora do vocabulário (ou nulo) vira 0, desconhecida."""
    mapa = {float(v): i for v, i in vocab.items()}
    return codigos.map(mapa).fillna(0).astype("int32")


def aplicar(linhas: pd.DataFrame, ajuste: dict[str, Any], cfg: Config) -> None:
    """Aplica a normalização (de agora ou de uma versão anterior do modelo) a todas as linhas. Categoria fora do
    vocabulário, como a de um item de uma subclasse nunca vista no treino, vira 0 (desconhecida)."""
    const = ajuste["constantes"]
    for bruto, final, simetrico in CONSTANTES_GLOBAIS:
        linhas[final] = escalar(linhas[bruto], const[final], simetrico).astype("float32")
    # Sem pares na subclasse no dia, ou item sem preço de venda ao vendedor: 0.
    linhas["f_retorno_subclasse"] = linhas["f_retorno_subclasse"].fillna(0.0)
    linhas["f_preco_npc"] = linhas["f_preco_npc"].fillna(0.0)
    linhas["f_observado"] = linhas["observado"].astype("float32")

    qualidade = linhas["qualidade"].clip(0, cfg.qualidade_max) / cfg.qualidade_max
    linhas["f_qualidade"] = qualidade.fillna(0.0).astype("float32")
    nmin, nmax = ajuste["nivel_item"]["min"], ajuste["nivel_item"]["max"]
    nivel = ((linhas["nivel_item"] - nmin) / max(nmax - nmin, EPS)).clip(0, 1)
    linhas["f_nivel_item"] = nivel.fillna(0.0).astype("float32")
    linhas["f_commodity"] = linhas["commodity"].astype("float32")

    for nome, origem, idx_col in CATEGORICAS:
        linhas[idx_col] = indices_do_vocabulario(linhas[origem], ajuste["vocabulario"][nome])
    linhas.drop(columns=["log_return", "log_preco_ema14", "volatilidade_7d", "retorno_subclasse", "log_preco_npc",
                         "ema14_anterior", "classe_id", "subclasse_id", "subclasse_chave", "qualidade", "nivel_item",
                         "preco_npc", "commodity"], inplace=True)


def ajustar_e_aplicar(linhas: pd.DataFrame, treino: pd.Series, cfg: Config) -> dict[str, Any]:
    """RN24 + RN25: as constantes são calculadas com as linhas do treino e aplicadas a todas as linhas."""
    ajuste = ajustar(linhas, treino, cfg)
    aplicar(linhas, ajuste, cfg)
    return ajuste


# ============================================================================================== 7. janelas e separação
def montar_janelas(linhas: pd.DataFrame, cortes: dict[str, pd.Timestamp], cfg: Config) -> pd.DataFrame:
    """Uma amostra para cada dia "hoje" (id_linha_origem) com 30 dias de entrada válidos e 7 dias de alvo com preço.
    O período da amostra é o dos seus alvos; amostras cujos alvos atravessam uma data de corte são descartadas,
    para que nenhum alvo de treino caia na validação (e nenhum da validação, no teste)."""
    J, H = cfg.janela, cfg.horizonte
    n = len(linhas)
    if n < J + H:
        return pd.DataFrame()
    apta = linhas["apta"].to_numpy()
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
    })
    if "reservado" in linhas:  # etapa 2c: item fora do treino
        jan["reservado"] = linhas["reservado"].to_numpy()[o]
    for h in range(1, H + 1):
        jan[f"y_{h}"] = lp[o + h] - lp[o]          # log-retorno de hoje até o dia h (ainda sem normalizar)
        jan[f"obs_{h}"] = obs[o + h]               # o alvo do dia h foi observado (e não preenchido)?
    return jan


def normalizar_alvo(jan: pd.DataFrame, cfg: Config,
                    alvo: Optional[dict[str, list[float]]] = None) -> dict[str, list[float]]:
    """Escalonador próprio do alvo (como recomendado no estudo do orientador), ajustado só nas amostras de treino dos
    itens não reservados. Com `alvo` (normalização de outra base), só aplica."""
    cols = [f"y_{h}" for h in range(1, cfg.horizonte + 1)]
    if alvo is None:
        treino = jan["periodo"] == PERIODOS[0]
        if "reservado" in jan:
            treino &= ~jan["reservado"]
        if not treino.any():
            raise ValueError("Nenhuma amostra de treino: histórico curto demais para a janela, o horizonte e o corte.")
        media = jan.loc[treino, cols].mean().to_numpy(dtype="float64")
        desvio = jan.loc[treino, cols].std(ddof=0).to_numpy(dtype="float64")
        desvio = np.where(desvio > EPS, desvio, 1.0)
    else:
        media = np.asarray(alvo["media"], dtype="float64")
        desvio = np.asarray(alvo["desvio"], dtype="float64")
    if len(jan):
        jan[cols] = ((jan[cols].to_numpy(dtype="float64") - media) / desvio).astype("float32")
    return {"media": media.tolist(), "desvio": desvio.tolist()}


# ======================================================================================================= orquestração
def preparar(entrada: Entrada, cfg: Config, regiao: Optional[str] = "US", ignorar_aptidao: bool = False,
             filtro_liquidez: bool = True, ilvl_minimo: Optional[float] = None, max_itens: Optional[int] = None,
             corte_validacao: Optional[str] = None, corte_teste: Optional[str] = None, semente: int = 42,
             reservar_itens: float = 0.0, normalizacao_base: Optional[dict[str, Any]] = None,
             excluir_itens: Optional[set[int]] = None) -> Resultado:
    """Prepara a base. Etapa 2c: `reservar_itens` tira uma fração dos itens de tudo o que o modelo aprende;
    `normalizacao_base` aplica a normalização de outra base (outra versão do modelo) em vez de calculá-la."""
    if normalizacao_base is not None and reservar_itens:
        raise ValueError("reservar itens só faz sentido ao calcular a normalização, não ao reaproveitá-la")
    precos = selecionar_series(entrada, cfg, regiao, ignorar_aptidao, filtro_liquidez, ilvl_minimo, max_itens, semente,
                               excluir_itens)
    if precos.empty:
        raise ValueError("Nenhuma série selecionada (verifique a região, a aptidão e a liquidez).")
    linhas = montar_calendario(precos)
    logger.info("%d séries, %d linhas (série × dia).", linhas["serie_idx"].nunique(), len(linhas))
    linhas = higienizar(linhas, cfg)
    regioes_usadas = set(linhas["regiao"].astype(str).unique()) | {"GLOBAL"}
    eventos_usados = entrada.eventos[entrada.eventos["regiao"].isin(regioes_usadas)]
    if normalizacao_base is None:
        # O mesmo conjunto de festivais para todas as regiões (as colunas precisam ser as mesmas em todas as linhas).
        festivais = festivais_do_calendario(eventos_usados)
    else:  # as mesmas colunas de festival da versão do modelo
        festivais = {c: n for c, n in normalizacao_base["eventos_detalhados"]["colunas"].items() if c != VARIAVEL_FEIRA}

    # Ciclo do item (variáveis 19 e 20): lançamentos das expansões e início dos dados (da versão do modelo, se houver).
    criterios = criterios_dos_itens(entrada, cfg, regiao)
    base_ciclo = (normalizacao_base or {}).get("ciclo_do_item")
    if base_ciclo:
        lancamentos = np.array(base_ciclo["lancamentos"], dtype="datetime64[D]")
        expansoes = list(base_ciclo["expansoes"])
        inicio_dados = np.datetime64(base_ciclo["inicio_dos_dados"], "D")
    else:
        lancamentos, expansoes = lancamentos_de_expansao(eventos_usados)
        inicio_dados = np.datetime64(criterios["primeiro_registro"].min() if len(criterios) else linhas["data"].min(), "D")
    ciclo = {"lancamentos": lancamentos, "inicio_dados": inicio_dados}
    linhas = calcular_variaveis_brutas(linhas, entrada, cfg, festivais, ciclo)

    # Registro por item: atributos, critérios de seleção, expansão e reserva (itens.parquet).
    itens = (linhas.drop_duplicates("serie_idx")[["serie", "item_id", "classe_id", "subclasse_id", "commodity"]]
             .astype({"serie": str}).reset_index(drop=True))
    itens = itens.merge(criterios, on=["serie", "item_id"], how="left")
    idx_exp = expansao_do_item(itens["primeiro_registro"].to_numpy(dtype="datetime64[ns]"), lancamentos, inicio_dados,
                               cfg.acesso_antecipado_dias)
    itens["expansao"] = [expansoes[i] if i >= 0 else SEM_EXPANSAO for i in idx_exp]
    itens_por_expansao = {str(k): int(v) for k, v in itens["expansao"].value_counts().items()}
    if cfg.variavel_expansao_item or cfg.variavel_idade_item:
        logger.info("Etapa 2d: itens por expansão (pelo primeiro registro): %s", itens_por_expansao)
    reservados: set[int] = set()
    if reservar_itens:
        reservados = sortear_reservados(itens, reservar_itens, semente)
        linhas["reservado"] = linhas["item_id"].isin(reservados).to_numpy()
        logger.info("Etapa 2c: %d de %d itens reservados (fora do treino, das constantes e do vocabulário).",
                    len(reservados), itens["item_id"].nunique())
    itens["reservado"] = itens["item_id"].isin(reservados)

    if normalizacao_base is None:
        cortes = calcular_cortes(linhas, cfg, corte_validacao, corte_teste)
    else:  # mesmas datas de corte da versão do modelo; início e fim são os desta base
        cortes = {"inicio": linhas["data"].min(), "fim": linhas["data"].max(),
                  "corte_validacao": pd.Timestamp(normalizacao_base["cortes"]["corte_validacao"]),
                  "corte_teste": pd.Timestamp(normalizacao_base["cortes"]["corte_teste"])}
    linhas["periodo"] = periodo_da_data(linhas["data"], cortes).astype("category")
    treino = linhas["periodo"] == PERIODOS[0]
    if reservados:
        treino &= ~linhas["reservado"]
    unicos = linhas.drop_duplicates("item_id")
    cobertura = {c: float(unicos[c].notna().mean())
                 for c in ("classe_id", "subclasse_id", "qualidade", "nivel_item", "preco_npc")}
    itens_commodity = int(unicos["commodity"].sum())
    del unicos
    if normalizacao_base is None:
        ajuste = ajustar(linhas, treino, cfg)
    else:
        ajuste = {k: normalizacao_base[k] for k in ("constantes", "nivel_item", "vocabulario")}
    aplicar(linhas, ajuste, cfg)

    # Variável 14 detalhada: entram a feira e os festivais com ao menos um dia ativo no treino. Um festival que só
    # aparece na validação ou no teste teria pesos nunca treinados (ruído), então fica de fora e é registrado.
    extras: list[str] = []
    festivais_usados: dict[str, str] = {}
    ignorados: list[str] = []
    if normalizacao_base is not None:
        variaveis_seq = list(normalizacao_base["variaveis"]["sequencia"])
        festivais_usados = dict(normalizacao_base["eventos_detalhados"]["colunas"])
        ignorados = list(normalizacao_base["eventos_detalhados"]["sem_ocorrencia_no_treino"])
    else:
        if cfg.eventos_detalhados:
            candidatos = {VARIAVEL_FEIRA: "Darkmoon Faire", **festivais}
            for col, nome in candidatos.items():
                if col in linhas and float(linhas.loc[treino, col].max()) > 0:
                    extras += [col, col + SUFIXO_PROXIMOS]
                    festivais_usados[col] = nome
                else:
                    ignorados.append(nome)
            if ignorados:
                logger.info("Eventos sem nenhum dia ativo no treino (fora das variáveis): %s", ignorados)
        variaveis_seq = VARIAVEIS_SEQUENCIA + extras
        variaveis_seq += [VARIAVEL_EXPANSAO_ITEM] if cfg.variavel_expansao_item else []
        variaveis_seq += [VARIAVEL_IDADE_ITEM] if cfg.variavel_idade_item else []
    variaveis = variaveis_seq + VARIAVEIS_ESTATICAS
    linhas["apta"] = linhas["preco"].notna() & np.isfinite(linhas[variaveis].to_numpy(dtype="float32")).all(axis=1)
    jan = montar_janelas(linhas, cortes, cfg)
    alvo = normalizar_alvo(jan, cfg, None if normalizacao_base is None else normalizacao_base["alvo"])

    originais = linhas[["id_linha", "serie", "item_id", "regiao", "data", "periodo", "preco_bruto", "quantidade_bruta",
                        "descartado_rn03", "observado", "preenchido", "preco", "quantidade"]].copy()
    originais["preco_bruto"] = originais["preco_bruto"].round().astype("Int64")
    originais["preco"] = originais["preco"].round().astype("Int64")
    originais = originais.rename(columns={"preco": "preco_cobre"})

    normalizadas = linhas[["id_linha", "serie", "item_id", "data", "periodo", "apta"] + variaveis +
                          VARIAVEIS_CATEGORICAS].copy()
    normalizadas[variaveis] = normalizadas[variaveis].astype("float32")

    contagens: dict[str, Any] = {
        "series": int(linhas["serie_idx"].nunique()),
        "linhas": int(len(linhas)),
        "linhas_aptas": int(linhas["apta"].sum()),
        "descartadas_rn03": int(linhas["descartado_rn03"].sum()),
        "preenchidas": int(linhas["preenchido"].sum()),
        "amostras": {p: int((jan["periodo"] == p).sum()) if len(jan) else 0 for p in PERIODOS},
        "cobertura_atributos": cobertura,
        "itens_commodity": itens_commodity,
    }
    if reservados:
        contagens["amostras_reservadas"] = {p: int((jan["reservado"] & (jan["periodo"] == p)).sum()) for p in PERIODOS}
    normalizacao: dict[str, Any] = {
        "versao_formato": VERSAO_FORMATO,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origem": entrada.origem,
        "regiao": regiao,
        "config": cfg.como_dict(),
        "cortes": {k: v.date().isoformat() for k, v in cortes.items()},
        **ajuste,
        "alvo": alvo,
        "variaveis": {"sequencia": variaveis_seq, "estaticas": VARIAVEIS_ESTATICAS,
                      "categoricas": VARIAVEIS_CATEGORICAS},
        "eventos_detalhados": {"colunas": festivais_usados, "sem_ocorrencia_no_treino": ignorados},
        "contagens": contagens,
    }
    normalizacao["ciclo_do_item"] = {
        "lancamentos": [str(d) for d in lancamentos], "expansoes": expansoes,
        "inicio_dos_dados": str(inicio_dados), "acesso_antecipado_dias": cfg.acesso_antecipado_dias,
        "idade_limite_dias": cfg.idade_limite_dias, "itens_por_expansao": itens_por_expansao,
    }
    normalizacao["reserva"] = ({"fracao": reservar_itens, "semente": semente, "estratificada_por": "classe_id",
                                "itens": sorted(reservados)} if reservados else None)
    if normalizacao_base is not None:
        normalizacao["normalizacao_de"] = {"assinatura": assinatura_normalizacao(normalizacao_base),
                                           "pasta": normalizacao_base.get("_pasta")}
    normalizacao["assinatura"] = assinatura_normalizacao(normalizacao)
    if normalizacao_base is not None and normalizacao["assinatura"] != normalizacao["normalizacao_de"]["assinatura"]:
        raise AssertionError("a normalização aplicada difere da base de origem")
    return Resultado(originais, normalizadas, jan, normalizacao, itens)


def salvar(res: Resultado, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    res.linhas_originais.to_parquet(pasta / "linhas_originais.parquet", index=False)
    res.linhas_normalizadas.to_parquet(pasta / "linhas_normalizadas.parquet", index=False)
    for p in PERIODOS:  # a separação física: um arquivo de amostras por período
        res.janelas[res.janelas["periodo"] == p].to_parquet(pasta / f"janelas_{p}.parquet", index=False)
    (pasta / "normalizacao.json").write_text(json.dumps(res.normalizacao, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    if res.itens is not None:
        res.itens.to_parquet(pasta / "itens.parquet", index=False)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fonte = ap.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--banco", action="store_true", help="lê do PostgreSQL (variáveis DB_* ou --db-url)")
    fonte.add_argument("--csv", type=Path, help="pasta com precos.csv, itens.csv, eventos.csv, reinos.csv, aptos.csv")
    ap.add_argument("--db-url", help="URL do SQLAlchemy; padrão: montada com DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME")
    ap.add_argument("--env-arquivo", type=Path,
                    help="arquivo .env com as variáveis DB_* (ex.: ../../backend/.env); o conteúdo não é exibido")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--regiao", default="US", help="US ou EU (RN11); vazio = todas")
    ap.add_argument("--itens", help="lista de item_id separados por vírgula (só no modo --banco)")
    ap.add_argument("--max-itens", type=int, help="sorteia no máximo N séries (para testes rápidos)")
    ap.add_argument("--ignorar-aptidao", action="store_true", help="não filtra por aptidao_treinamento (RN15)")
    ap.add_argument("--sem-filtro-liquidez", action="store_true", help="não aplica a RN02 na seleção")
    ap.add_argument("--ilvl-minimo", type=float, help="RN07: nível mínimo dos equipamentos (valor a confirmar)")
    ap.add_argument("--corte-validacao", help="AAAA-MM-DD; padrão: 70%% do calendário")
    ap.add_argument("--corte-teste", help="AAAA-MM-DD; padrão: 90%% do calendário")
    ap.add_argument("--janela", type=int)
    ap.add_argument("--horizonte", type=int)
    ap.add_argument("--semente", type=int, default=42)
    eventos = ap.add_mutually_exclusive_group()
    eventos.add_argument("--eventos-detalhados", action="store_true",
                         help="variável 14 com um indicador por festival e pela Feira de Negrilua (comparação)")
    eventos.add_argument("--eventos-agregados", action="store_true",
                         help="variável 14 só como 'algum festival ativo' (padrão; mantido por compatibilidade)")
    ap.add_argument("--rn03-confirmacao", type=int, help="preços seguidos fora da faixa que confirmam um novo patamar")
    ap.add_argument("--rn03-ema-bruta", action="store_true",
                    help="RN03 com a EMA de todos os preços do banco (comportamento anterior, para comparação)")
    ap.add_argument("--variavel-expansao-item", action="store_true",
                    help="etapa 2d: variável 19, item da expansão vigente no dia")
    ap.add_argument("--variavel-idade-item", action="store_true",
                    help="etapa 2d: variável 20, idade do item (dias desde o primeiro registro)")
    ap.add_argument("--subclasse-por-classe", action="store_true",
                    help="etapa 2i: variáveis 6 e 15 pelo par (classe, subclasse), e não pelo código da subclasse sozinho")
    ap.add_argument("--reservar-itens", type=float, default=0.0,
                    help="etapa 2c: fração dos itens (ex.: 0.2) sorteada para ficar fora do treino, pela --semente")
    ap.add_argument("--normalizacao-de", type=Path,
                    help="etapa 2c: aplica a normalização (cortes, constantes, vocabulário, alvo) da base desta pasta")
    ap.add_argument("--excluir-itens-de", type=Path,
                    help="etapa 2c: não seleciona os itens que já estão na base desta pasta")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    base: Optional[dict[str, Any]] = None
    if args.normalizacao_de:
        conflitos = [n for n, v in (("--janela", args.janela), ("--horizonte", args.horizonte),
                                    ("--eventos-detalhados", args.eventos_detalhados),
                                    ("--rn03-confirmacao", args.rn03_confirmacao),
                                    ("--rn03-ema-bruta", args.rn03_ema_bruta), ("--corte-validacao", args.corte_validacao),
                                    ("--corte-teste", args.corte_teste), ("--reservar-itens", args.reservar_itens),
                                    ("--variavel-expansao-item", args.variavel_expansao_item),
                                    ("--variavel-idade-item", args.variavel_idade_item),
                                    ("--subclasse-por-classe", args.subclasse_por_classe)) if v]
        if conflitos:
            ap.error(f"com --normalizacao-de, a configuração vem da outra base; tire {', '.join(conflitos)}")
        base = json.loads((args.normalizacao_de / "normalizacao.json").read_text(encoding="utf-8"))
        base["_pasta"] = str(args.normalizacao_de)
    excluir: Optional[set[int]] = None
    if args.excluir_itens_de:
        excluir = set(pd.read_parquet(args.excluir_itens_de / "linhas_originais.parquet", columns=["item_id"])["item_id"]
                      .unique().tolist())
    cfg = Config()
    if base is not None:
        campos = set(Config.__dataclass_fields__)
        cfg = Config(**{k: v for k, v in base["config"].items() if k in campos})
    if args.janela:
        cfg = replace(cfg, janela=args.janela)
    if args.horizonte:
        cfg = replace(cfg, horizonte=args.horizonte)
    if args.rn03_confirmacao:
        cfg = replace(cfg, rn03_confirmacao=args.rn03_confirmacao)
    if args.rn03_ema_bruta:
        cfg = replace(cfg, rn03_ema_so_aceitos=False)
    if args.eventos_detalhados:
        cfg = replace(cfg, eventos_detalhados=True)
    if args.variavel_expansao_item:
        cfg = replace(cfg, variavel_expansao_item=True)
    if args.variavel_idade_item:
        cfg = replace(cfg, variavel_idade_item=True)
    if args.subclasse_por_classe:
        cfg = replace(cfg, subclasse_por_classe=True)

    if args.banco:
        if args.env_arquivo:
            from dotenv import load_dotenv  # python-dotenv, o mesmo do backend
            if not load_dotenv(args.env_arquivo, override=False):
                ap.error(f"não foi possível ler {args.env_arquivo}")
        itens = [int(x) for x in args.itens.split(",")] if args.itens else None
        entrada = carregar_banco(args.db_url or url_do_banco(), cfg, itens)
    else:
        entrada = carregar_csv(args.csv, cfg)

    res = preparar(entrada, cfg, regiao=args.regiao or None, ignorar_aptidao=args.ignorar_aptidao,
                   filtro_liquidez=not args.sem_filtro_liquidez, ilvl_minimo=args.ilvl_minimo,
                   max_itens=args.max_itens, corte_validacao=args.corte_validacao, corte_teste=args.corte_teste,
                   semente=args.semente, reservar_itens=args.reservar_itens, normalizacao_base=base,
                   excluir_itens=excluir)
    salvar(res, args.saida)
    c = res.normalizacao["contagens"]
    logger.info("Cortes: %s", res.normalizacao["cortes"])
    logger.info("Amostras: %s | linhas aptas: %d de %d | RN03: %d | preenchidas: %d",
                c["amostras"], c["linhas_aptas"], c["linhas"], c["descartadas_rn03"], c["preenchidas"])
    logger.info("Cobertura dos atributos fixos: %s | itens de commodity: %d", c["cobertura_atributos"],
                c["itens_commodity"])
    if res.normalizacao.get("reserva"):
        logger.info("Reservados (fora do treino): %d itens | amostras: %s", len(res.normalizacao["reserva"]["itens"]),
                    c["amostras_reservadas"])
    logger.info("Arquivos gravados em %s", args.saida.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
