"""Etapa 2i: refaz, numa cópia de uma base pronta, só a variável 6 (índice da subclasse) e o índice da subclasse da
variável 15, com a subclasse dentro da classe (`Config.subclasse_por_classe`).

As janelas, os alvos e as demais colunas ficam idênticos: a comparação com os modelos da base de origem isola a
correção. A base não é preparada de novo a partir do banco, que mudou desde a preparação (dias novos, aptidão).

Antes de gravar, a conferência: com a chave da base de origem, o cálculo tem de reproduzir exatamente a variável 6, a
constante dela, o vocabulário e os índices de classe e de subclasse gravados. Se não reproduzir, nada é gravado. Os
atributos dos itens vêm do banco (ou de um itens.csv), e a conferência também confirma que não mudaram.

Uso
    python refazer_subclasse.py --banco --pasta saida/treino01_agr --saida saida/treino2i_sub
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import shutil
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import PERIODOS, Config
from dataset import assinatura_normalizacao
from io_dados import carregar_itens_banco, carregar_itens_csv, url_do_banco
from preparar_dados import (CATEGORICAS, chave_da_subclasse, escalar, indices_do_vocabulario, montar_vocabulario,
                            percentil_treino, retorno_da_subclasse)

logger = logging.getLogger("refazer_subclasse")

COLUNAS_ORIGINAIS = ["id_linha", "serie", "item_id", "regiao", "data", "periodo", "observado", "preco_cobre",
                     "quantidade"]
CONSTANTE = "f_retorno_subclasse"
COLUNAS_REFEITAS = [CONSTANTE, "subclasse_idx"]


def config_da_base(normalizacao: dict[str, Any]) -> Config:
    campos = set(Config.__dataclass_fields__)
    return Config(**{k: v for k, v in normalizacao["config"].items() if k in campos})


def linhas_da_base(pasta: Path, itens: pd.DataFrame) -> pd.DataFrame:
    """As colunas que a variável 6 usa, a partir de linhas_originais.parquet, na mesma ordem (série, item, dia) da
    preparação. O log-retorno sai do preço já tratado pela RN03 e preenchido (RN24), como em calcular_variaveis_brutas."""
    o = pd.read_parquet(Path(pasta) / "linhas_originais.parquet", columns=COLUNAS_ORIGINAIS)
    if not np.array_equal(o["id_linha"].to_numpy(), np.arange(len(o))):
        raise ValueError("linhas_originais.parquet fora da ordem de id_linha")
    serie_idx = o.groupby(["serie", "item_id"], sort=False, observed=True).ngroup()
    log_preco = np.log(o["preco_cobre"].astype("float64"))
    o["log_return"] = log_preco - log_preco.groupby(serie_idx, sort=False).shift(1)
    o["quantidade"] = o["quantidade"].astype("float64")
    o["observado"] = o["observado"].astype(bool)
    atributos = itens.set_index("item_id")
    for col in ("classe_id", "subclasse_id"):
        o[col] = o["item_id"].map(atributos[col]) if len(atributos) else np.nan
    return o


def treino_da_base(linhas: pd.DataFrame, normalizacao: dict[str, Any]) -> pd.Series:
    """O período de treinamento sem os itens reservados da etapa 2c, como em preparar()."""
    treino = linhas["periodo"].astype(str) == PERIODOS[0]
    reserva = normalizacao.get("reserva") or {}
    if reserva.get("itens"):
        treino &= ~linhas["item_id"].isin(set(reserva["itens"]))
    return treino


def calcular(linhas: pd.DataFrame, treino: pd.Series, cfg: Config) -> dict[str, Any]:
    """Variável 6 e índices da variável 15 com a chave de `cfg`, pelas mesmas funções da preparação."""
    chave = chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], cfg)
    bruto = retorno_da_subclasse(linhas, chave)
    constante = percentil_treino(bruto, treino, cfg, True)
    codigos = {"classe_id": linhas["classe_id"], "subclasse_chave": chave}
    vocab = {nome: montar_vocabulario(codigos[origem][treino]) for nome, origem, _ in CATEGORICAS}
    out: dict[str, Any] = {
        "constante": constante,
        "vocabulario": vocab,
        CONSTANTE: escalar(bruto, constante, True).astype("float32").fillna(0.0),
        "sem_par_no_dia": bruto.isna() & chave.notna(),
    }
    for nome, origem, idx_col in CATEGORICAS:
        out[idx_col] = indices_do_vocabulario(codigos[origem], vocab[nome])
    return out


def _diferencas(a: np.ndarray, b: np.ndarray, atol: float) -> int:
    return int((~np.isclose(a, b, rtol=0, atol=atol, equal_nan=True)).sum())


def conferir(pasta: Path, linhas: pd.DataFrame, normalizacao: dict[str, Any], normalizadas: pd.DataFrame,
             treino: pd.Series) -> dict[str, Any]:
    """Com a chave da base de origem, o cálculo tem de dar o que está gravado nela. Uma diferença quer dizer que os
    atributos dos itens mudaram depois da preparação, ou que o cálculo não é o da preparação."""
    antigo = calcular(linhas, treino, config_da_base(normalizacao))
    problemas: dict[str, Any] = {}
    gravada = float(normalizacao["constantes"][CONSTANTE])
    if not math.isclose(antigo["constante"], gravada, rel_tol=1e-9):
        problemas["constante"] = {"gravada": gravada, "calculada": antigo["constante"]}
    if antigo["vocabulario"] != normalizacao["vocabulario"]:
        problemas["vocabulario"] = {"gravado": normalizacao["vocabulario"], "calculado": antigo["vocabulario"]}
    n6 = _diferencas(normalizadas[CONSTANTE].to_numpy(), antigo[CONSTANTE].to_numpy(), 1e-6)
    if n6:
        problemas[CONSTANTE] = n6
    for _, _, idx_col in CATEGORICAS:
        n = int((normalizadas[idx_col].to_numpy() != antigo[idx_col].to_numpy()).sum())
        if n:
            itens = normalizadas.loc[normalizadas[idx_col].to_numpy() != antigo[idx_col].to_numpy(), "item_id"]
            problemas[idx_col] = {"linhas": n, "itens": sorted(int(i) for i in itens.unique()[:20])}
    if problemas:
        raise ValueError(f"a variável 6 e os índices recalculados não batem com os da base {pasta}: "
                         f"{json.dumps(problemas, ensure_ascii=False, default=str)}")
    return {"linhas_conferidas": int(len(linhas)), "diferencas": 0, "constante": gravada,
            "sem_par_no_dia": int(antigo["sem_par_no_dia"].sum())}


def subclasses_dos_itens(linhas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por item, com o par e se o código da subclasse é usado por mais de uma classe na base."""
    itens = linhas.drop_duplicates("item_id")[["item_id", "classe_id", "subclasse_id"]].reset_index(drop=True)
    classes = itens.dropna().groupby("subclasse_id")["classe_id"].nunique()
    itens["codigo_compartilhado"] = itens["subclasse_id"].map(classes).fillna(0).gt(1)
    return itens


