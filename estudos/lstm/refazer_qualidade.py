"""Etapa 2j: refaz, numa cópia de uma base pronta, só a qualidade do item (variável 16), que deixa de ser a qualidade
dividida por 5 e passa a ser uma coluna de 0 ou 1 por qualidade (`Config.qualidade_one_hot`), como pediu o orientador
em 30/10.

As janelas, os alvos e as demais colunas ficam idênticos: a comparação com os modelos da base de origem isola a troca. A
base não é preparada de novo a partir do banco, que mudou desde a preparação (dias novos, aptidão).

Antes de gravar, a conferência: com a qualidade de cada item, a `f_qualidade` recalculada (qualidade ÷ 5, sem qualidade
= 0) tem de ser igual à gravada em todas as linhas. Se não for, nada é gravado. As qualidades vêm do banco (ou de um
itens.csv), e a conferência também confirma que não mudaram desde a preparação.

Uso
    python refazer_qualidade.py --banco --pasta saida/treino2i_sub --saida saida/treino2j_qual
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import shutil
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import COLUNAS_DA_QUALIDADE, PERIODOS, variaveis_estaticas
from dataset import assinatura_normalizacao
from io_dados import carregar_itens_banco, carregar_itens_csv, url_do_banco
from preparar_dados import qualidade_em_colunas
from refazer_subclasse import config_da_base

logger = logging.getLogger("refazer_qualidade")

ANTIGA = "f_qualidade"
NOMES_DAS_QUALIDADES = {0: "pobre", 1: "comum", 2: "incomum", 3: "rara", 4: "épica", 5: "lendária ou acima"}
SEM_QUALIDADE = "sem qualidade"


def qualidade_por_linha(pasta: Path, itens: pd.DataFrame) -> pd.DataFrame:
    """id_linha, item_id e a qualidade do item de cada linha da base (nula se o item não tem qualidade cadastrada)."""
    o = pd.read_parquet(Path(pasta) / "linhas_originais.parquet", columns=["id_linha", "item_id"])
    if not np.array_equal(o["id_linha"].to_numpy(), np.arange(len(o))):
        raise ValueError("linhas_originais.parquet fora da ordem de id_linha")
    qualidade = itens.drop_duplicates("item_id").set_index("item_id")["qualidade"]
    o["qualidade"] = o["item_id"].map(qualidade).astype("float64")
    return o


def conferir(normalizadas: pd.DataFrame, qualidade: pd.Series, qualidade_max: int) -> dict[str, Any]:
    """A `f_qualidade` gravada tem de ser a da preparação: a qualidade limitada a `qualidade_max`, dividida por ele, e 0
    sem qualidade. Uma diferença em qualquer linha (por exemplo, um item que mudou de qualidade no banco) aborta."""
    esperada = (qualidade.clip(0, qualidade_max) / qualidade_max).fillna(0.0).astype("float32").to_numpy()
    gravada = normalizadas[ANTIGA].to_numpy(dtype="float32")
    diferentes = esperada != gravada
    if diferentes.any():
        itens = sorted(set(normalizadas.loc[diferentes, "item_id"].astype(int).tolist()))
        raise ValueError(f"a qualidade recalculada e a gravada na base não batem em {int(diferentes.sum())} linhas "
                         f"({len(itens)} itens, por exemplo {itens[:10]}); nada foi gravado")
    return {"linhas_conferidas": int(len(gravada)), "diferencas": 0}


def contar(linhas: pd.DataFrame, apta: np.ndarray) -> dict[str, Any]:
    """Itens e linhas aptas por qualidade, na ordem das colunas (lendária reúne lendária, artefato e herança)."""
    codigo = linhas["qualidade"].clip(upper=len(COLUNAS_DA_QUALIDADE) - 1)
    nome = codigo.map(NOMES_DAS_QUALIDADES).fillna(SEM_QUALIDADE)
    ordem = list(NOMES_DAS_QUALIDADES.values()) + [SEM_QUALIDADE]
    itens = nome.groupby(linhas["item_id"]).first().value_counts()
    aptas = nome[apta].value_counts()
    return {
        "itens_por_qualidade": {k: int(itens.get(k, 0)) for k in ordem},
        "linhas_aptas_por_qualidade": {k: int(aptas.get(k, 0)) for k in ordem},
        "itens_artefato_ou_heranca": int((linhas.drop_duplicates("item_id")["qualidade"] >= 6).sum()),
    }


def refazer(pasta: Path, itens: pd.DataFrame, saida: Path, origem: str = "") -> dict[str, Any]:
    """Confere a base com a qualidade de origem e grava a cópia com a qualidade em one-hot."""
    pasta, saida = Path(pasta), Path(saida)
    if pasta.resolve() == saida.resolve():
        raise ValueError("a saída tem de ser outra pasta: a base de origem não é alterada")
    normalizacao = json.loads((pasta / "normalizacao.json").read_text(encoding="utf-8"))
    cfg = config_da_base(normalizacao)
    if cfg.qualidade_one_hot:
        raise ValueError(f"a base {pasta} já usa a qualidade em one-hot")
    linhas = qualidade_por_linha(pasta, itens)
    normalizadas = pd.read_parquet(pasta / "linhas_normalizadas.parquet")
    if not np.array_equal(normalizadas["id_linha"].to_numpy(), linhas["id_linha"].to_numpy()):
        raise ValueError("linhas_normalizadas.parquet e linhas_originais.parquet não estão alinhadas")
    conferencia = conferir(normalizadas, linhas["qualidade"], cfg.qualidade_max)
    logger.info("Conferência: %s", conferencia)

    # As seis colunas entram no lugar da f_qualidade, na mesma posição da preparação com a opção ligada.
    novas = qualidade_em_colunas(linhas["qualidade"])
    colunas = list(normalizadas.columns)
    posicao = colunas.index(ANTIGA)
    for col, valores in novas.items():
        normalizadas[col] = valores
    normalizadas = normalizadas[colunas[:posicao] + COLUNAS_DA_QUALIDADE + colunas[posicao + 1:]]
    contagens = contar(linhas, normalizadas["apta"].to_numpy(dtype=bool))
    logger.info("Contagens: %s", contagens)

    nova = copy.deepcopy(normalizacao)
    nova["gerado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nova["config"]["qualidade_one_hot"] = True
    nova["variaveis"]["estaticas"] = variaveis_estaticas(replace(cfg, qualidade_one_hot=True))
    assinatura_base = normalizacao.get("assinatura") or assinatura_normalizacao(normalizacao)
    nova["qualidade_refeita"] = {"base": str(pasta), "assinatura_base": assinatura_base, "origem": origem,
                                 "conferencia": conferencia, "contagens": contagens}
    nova["assinatura"] = assinatura_normalizacao(nova)

    saida.mkdir(parents=True, exist_ok=True)
    copiados = (["linhas_originais.parquet"] + [f"janelas_{p}.parquet" for p in PERIODOS]
                + ["itens.parquet", "subclasses.csv"])
    for nome in copiados:
        if (pasta / nome).exists():
            shutil.copy2(pasta / nome, saida / nome)
    normalizadas.to_parquet(saida / "linhas_normalizadas.parquet", index=False)
    linhas.drop_duplicates("item_id")[["item_id", "qualidade"]].to_csv(saida / "qualidades.csv", index=False)
    (saida / "normalizacao.json").write_text(json.dumps(nova, indent=2, ensure_ascii=False), encoding="utf-8")
    return nova["qualidade_refeita"] | {"assinatura": nova["assinatura"]}


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
