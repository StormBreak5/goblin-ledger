"""Exemplo mínimo de treino da LSTM global com os dados preparados, só para fechar o ciclo
preparar → treinar → prever → avaliar. A arquitetura segue o estudo do orientador: LSTM(64), Dropout(0,2), Adam,
EarlyStopping(patience=10); a saída é Dense(7), um log-retorno normalizado para cada dia do horizonte. Os atributos
fixos e os embeddings de classe (4 dimensões) e subclasse (8 dimensões) entram depois da LSTM.

Uso (precisa de tensorflow, que não está no requirements.txt do estudo)
    python exemplo_keras.py --pasta saida/estudo01 --max-amostras 200000 --epocas 50
    python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes saida/estudo01/previsoes_validacao_lstm.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from avaliar import salvar_previsoes
from dataset import DadosPreparados


def amostrar(dados: DadosPreparados, periodo: str, maximo: Optional[int], semente: int) -> dict[str, np.ndarray]:
    jan = dados.janelas(periodo)
    if maximo and len(jan) > maximo:
        jan = jan.sample(maximo, random_state=semente)
    return dados.tensores(jan)


def construir_modelo(dados: DadosPreparados):  # type: ignore[no-untyped-def]
    import keras
    from keras import layers

    voc = dados.normalizacao["vocabulario"]
    seq = keras.Input((dados.janela, len(dados.var_seq)), name="X_seq")
    est = keras.Input((len(dados.var_est),), name="X_est")
    cat = keras.Input((2,), dtype="int32", name="X_cat")
    h = layers.LSTM(64)(seq)
    h = layers.Dropout(0.2)(h)
    classe = layers.Flatten()(layers.Embedding(len(voc["classe_id"]) + 1, 4)(cat[:, 0:1]))
    subclasse = layers.Flatten()(layers.Embedding(len(voc["subclasse_id"]) + 1, 8)(cat[:, 1:2]))
    h = layers.Concatenate()([h, est, classe, subclasse])
    h = layers.Dense(32, activation="relu")(h)
    saida = layers.Dense(dados.horizonte, name="y")(h)
    modelo = keras.Model([seq, est, cat], saida)
    modelo.compile(optimizer=keras.optimizers.Adam(1e-3), loss="mse", metrics=["mae"])
    return modelo


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--max-amostras", type=int, default=200_000)
    ap.add_argument("--epocas", type=int, default=50)
    ap.add_argument("--lote", type=int, default=512)
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args(argv)

    import keras

    keras.utils.set_random_seed(args.semente)
    dados = DadosPreparados(args.pasta)
    tr = amostrar(dados, "treino", args.max_amostras, args.semente)
    va = amostrar(dados, "validacao", None, args.semente)

    def entradas(t: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        return {"X_seq": t["X_seq"], "X_est": t["X_est"], "X_cat": t["X_cat"]}

    modelo = construir_modelo(dados)
    parada = keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
    modelo.fit(entradas(tr), tr["y"], validation_data=(entradas(va), va["y"]), epochs=args.epocas,
               batch_size=args.lote, callbacks=[parada], verbose=2)

    yhat = modelo.predict(entradas(va), batch_size=4096, verbose=0)
    destino = args.pasta / "previsoes_validacao_lstm.parquet"
    salvar_previsoes(va["id_amostra"], yhat, destino)   # o id_amostra acompanha cada previsão até a avaliação
    modelo.save(args.pasta / "modelo_lstm.keras")
    print(f"Previsões gravadas em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