def refazer(pasta: Path, itens: pd.DataFrame, saida: Path, origem: str = "") -> dict[str, Any]:
    """Confere a base com a chave de origem e grava a cópia com a subclasse dentro da classe."""
    pasta, saida = Path(pasta), Path(saida)
    if pasta.resolve() == saida.resolve():
        raise ValueError("a saída tem de ser outra pasta: a base de origem não é alterada")
    normalizacao = json.loads((pasta / "normalizacao.json").read_text(encoding="utf-8"))
    cfg = config_da_base(normalizacao)
    if cfg.subclasse_por_classe:
        raise ValueError(f"a base {pasta} já usa a subclasse dentro da classe")
    linhas = linhas_da_base(pasta, itens)
    treino = treino_da_base(linhas, normalizacao)
    normalizadas = pd.read_parquet(pasta / "linhas_normalizadas.parquet")
    if not np.array_equal(normalizadas["id_linha"].to_numpy(), linhas["id_linha"].to_numpy()):
        raise ValueError("linhas_normalizadas.parquet e linhas_originais.parquet não estão alinhadas")
    conferencia = conferir(pasta, linhas, normalizacao, normalizadas, treino)
    logger.info("Conferência: %s", conferencia)

    novo = calcular(linhas, treino, replace(cfg, subclasse_por_classe=True))
    antes = normalizadas[COLUNAS_REFEITAS].copy()
    for col in COLUNAS_REFEITAS:
        normalizadas[col] = novo[col].to_numpy().astype(antes[col].dtype)
    apta = normalizadas["apta"].to_numpy(dtype=bool)
    mudou = ~np.isclose(antes[CONSTANTE].to_numpy(), normalizadas[CONSTANTE].to_numpy(), rtol=0, atol=1e-6)
    zero_antes = antes[CONSTANTE].to_numpy() == 0
    zero_depois = normalizadas[CONSTANTE].to_numpy() == 0
    subclasses = subclasses_dos_itens(linhas)
    contagens = {
        "linhas": int(len(linhas)),
        "linhas_aptas": int(apta.sum()),
        "variavel_6_mudou": {"linhas": int(mudou.sum()), "aptas": int((mudou & apta).sum())},
        "variavel_6_zero": {"antes": int(zero_antes.sum()), "depois": int(zero_depois.sum()),
                            "aptas_antes": int((zero_antes & apta).sum()),
                            "aptas_depois": int((zero_depois & apta).sum())},
        "sem_par_no_dia": {"antes": conferencia["sem_par_no_dia"], "depois": int(novo["sem_par_no_dia"].sum())},
        "constante": {"antes": conferencia["constante"], "depois": novo["constante"]},
        "vocabulario_subclasse": {"antes": len(normalizacao["vocabulario"]["subclasse_id"]),
                                  "depois": len(novo["vocabulario"]["subclasse_id"])},
        "indice_da_subclasse_mudou_linhas": int((antes["subclasse_idx"].to_numpy()
                                                 != normalizadas["subclasse_idx"].to_numpy()).sum()),
        "itens": int(len(subclasses)),
        "itens_com_codigo_compartilhado": int(subclasses["codigo_compartilhado"].sum()),
        "pares_na_base": int(subclasses.dropna(subset=["classe_id", "subclasse_id"])
                             .drop_duplicates(["classe_id", "subclasse_id"]).shape[0]),
    }
    logger.info("Contagens: %s", contagens)

    nova = copy.deepcopy(normalizacao)
    nova["gerado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nova["config"]["subclasse_por_classe"] = True
    nova["constantes"][CONSTANTE] = novo["constante"]
    nova["vocabulario"] = novo["vocabulario"]
    # As bases mais antigas (como a treino01_agr, de 06/10) não gravavam a assinatura: ela é calculada do mesmo jeito.
    assinatura_base = normalizacao.get("assinatura") or assinatura_normalizacao(normalizacao)
    nova["subclasse_refeita"] = {"base": str(pasta), "assinatura_base": assinatura_base, "origem": origem,
                                 "conferencia": conferencia, "contagens": contagens}
    nova["assinatura"] = assinatura_normalizacao(nova)

    saida.mkdir(parents=True, exist_ok=True)
    copiados = ["linhas_originais.parquet"] + [f"janelas_{p}.parquet" for p in PERIODOS] + ["itens.parquet"]
    for nome in copiados:
        if (pasta / nome).exists():
            shutil.copy2(pasta / nome, saida / nome)
    normalizadas.to_parquet(saida / "linhas_normalizadas.parquet", index=False)
    subclasses.to_csv(saida / "subclasses.csv", index=False)
    (saida / "normalizacao.json").write_text(json.dumps(nova, indent=2, ensure_ascii=False), encoding="utf-8")
    return nova["subclasse_refeita"] | {"assinatura": nova["assinatura"]}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fonte = ap.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--banco", action="store_true", help="atributos dos itens do PostgreSQL (variáveis DB_*)")
    fonte.add_argument("--csv", type=Path, help="pasta com itens.csv")
    ap.add_argument("--db-url", help="URL do SQLAlchemy; padrão: montada com DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME")
    ap.add_argument("--pasta", type=Path, required=True, help="a base de origem, que não é alterada")
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    normalizacao = json.loads((args.pasta / "normalizacao.json").read_text(encoding="utf-8"))
    if args.banco:
        itens = carregar_itens_banco(args.db_url or url_do_banco(), config_da_base(normalizacao))
    else:
        itens = carregar_itens_csv(args.csv)
    info = refazer(args.pasta, itens, args.saida, "banco" if args.banco else f"csv:{args.csv}")
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
