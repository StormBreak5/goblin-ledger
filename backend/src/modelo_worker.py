"""Serviço `modelo` (CU11): consome a fila de treinamentos registrada pela API e executa um por vez.

A API registra o pedido do Admin em `execucao_treinamento` (CU11-C1 passo 1); este serviço, que tem pandas e
TensorFlow, o retira da fila e executa os passos 2 a 12 (src/ml/treinamento_inicial.py). O agendamento do
retreinamento (C2) e da consolidação diária (C3) entra aqui nos próximos pedidos.

Uso (dentro do container): python -m src.modelo_worker
"""
import logging
import os
import time

from sqlalchemy.exc import SQLAlchemyError

from src.ml.artefatos import pasta_dos_modelos
from src.ml.configuracao import ConfigModelo
from src.ml.treinamento_inicial import TreinamentoInicial, preencher_liberados_sem_amostra_de_treino
from src.models.modelo import ETAPA_INTERNA, STATUS_FALHA, TIPO_INICIAL, ExecucaoTreinamento
from src.repositories.database import init_db
from src.services.security import agora
from src.services.treinamento_service import TreinamentoService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("modelo_worker")


def intervalo_da_fila() -> float:
    """MODELO_INTERVALO_FILA_SEGUNDOS: de quanto em quanto tempo a fila é consultada (padrão: 10 s)."""
    return float(os.getenv("MODELO_INTERVALO_FILA_SEGUNDOS", "").strip() or "10")


def atender_um(SessionLocal, treinamento: TreinamentoInicial) -> bool:  # type: ignore[no-untyped-def]
    """Retira um pedido da fila e o executa. Devolve False se não havia nada a fazer."""
    with SessionLocal() as sessao:
        id_execucao = TreinamentoService(sessao).pegar_proximo()
        tipo = None if id_execucao is None else sessao.get(ExecucaoTreinamento, id_execucao).tipo
    if id_execucao is None:
        return False
    if tipo != TIPO_INICIAL:  # o retreinamento (C2) ainda não foi implementado
        with SessionLocal() as sessao:
            execucao = sessao.get(ExecucaoTreinamento, id_execucao)
            execucao.status, execucao.etapa_da_falha, execucao.concluido_em = STATUS_FALHA, ETAPA_INTERNA, agora()
            execucao.erro = f"Tipo de treinamento não suportado por este serviço: {tipo}."
            sessao.commit()
        return True
    logger.info("CU11-C1: iniciando o treinamento %s.", id_execucao)
    treinamento.executar(id_execucao)
    return True


def main() -> None:
    cfg = ConfigModelo.do_ambiente()
    pasta = pasta_dos_modelos()
    pasta.mkdir(parents=True, exist_ok=True)
    SessionLocal = init_db()  # aplica as migrações (com a trava do Alembic, como a API e o worker)
    treinamento = TreinamentoInicial(SessionLocal.kw["bind"], cfg, pasta)
    with SessionLocal() as sessao:
        interrompidos = TreinamentoService(sessao).encerrar_em_execucao()
    if interrompidos:
        logger.warning("CU11: %d treinamento(s) interrompido(s) pelo reinício do serviço.", interrompidos)
    preencher_liberados_sem_amostra_de_treino(SessionLocal.kw["bind"])
    logger.info("Serviço modelo pronto: fila a cada %.0f s, artefatos em %s, RN07 %s.", intervalo_da_fila(),
                pasta.resolve(), "desligada" if cfg.ilvl_minimo is None else f"com nível mínimo {cfg.ilvl_minimo}")
    while True:
        try:
            if atender_um(SessionLocal, treinamento):
                continue
        except SQLAlchemyError:
            logger.warning("Serviço modelo: banco indisponível ao consultar a fila.", exc_info=True)
        time.sleep(intervalo_da_fila())


if __name__ == "__main__":
    main()
