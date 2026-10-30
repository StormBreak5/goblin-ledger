"""Apoio aos testes do CU11 (C1 e C2): o cenário sintético, os treinadores falsos e a execução pela fila.

Importado só depois do `pytest.importorskip` de pandas e TensorFlow, nos módulos de teste.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from sinteticos import gerar
from src.ml.configuracao import PADROES_DAS_VERSOES_ANTIGAS, ConfigModelo
from src.ml.dataset import DadosPreparados
from src.ml.rede import ResultadoDoTreino, TreinadorKeras
from src.ml.retreinamento import Retreinamento
from src.ml.treinamento_inicial import TreinamentoInicial
from src.models.modelo import ModeloPreditivo, ProjecaoItem
from src.services.treinamento_service import ResumoDoTreinamento, TreinamentoService

CFG = ConfigModelo(unidades=4, epocas_max=1, paciencia=1, lote=64, amostras_por_epoca=256, amostras_validacao=256)
# Uma versão de antes das etapas 2g e 2i do estudo: ReLU e o código da subclasse sozinho (como a v1 do banco real).
CFG_ANTIGA = replace(CFG, **PADROES_DAS_VERSOES_ANTIGAS)
FIM = "2026-10-05"
FORA_DO_TREINO = 200_003  # elegível, mas não apto ao treinamento (RN15)


def cenario(*extras: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """6 itens sintéticos de 2024-01-01 a 2026-10-05, todos líquidos (RN02); o 200003 não é apto (RN15)."""
    dados = gerar(n_itens=6, inicio="2024-01-01", fim=FIM, semente=5)
    dados["precos"]["quantidade"] = dados["precos"]["quantidade"].clip(lower=100)
    if extras:
        dados["precos"] = pd.concat([dados["precos"], *extras], ignore_index=True)
    return dados


def aptos_do(dados: dict[str, pd.DataFrame]) -> set[int]:
    return set(dados["precos"]["item_id"].astype(int)) - {FORA_DO_TREINO}


class TreinadorFalso:
    """Sem rede: o "modelo" é o modo de previsão de cada item ("perfeita", "ingenua" ou "ruim", 50% acima do preço).
    `salvar` grava o modo no artefato e `carregar` o lê de volta, para o C2 avaliar a versão vigente como ela era."""

    def __init__(self, modos: Optional[dict[int, str]] = None, padrao: str = "perfeita",
                 erro: Optional[BaseException] = None) -> None:
        self.modos = modos or {}
        self.padrao = padrao
        self.erro = erro
        self.itens_do_treino: set[int] = set()
        self.treinou = False
        self.previsoes: list[dict[str, Any]] = []  # normalização e amostras de cada chamada a `prever`

    def treinar(self, dados: DadosPreparados, jan_treino: pd.DataFrame, jan_validacao: pd.DataFrame,
                cfg: ConfigModelo, ao_fim_da_epoca: Any = None) -> ResultadoDoTreino:
        self.treinou = True
        if self.erro is not None:
            raise self.erro
        self.itens_do_treino = set(jan_treino["item_id"]) | set(jan_validacao["item_id"])
        if ao_fim_da_epoca is not None:
            ao_fim_da_epoca(1, cfg.epocas_max, 0.5)
        modelo = {"padrao": self.padrao, "modos": {str(k): v for k, v in self.modos.items()}}
        return ResultadoDoTreino(modelo=modelo, epocas=1, melhor_epoca=1, melhor_val_loss=0.5, duracao_segundos=0.1,
                                 segundos_por_epoca=0.1, amostras_treino=len(jan_treino),
                                 amostras_validacao=len(jan_validacao), amostras_parada_antecipada=len(jan_validacao))

    def prever(self, modelo: Any, dados: DadosPreparados, jan: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        self.previsoes.append({"normalizacao": dados.normalizacao, "janelas": jan[["id_amostra", "serie", "item_id",
                                                                                  "data_origem"]].copy()})
        alvo = dados.normalizacao["alvo"]
        media, desvio = np.asarray(alvo["media"]), np.asarray(alvo["desvio"])
        yhat = jan[dados.colunas_alvo()].to_numpy("float64")
        modos = jan["item_id"].map(lambda i: modelo["modos"].get(str(int(i)), modelo["padrao"])).to_numpy()
        yhat[modos == "ingenua"] = (0.0 - media) / desvio
        yhat[modos == "ruim"] = (np.log(1.5) - media) / desvio
        return jan["id_amostra"].to_numpy(), yhat

    def salvar(self, modelo: Any, caminho: Path) -> None:
        caminho.write_text(json.dumps(modelo), encoding="utf-8")

    def carregar(self, caminho: Path) -> Any:
        return json.loads(caminho.read_text(encoding="utf-8"))


class TreinadorKerasComPrevisaoPerfeita(TreinadorKeras):
    """Treina a LSTM de verdade e grava o modelo.keras, mas a avaliação usa o próprio alvo, para o teste saber quais
    itens são liberados (a rede mínima de 1 época não atinge a RN10)."""

    def __init__(self) -> None:
        self.itens_do_treino: set[int] = set()

    def treinar(self, dados, jan_treino, jan_validacao, cfg, ao_fim_da_epoca=None):  # type: ignore[no-untyped-def]
        self.itens_do_treino = set(jan_treino["item_id"]) | set(jan_validacao["item_id"])
        return super().treinar(dados, jan_treino, jan_validacao, cfg, ao_fim_da_epoca)

    def prever(self, modelo, dados, jan):  # type: ignore[no-untyped-def]
        self.previsao_real = super().prever(modelo, dados, jan)
        return jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64")


def executar(pg_engine, db_session, relogio, pasta: Path, treinador: Any,
             cfg: ConfigModelo = CFG) -> ResumoDoTreinamento:
    """CU11-C1: o pedido do Admin entra na fila e o serviço `modelo` o executa."""
    servico = TreinamentoService(db_session, relogio)
    id_execucao = servico.registrar_pedido("US")
    assert servico.pegar_proximo() == id_execucao
    TreinamentoInicial(pg_engine, cfg, pasta, treinador, relogio).executar(id_execucao)
    db_session.expire_all()
    return servico.resumo(id_execucao)


def retreinar(pg_engine, db_session, relogio, pasta: Path, treinador: Any,
              cfg: ConfigModelo = CFG) -> ResumoDoTreinamento:
    """CU11-C2: o agendador registra o retreinamento da região e o serviço `modelo` o executa."""
    servico = TreinamentoService(db_session, relogio)
    [registro] = servico.registrar_retreinamentos(["US"])
    assert registro.id_execucao is not None and servico.pegar_proximo() == registro.id_execucao
    Retreinamento(pg_engine, cfg, pasta, treinador, relogio).executar(registro.id_execucao)
    db_session.expire_all()
    return servico.resumo(registro.id_execucao)


def como_versao_antiga(db_session, versao: int) -> None:
    """Tira do normalizacao.json e do treino.json da versão os campos que as versões treinadas antes das etapas 2g e 2i
    não gravavam (a ativação e a subclasse pelo par), deixando os artefatos como os da v1 do banco real."""
    pasta = Path(db_session.get(ModeloPreditivo, versao).caminho_artefatos)
    for arquivo, chave in (("normalizacao.json", "config"), ("treino.json", "parametros")):
        caminho = pasta / arquivo
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
        for campo in PADROES_DAS_VERSOES_ANTIGAS:
            del conteudo[chave][campo]
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def ativacao_da_rede(caminho: Path) -> str:
    """A ativação da camada densa de 32 gravada no modelo.keras de uma versão."""
    import keras

    rede = keras.models.load_model(caminho / "modelo.keras", compile=False)
    [densa] = [c for c in rede.layers if isinstance(c, keras.layers.Dense) and c.units == 32]
    return str(densa.get_config()["activation"])


def projecoes(db_session) -> dict[int, ProjecaoItem]:
    return {p.item_id: p for p in db_session.query(ProjecaoItem)}


def pastas(pasta: Path) -> set[str]:
    return {p.name for p in pasta.iterdir()} if pasta.exists() else set()
