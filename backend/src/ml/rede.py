"""CU11-C1 passo 8: rede e treino do modelo global (porte de `estudos/lstm/treinar.py`, configuração final).

- LSTM(64) → Dropout(0,2) → junção com os atributos fixos e os embeddings de classe (4) e subclasse (8) →
  Dense(32, ReLU) → Dense(7).
- Perda MAE, sem máscara (etapas 2b e 2e), Adam com taxa fixa de 0,001.
- Lotes de 512 montados sob demanda, com 400 mil amostras sorteadas do treino a cada época.
- EarlyStopping na validação (paciência 10, volta para a melhor época), com uma amostra fixa de até 200 mil amostras.
- FE1: treino que produz NaN (TerminateOnNaN), falta de memória ou esgotamento de recursos do TensorFlow.

O TensorFlow é importado só dentro das funções: o restante do pipeline roda sem ele.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

import numpy as np
import pandas as pd

from src.ml.configuracao import ConfigModelo
from src.ml.dataset import DadosPreparados

logger = logging.getLogger(__name__)

# Chamado ao fim de cada época: (época, máximo de épocas, perda de validação).
AoFimDaEpoca = Callable[[int, int, Optional[float]], None]


class FalhaNoTreinamento(RuntimeError):
    """CU11-C1-FE1: o treinamento não converge ou é interrompido por esgotamento de recursos."""


@dataclass
class ResultadoDoTreino:
    modelo: Any
    epocas: int
    melhor_epoca: int
    melhor_val_loss: Optional[float]
    duracao_segundos: float
    segundos_por_epoca: float
    amostras_treino: int
    amostras_validacao: int
    amostras_parada_antecipada: int
    versoes: dict[str, str] = field(default_factory=dict)


class Treinador(Protocol):
    """O que o treinamento inicial usa da rede. Os testes injetam um treinador falso para controlar as previsões."""

    def treinar(self, dados: DadosPreparados, jan_treino: pd.DataFrame, jan_validacao: pd.DataFrame,
                cfg: ConfigModelo, ao_fim_da_epoca: Optional[AoFimDaEpoca] = None) -> ResultadoDoTreino: ...

    def prever(self, modelo: Any, dados: DadosPreparados, jan: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]: ...

    def salvar(self, modelo: Any, caminho: Path) -> None: ...


def construir_modelo(dados: DadosPreparados, cfg: ConfigModelo):  # type: ignore[no-untyped-def]
    import keras
    from keras import layers

    voc = dados.normalizacao["vocabulario"]
    seq = keras.Input((dados.janela, len(dados.var_seq)), name="X_seq")
    est = keras.Input((len(dados.var_est),), name="X_est")
    cat = keras.Input((2,), dtype="int32", name="X_cat")
    h = layers.LSTM(cfg.unidades, name="lstm")(seq)
    h = layers.Dropout(cfg.dropout, name="dropout")(h)
    classe = layers.Flatten()(layers.Embedding(len(voc["classe_id"]) + 1, 4, name="emb_classe")(cat[:, 0:1]))
    subclasse = layers.Flatten()(layers.Embedding(len(voc["subclasse_id"]) + 1, 8, name="emb_subclasse")(cat[:, 1:2]))
    h = layers.Concatenate()([h, est, classe, subclasse])
    h = layers.Dense(32, activation="relu")(h)
    saida = layers.Dense(dados.horizonte, name="y")(h)
    modelo = keras.Model([seq, est, cat], saida, name="lstm_global")
    # Sem a máscara, a perda mascarada do estudo é igual à MAE (ou à Huber, ou à MSE) do Keras sobre os 7 dias.
    perdas = {"mae": keras.losses.MeanAbsoluteError(), "huber": keras.losses.Huber(delta=1.0),
              "mse": keras.losses.MeanSquaredError()}
    modelo.compile(optimizer=keras.optimizers.Adam(cfg.taxa_aprendizado), loss=perdas[cfg.perda], metrics=["mae"])
    return modelo


def criar_lotes(dados: DadosPreparados, jan: pd.DataFrame, lote: int, por_epoca: int, embaralhar: bool,
                semente: int):  # type: ignore[no-untyped-def]
    """Lotes sob demanda, sem materializar todas as janelas. A cada época sorteia `por_epoca` amostras (0 = todas)."""
    import keras

    class Lotes(keras.utils.PyDataset):
        def __init__(self) -> None:
            super().__init__(workers=1, use_multiprocessing=False)
            self.rng = np.random.default_rng(semente)
            self.n = len(jan) if not por_epoca else min(por_epoca, len(jan))
            self._sortear()

        def _sortear(self) -> None:
            if embaralhar:
                self.ordem = self.rng.choice(len(jan), size=self.n, replace=False)
            else:
                self.ordem = np.arange(self.n)

        def __len__(self) -> int:
            return math.ceil(self.n / lote)

        def __getitem__(self, i: int):  # type: ignore[no-untyped-def]
            t = dados.tensores(jan.iloc[self.ordem[i * lote:(i + 1) * lote]])
            return {"X_seq": t["X_seq"], "X_est": t["X_est"], "X_cat": t["X_cat"]}, t["y"]

        def on_epoch_end(self) -> None:
            self._sortear()

    return Lotes()


def prever(modelo: Any, dados: DadosPreparados, jan: pd.DataFrame, lote: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    """Previsões normalizadas (yhat_1 ... yhat_7) com o id de cada amostra."""
    if jan.empty:
        return np.zeros(0, dtype=np.int64), np.zeros((0, dados.horizonte), dtype=np.float32)
    ids, saidas = [], []
    for ini in range(0, len(jan), lote):
        t = dados.tensores(jan.iloc[ini:ini + lote])
        saidas.append(np.asarray(modelo.predict_on_batch({"X_seq": t["X_seq"], "X_est": t["X_est"],
                                                          "X_cat": t["X_cat"]})))
        ids.append(t["id_amostra"])
    return np.concatenate(ids), np.concatenate(saidas)


class TreinadorKeras:
    """CU11-C1 passo 8 com o Keras/TensorFlow."""

    def treinar(self, dados: DadosPreparados, jan_treino: pd.DataFrame, jan_validacao: pd.DataFrame,
                cfg: ConfigModelo, ao_fim_da_epoca: Optional[AoFimDaEpoca] = None) -> ResultadoDoTreino:
        """Treina com as amostras de treino do conjunto de treinamento e para quando o erro na validação deixa de
        diminuir (RN25). Levanta FalhaNoTreinamento (FE1) se o treino divergir ou faltar recurso."""
        import keras
        import tensorflow as tf

        if jan_treino.empty or jan_validacao.empty:
            raise FalhaNoTreinamento(f"Sem amostras para treinar (treino {len(jan_treino)}, validação "
                                     f"{len(jan_validacao)}).")
        keras.utils.set_random_seed(cfg.semente)
        va_es = jan_validacao if not cfg.amostras_validacao or len(jan_validacao) <= cfg.amostras_validacao else \
            jan_validacao.sample(cfg.amostras_validacao, random_state=cfg.semente).sort_values("id_amostra")
        logger.info("CU11-C1 passo 8: treino %d amostras (por época: %d), validação %d (parada antecipada com %d).",
                    len(jan_treino), min(cfg.amostras_por_epoca or len(jan_treino), len(jan_treino)),
                    len(jan_validacao), len(va_es))

        vigia = _Vigia(cfg.epocas_max, ao_fim_da_epoca)
        callbacks = [
            keras.callbacks.EarlyStopping(monitor="val_loss", patience=cfg.paciencia, restore_best_weights=True),
            keras.callbacks.TerminateOnNaN(),
            vigia.callback(keras),
        ]
        inicio = time.time()
        try:
            modelo = construir_modelo(dados, cfg)
            hist = modelo.fit(
                criar_lotes(dados, jan_treino, cfg.lote, cfg.amostras_por_epoca, True, cfg.semente),
                validation_data=criar_lotes(dados, va_es, cfg.lote, 0, False, cfg.semente),
                epochs=cfg.epocas_max, callbacks=callbacks, verbose=2)
        except (MemoryError, tf.errors.ResourceExhaustedError) as e:
            raise FalhaNoTreinamento(f"Treinamento interrompido por esgotamento de recursos: {e!r}") from e
        duracao = time.time() - inicio
        perdas = hist.history.get("loss", [])
        val = hist.history.get("val_loss", [])
        if vigia.perda_invalida or not perdas or not np.all(np.isfinite(perdas)) or not np.all(np.isfinite(val)):
            raise FalhaNoTreinamento("O treinamento não convergiu: a perda deixou de ser um número finito (NaN).")
        melhor = int(np.argmin(val)) + 1
        return ResultadoDoTreino(
            modelo=modelo, epocas=len(val), melhor_epoca=melhor, melhor_val_loss=float(min(val)),
            duracao_segundos=round(duracao, 1), segundos_por_epoca=round(duracao / max(len(val), 1), 1),
            amostras_treino=len(jan_treino), amostras_validacao=len(jan_validacao),
            amostras_parada_antecipada=len(va_es),
            versoes={"tensorflow": tf.__version__, "keras": keras.__version__},
        )

    def prever(self, modelo: Any, dados: DadosPreparados, jan: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return prever(modelo, dados, jan)

    def salvar(self, modelo: Any, caminho: Path) -> None:
        modelo.save(caminho)


class _Vigia:
    """Acompanha o treino: registra o andamento ao fim de cada época e nota a perda que deixa de ser finita."""

    def __init__(self, epocas_max: int, ao_fim_da_epoca: Optional[AoFimDaEpoca]) -> None:
        self.epocas_max = epocas_max
        self.ao_fim_da_epoca = ao_fim_da_epoca
        self.perda_invalida = False

    def callback(self, keras: Any) -> Any:
        vigia = self

        class Vigia(keras.callbacks.Callback):  # type: ignore[misc, name-defined]
            def on_train_batch_end(self, batch: int, logs: Optional[dict[str, Any]] = None) -> None:
                perda = (logs or {}).get("loss")
                if perda is not None and not np.isfinite(float(perda)):
                    vigia.perda_invalida = True

            def on_epoch_end(self, epoch: int, logs: Optional[dict[str, Any]] = None) -> None:
                if vigia.ao_fim_da_epoca is not None:
                    val = (logs or {}).get("val_loss")
                    vigia.ao_fim_da_epoca(epoch + 1, vigia.epocas_max, None if val is None else float(val))

        return Vigia()
