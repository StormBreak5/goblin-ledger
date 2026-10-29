"""Etapa 2g: diagnóstico da camada densa de 32 de um modelo treinado.

Para cada amostra do período, calcula as 32 pré-ativações da camada (x · W + b, antes da ativação) e conta:
- as amostras em que nenhuma unidade tem pré-ativação positiva. Com a ReLU, a saída dessas amostras é exatamente o
  viés da camada de saída, a mesma previsão para qualquer item (no sistema, 12% das janelas de 19/10/2026);
- as unidades que não ficam positivas em nenhuma amostra.
Com a LeakyReLU e a GELU, as mesmas contagens mostram quantas amostras ficariam sem sinal se a ativação fosse a ReLU.

Uso
    python ativacoes.py --modelo saida/treino01_agr/modelos/mae_s42 --pasta saida/treino01_agr --periodo validacao
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from dataset import DadosPreparados, assinatura_normalizacao


def camada_densa(modelo: Any) -> Any:
    """A camada densa entre a junção (LSTM, atributos e embeddings) e a saída `y`."""
    import keras

    densas = [c for c in modelo.layers if isinstance(c, keras.layers.Dense) and c.name != "y"]
    if len(densas) != 1:
        raise ValueError(f"esperava uma camada densa além da saída, encontrei {len(densas)}")
    return densas[0]


def pre_ativacoes(modelo: Any, dados: DadosPreparados, jan: pd.DataFrame, lote: int = 4096) -> np.ndarray:
    """[amostras, unidades]: a entrada da camada densa vezes os pesos, mais o viés."""
    import keras

    densa = camada_densa(modelo)
    entrada = keras.Model(modelo.inputs, densa.input)
    pesos, vies = (np.asarray(p, dtype=np.float64) for p in densa.get_weights())
    saidas = []
    for ini in range(0, len(jan), lote):
        t = dados.tensores(jan.iloc[ini:ini + lote])
        x = np.asarray(entrada.predict_on_batch({"X_seq": t["X_seq"], "X_est": t["X_est"], "X_cat": t["X_cat"]}),
                       dtype=np.float64)
        saidas.append(x @ pesos + vies)
    return np.concatenate(saidas) if saidas else np.zeros((0, len(vies)))


def resumir(z: np.ndarray) -> dict[str, Any]:
    positivas = z > 0
    ativas = positivas.sum(axis=1)
    n = int(len(z))
    sem = int((ativas == 0).sum())
    return {
        "amostras": n,
        "unidades": int(z.shape[1]),
        "amostras_sem_unidade_ativa": sem,
        "fracao_sem_unidade_ativa": round(sem / n, 6) if n else None,
        "unidades_nunca_ativas": int((~positivas.any(axis=0)).sum()) if n else int(z.shape[1]),
        "unidades_ativas_por_amostra": ({"p10": float(np.percentile(ativas, 10)), "mediana": float(np.median(ativas)),
                                         "p90": float(np.percentile(ativas, 90))} if n else None),
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", type=Path, required=True, help="pasta do modelo (modelo.keras e normalizacao.json)")
    ap.add_argument("--pasta", type=Path, required=True, help="a base do modelo")
    ap.add_argument("--periodo", choices=["treino", "validacao"], default="validacao",
                    help="o teste fica de fora (RN25)")
    ap.add_argument("--max-amostras", type=int, default=0, help="sorteia no máximo N amostras; 0 = todas")
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args(argv)

    import keras

    dados = DadosPreparados(args.pasta)
    norm_modelo = json.loads((args.modelo / "normalizacao.json").read_text(encoding="utf-8"))
    if assinatura_normalizacao(norm_modelo) != assinatura_normalizacao(dados.normalizacao):
        ap.error(f"{args.modelo} foi treinado com outra normalização que a de {args.pasta}")
    modelo = keras.models.load_model(args.modelo / "modelo.keras", compile=False)
    jan = dados.janelas(args.periodo)
    if args.max_amostras and len(jan) > args.max_amostras:
        jan = jan.sample(args.max_amostras, random_state=args.semente).sort_values("id_amostra")
    info_treino = args.modelo / "treino.json"
    parametros = json.loads(info_treino.read_text(encoding="utf-8")).get("parametros", {}) if info_treino.exists() \
        else {}
    resumo = {"modelo": args.modelo.name, "periodo": args.periodo,
              "ativacao": parametros.get("ativacao", "relu"), **resumir(pre_ativacoes(modelo, dados, jan))}
    (args.modelo / f"ativacoes_{args.periodo}.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False),
                                                                encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
