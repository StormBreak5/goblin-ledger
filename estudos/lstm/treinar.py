"""Treino da LSTM global com os dados preparados (passos 6 e 7 do roteiro).

- Usa todas as amostras de treino, montando os lotes sob demanda (nada de [milhões, 30, 16] na memória). A cada época
  sorteia `--amostras-por-epoca` amostras do treino (0 = todas).
- Para quando o erro na validação passa `--paciencia` épocas sem melhorar e volta para a melhor versão (EarlyStopping).
- Máscara (opcional, `--mascara`): o erro de cada amostra passa a ser a média só dos dias previstos com preço
  observado (obs_1..obs_7). O padrão é sem máscara: na etapa 2b (3 sementes, validação), treinar sem a máscara foi
  melhor (docs/relatorio-etapa2b.md).
- Grava em <pasta>/modelos/<nome>/: modelo.keras, normalizacao.json (as constantes desta versão, RN25), treino.json,
  historico.csv e previsoes_validacao.parquet (com id_amostra, pronto para o avaliar.py).
- O período de teste só é previsto com --prever-teste (junto com o treino) ou com --apenas-prever-teste (usa o modelo
  já gravado em modelos/<nome>). Use uma única vez, com a configuração já escolhida (RN25).
- Perda: o padrão é a MAE (erro absoluto), aprovada na etapa 2e: o modelo passa a mirar a mediana, a mesma coisa
  que a RN10 mede (MdAPE), e a mediana do MdAPE por item caiu de 22,67% para 20,62% (docs/relatorio-etapa2e.md).
  `--perda huber` repete a configuração anterior. `--reduzir-taxa` (ReduceLROnPlateau) foi testada e reprovada.
- Etapa 2g: `--ativacao leaky_relu` ou `gelu` troca a ativação da camada densa de 32 (o padrão continua a ReLU).
- Etapa 2h: `--calendario-futuro` (arquivo do calendario_futuro.py) junta a entrada X_fut [7, 6], o calendário de D+1
  a D+7 conhecido em D, achatada e juntada antes da camada densa de 32. Sem a opção, a rede não muda.
- Etapa 2c: numa base preparada com --reservar-itens, as amostras dos itens reservados ficam fora do treino e da
  parada antecipada (o modelo nunca as vê), mas são previstas na validação, para medir o erro em itens não vistos.
  Com --incluir-reservados, treina com todos os itens (o controle do experimento).

Uso
    python treinar.py --pasta saida/real01 --nome lstm01
    python avaliar.py --pasta saida/real01 --periodo validacao --previsoes saida/real01/modelos/lstm01/previsoes_validacao.parquet
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from avaliar import salvar_previsoes
from calendario_futuro import COLUNAS_FUTURAS, CalendarioFuturo
from dataset import DadosPreparados


def criar_perdas(tipo: str, horizonte: int, delta: float = 1.0):  # type: ignore[no-untyped-def]
    """Perda e métrica mascaradas. y_true chega como [y_1..y_H, obs_1..obs_H]; os dias com obs = 0 não contam.
    Com todos os obs = 1, a perda é igual à Huber, à MSE ou à MAE do Keras sobre os H dias. A MAE (etapa 2e) leva o
    modelo a prever a mediana, que é o que a RN10 mede (MdAPE); a Huber trata os erros pequenos como quadráticos e é
    puxada pelos picos."""
    if tipo not in ("huber", "mse", "mae"):
        raise ValueError(f"perda desconhecida: {tipo}")
    from keras import ops

    def _separar(y_true, y_pred):  # type: ignore[no-untyped-def]
        y, m = y_true[:, :horizonte], y_true[:, horizonte:]
        return y_pred - y, m, ops.maximum(ops.sum(m, axis=-1), 1.0)

    def perda_mascarada(y_true, y_pred):  # type: ignore[no-untyped-def]
        e, m, n = _separar(y_true, y_pred)
        if tipo == "huber":
            a = ops.abs(e)
            elem = ops.where(a <= delta, 0.5 * e * e, delta * (a - 0.5 * delta))
        elif tipo == "mae":
            elem = ops.abs(e)
        else:
            elem = e * e
        return ops.sum(elem * m, axis=-1) / n

    def mae_mascarado(y_true, y_pred):  # type: ignore[no-untyped-def]
        e, m, n = _separar(y_true, y_pred)
        return ops.sum(ops.abs(e) * m, axis=-1) / n

    return perda_mascarada, mae_mascarado


ATIVACOES = ("relu", "leaky_relu", "gelu")
INCLINACAO_LEAKY = 0.1  # etapa 2g: inclinação da LeakyReLU para pré-ativações negativas


def construir_modelo(dados: DadosPreparados, unidades: int, dropout: float, taxa: float, perda: str,  # type: ignore[no-untyped-def]
                     ativacao: str = "relu", futuro: Optional[tuple[int, int]] = None):
    """`ativacao` (etapa 2g) é a da camada densa de 32. Com a ReLU, uma amostra cujas 32 pré-ativações são negativas
    sai igual ao viés da camada de saída; a LeakyReLU e a GELU mantêm um gradiente para elas. `futuro` (etapa 2h) é o
    formato (dias, variáveis) do X_fut, o calendário dos dias previstos, juntado antes da camada densa."""
    import keras
    from keras import layers

    if ativacao not in ATIVACOES:
        raise ValueError(f"ativação desconhecida: {ativacao}")
    voc = dados.normalizacao["vocabulario"]
    seq = keras.Input((dados.janela, len(dados.var_seq)), name="X_seq")
    est = keras.Input((len(dados.var_est),), name="X_est")
    cat = keras.Input((2,), dtype="int32", name="X_cat")
    h = layers.LSTM(unidades, name="lstm")(seq)
    h = layers.Dropout(dropout, name="dropout")(h)
    classe = layers.Flatten()(layers.Embedding(len(voc["classe_id"]) + 1, 4, name="emb_classe")(cat[:, 0:1]))
    subclasse = layers.Flatten()(layers.Embedding(len(voc["subclasse_id"]) + 1, 8, name="emb_subclasse")(cat[:, 1:2]))
    entradas = [seq, est, cat]
    partes = [h, est, classe, subclasse]
    if futuro is not None:
        fut = keras.Input(futuro, name="X_fut")
        entradas.append(fut)
        partes.append(layers.Flatten(name="fut_achatado")(fut))
    h = layers.Concatenate()(partes)
    if ativacao == "leaky_relu":
        h = layers.LeakyReLU(negative_slope=INCLINACAO_LEAKY)(layers.Dense(32)(h))
    else:
        h = layers.Dense(32, activation=ativacao)(h)
    saida = layers.Dense(dados.horizonte, name="y")(h)
    modelo = keras.Model(entradas, saida, name="lstm_global")
    fn_perda, fn_mae = criar_perdas(perda, dados.horizonte)
    modelo.compile(optimizer=keras.optimizers.Adam(taxa), loss=fn_perda, metrics=[fn_mae])
    return modelo


def entradas_do_lote(t: dict[str, np.ndarray], jan: pd.DataFrame,
                     calendario: Optional[CalendarioFuturo]) -> dict[str, np.ndarray]:
    x = {"X_seq": t["X_seq"], "X_est": t["X_est"], "X_cat": t["X_cat"]}
    if calendario is not None:  # etapa 2h
        x["X_fut"] = calendario.tensor(jan["serie"], jan["data_origem"])
    return x


def criar_lotes(dados: DadosPreparados, jan: pd.DataFrame, lote: int, por_epoca: int, embaralhar: bool, semente: int,
                usar_mascara: bool = True, calendario: Optional[CalendarioFuturo] = None):  # type: ignore[no-untyped-def]
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
            parte = jan.iloc[self.ordem[i * lote:(i + 1) * lote]]
            t = dados.tensores(parte)
            mascara = t["mascara"].astype(np.float32) if usar_mascara else np.ones_like(t["y"], dtype=np.float32)
            return entradas_do_lote(t, parte, calendario), np.concatenate([t["y"], mascara], 1)

        def on_epoch_end(self) -> None:
            self._sortear()

    return Lotes()


def prever(modelo, dados: DadosPreparados, jan: pd.DataFrame, lote: int = 4096,  # type: ignore[no-untyped-def]
           calendario: Optional[CalendarioFuturo] = None) -> tuple[np.ndarray, np.ndarray]:
    if ("X_fut" in [i.name for i in modelo.inputs]) != (calendario is not None):
        raise ValueError("o calendário futuro (etapa 2h) tem de ser passado se, e só se, o modelo tem a entrada X_fut")
    ids, saidas = [], []
    for ini in range(0, len(jan), lote):
        parte = jan.iloc[ini:ini + lote]
        t = dados.tensores(parte)
        saidas.append(modelo.predict_on_batch(entradas_do_lote(t, parte, calendario)))
        ids.append(t["id_amostra"])
    return np.concatenate(ids), np.concatenate(saidas)


def separar_reservados(jan_tr: pd.DataFrame, jan_va: pd.DataFrame,
                       incluir: bool) -> tuple[pd.DataFrame, pd.DataFrame, Optional[dict[str, Any]]]:
    """Etapa 2c: tira os itens reservados do treino e da validação usada na parada antecipada (a escolha da época
    também não pode depender deles). Devolve o treino, a validação da parada antecipada e o resumo da reserva."""
    if "reservado" not in jan_tr.columns:
        return jan_tr, jan_va, None
    itens = int(pd.concat([jan_tr.loc[jan_tr["reservado"], "item_id"], jan_va.loc[jan_va["reservado"], "item_id"]])
                .nunique())
    resumo = {"itens_reservados": itens, "incluidos_no_treino": bool(incluir),
              "amostras_reservadas_treino": int(jan_tr["reservado"].sum()),
              "amostras_reservadas_validacao": int(jan_va["reservado"].sum())}
    if incluir:
        return jan_tr, jan_va, resumo
    return (jan_tr[~jan_tr["reservado"].to_numpy()].reset_index(drop=True),
            jan_va[~jan_va["reservado"].to_numpy()].reset_index(drop=True), resumo)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True, help="saída do preparar_dados.py")
    ap.add_argument("--nome", default=None, help="nome desta versão (padrão: lstm_<data-hora>)")
    ap.add_argument("--epocas", type=int, default=100, help="máximo de épocas")
    ap.add_argument("--paciencia", type=int, default=10, help="épocas sem melhora na validação até parar")
    ap.add_argument("--lote", type=int, default=512)
    ap.add_argument("--amostras-por-epoca", type=int, default=400_000, help="sorteadas do treino a cada época; 0 = todas")
    ap.add_argument("--amostras-validacao", type=int, default=200_000,
                    help="amostra fixa da validação para a parada antecipada; 0 = todas")
    ap.add_argument("--perda", choices=["huber", "mse", "mae"], default="mae",
                    help="padrão: mae (etapa 2e); huber = configuração das etapas 2 a 2d")
    ap.add_argument("--reduzir-taxa", action="store_true",
                    help="etapa 2e: multiplica a taxa por --fator-taxa após --paciencia-taxa épocas sem melhora")
    ap.add_argument("--fator-taxa", type=float, default=0.5)
    ap.add_argument("--paciencia-taxa", type=int, default=3)
    ap.add_argument("--taxa-minima", type=float, default=1e-5)
    ap.add_argument("--unidades", type=int, default=64)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--ativacao", choices=ATIVACOES, default="relu",
                    help="etapa 2g: ativação da camada densa de 32; padrão: relu (configuração final)")
    ap.add_argument("--calendario-futuro", type=Path,
                    help="etapa 2h: calendario_futuro.parquet do calendario_futuro.py; junta a entrada X_fut")
    ap.add_argument("--taxa", type=float, default=1e-3, help="taxa de aprendizado do Adam")
    ap.add_argument("--semente", type=int, default=42)
    mascara = ap.add_mutually_exclusive_group()
    mascara.add_argument("--mascara", action="store_true",
                         help="ignora no erro os dias preenchidos ou descartados pela RN03 (comparação)")
    mascara.add_argument("--sem-mascara", action="store_true", help="padrão; mantido por compatibilidade")
    ap.add_argument("--incluir-reservados", action="store_true",
                    help="etapa 2c: treina também com os itens reservados (controle); padrão: deixá-los de fora")
    ap.add_argument("--prever-teste", action="store_true", help="também prevê o período de teste (uso único, RN25)")
    ap.add_argument("--apenas-prever-teste", action="store_true",
                    help="não treina: carrega modelos/<nome>/modelo.keras e prevê o período de teste (uso único, RN25)")
    args = ap.parse_args(argv)

    import keras
    import tensorflow as tf

    keras.utils.set_random_seed(args.semente)
    dados = DadosPreparados(args.pasta)
    calendario = (CalendarioFuturo.carregar(args.calendario_futuro, args.pasta, dados.horizonte)
                  if args.calendario_futuro else None)
    if args.apenas_prever_teste:
        if not args.nome:
            ap.error("--apenas-prever-teste exige --nome do modelo já treinado")
        destino = args.pasta / "modelos" / args.nome
        modelo = keras.models.load_model(destino / "modelo.keras", compile=False)
        ids_t, yhat_t = prever(modelo, dados, dados.janelas("teste"), calendario=calendario)
        salvar_previsoes(ids_t, yhat_t, destino / "previsoes_teste.parquet")
        info_p = destino / "treino.json"
        info = json.loads(info_p.read_text(encoding="utf-8"))
        info["previu_teste"] = True
        info_p.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Previsões do teste em {destino / 'previsoes_teste.parquet'}. Avalie com:\n  python avaliar.py --pasta "
              f"{args.pasta} --periodo teste --previsoes {destino / 'previsoes_teste.parquet'} --rotulo {args.nome}")
        return 0
    nome = args.nome or "lstm_" + datetime.now().strftime("%Y%m%d_%H%M")
    destino = args.pasta / "modelos" / nome
    if destino.exists():
        ap.error(f"{destino} já existe; escolha outro --nome")
    destino.mkdir(parents=True)

    jan_tr = dados.janelas("treino")
    jan_va = dados.janelas("validacao")
    jan_tr, va_base, reserva = separar_reservados(jan_tr, jan_va, args.incluir_reservados)
    va_es = va_base if not args.amostras_validacao or len(va_base) <= args.amostras_validacao else \
        va_base.sample(args.amostras_validacao, random_state=args.semente).sort_values("id_amostra")
    print(f"amostras: treino {len(jan_tr):,} (por época: {args.amostras_por_epoca or len(jan_tr):,}) | "
          f"validação {len(jan_va):,} (parada antecipada com {len(va_es):,})")
    if reserva:
        print(f"etapa 2c: {reserva['itens_reservados']:,} itens reservados "
              f"{'INCLUÍDOS no treino (controle)' if reserva['incluidos_no_treino'] else 'FORA do treino'}")

    modelo = construir_modelo(dados, args.unidades, args.dropout, args.taxa, args.perda, args.ativacao,
                              (dados.horizonte, len(COLUNAS_FUTURAS)) if calendario is not None else None)
    modelo.summary(print_fn=lambda s, **_: print(s))
    callbacks = []
    if args.reduzir_taxa:  # antes do CSVLogger, para a taxa de cada época ir para o historico.csv
        callbacks.append(keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=args.fator_taxa,
                                                           patience=args.paciencia_taxa, min_lr=args.taxa_minima))
    callbacks += [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=args.paciencia, restore_best_weights=True),
        keras.callbacks.CSVLogger(str(destino / "historico.csv")),
        keras.callbacks.TerminateOnNaN(),
    ]
    inicio = time.time()
    hist = modelo.fit(
        criar_lotes(dados, jan_tr, args.lote, args.amostras_por_epoca, True, args.semente, args.mascara, calendario),
        validation_data=criar_lotes(dados, va_es, args.lote, 0, False, args.semente, args.mascara, calendario),
        epochs=args.epocas, callbacks=callbacks, verbose=2)
    duracao = time.time() - inicio
    val = hist.history.get("val_loss", [])
    melhor = int(np.argmin(val)) + 1 if val else None

    modelo.save(destino / "modelo.keras")
    shutil.copy(args.pasta / "normalizacao.json", destino / "normalizacao.json")
    ids, yhat = prever(modelo, dados, jan_va, calendario=calendario)
    salvar_previsoes(ids, yhat, destino / "previsoes_validacao.parquet")
    if args.prever_teste:
        ids_t, yhat_t = prever(modelo, dados, dados.janelas("teste"), calendario=calendario)
        salvar_previsoes(ids_t, yhat_t, destino / "previsoes_teste.parquet")

    info: dict[str, Any] = {
        "nome": nome,
        "treinado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parametros": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "epocas_executadas": len(val),
        "melhor_epoca": melhor,
        "melhor_val_loss": float(min(val)) if val else None,
        "duracao_segundos": round(duracao, 1),
        "segundos_por_epoca": round(duracao / max(len(val), 1), 1),
        "amostras": {"treino": len(jan_tr), "validacao": len(jan_va), "validacao_parada_antecipada": len(va_es)},
        "reserva": reserva,
        "versoes": {"tensorflow": tf.__version__, "keras": keras.__version__},
        "taxa_final": float(keras.ops.convert_to_numpy(modelo.optimizer.learning_rate)),
        "previu_teste": bool(args.prever_teste),
        "mascara": bool(args.mascara),
        "variaveis_sequencia": len(dados.var_seq),
        # Etapa 2h: o calendário dos dias previstos (X_fut), ou None.
        "calendario_futuro": None if calendario is None else {
            "arquivo": str(args.calendario_futuro), "assinatura": calendario.assinatura,
            "formato": [calendario.horizonte, len(COLUNAS_FUTURAS)], "colunas": list(COLUNAS_FUTURAS)},
    }
    (destino / "treino.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: info[k] for k in ("epocas_executadas", "melhor_epoca", "melhor_val_loss", "segundos_por_epoca",
                                           "taxa_final")},
                     ensure_ascii=False))
    print(f"\nModelo em {destino}. Próximo passo:\n  python avaliar.py --pasta {args.pasta} --periodo validacao "
          f"--previsoes {destino / 'previsoes_validacao.parquet'} --rotulo {nome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
