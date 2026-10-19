"""Serviço `modelo` (CU11): consome a fila de treinamentos e agenda o retreinamento semanal.

- A API registra o pedido do Admin (CU11-C1 passo 1); o agendador deste serviço registra o retreinamento (CU11-C2
  passo 1, `MODELO_RETREINO_CRON`). Este serviço, que tem pandas e TensorFlow, retira as execuções da fila, uma por vez:
  `INICIAL` → src/ml/treinamento_inicial.py; `RETREINAMENTO` → src/ml/retreinamento.py.
- A consolidação diária (C3) entra aqui no próximo pedido.

Uso (dentro do container):
    python -m src.modelo_worker                          # o serviço: fila + agendador
    python -m src.modelo_worker --retreinar US           # CU11-C2 passo 1 pelo mesmo caminho do agendador
    python -m src.modelo_worker --retreinar --aguardar   # todas as regiões com modelo vigente; espera o fim
"""
import argparse
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Sequence

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import SQLAlchemyError

from src.ml.artefatos import pasta_dos_modelos
from src.ml.configuracao import ConfigModelo
from src.ml.retreinamento import Retreinamento
from src.ml.treinamento_inicial import TreinamentoInicial, preencher_liberados_sem_amostra_de_treino
from src.models.modelo import (ETAPA_INTERNA, STATUS_EM_ANDAMENTO, STATUS_FALHA, TIPO_INICIAL, TIPO_RETREINAMENTO,
                               ExecucaoTreinamento)
from src.repositories.database import init_db
from src.services.agendamento import ultimo_disparo
from src.services.security import agora
from src.services.treinamento_service import RegistroDoRetreinamento, TreinamentoService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("modelo_worker")

RETREINO_JOB_ID = "retreinamento_job"
# CU11-C2 passo 1: depois do reinício semanal dos EUA (terça-feira). Use o nome do dia: no APScheduler 3, o dia da
# semana em número começa na segunda (0), diferente do crontab ("2" seria quarta-feira).
HORARIO_PADRAO_DO_RETREINO = "0 18 * * tue"


def intervalo_da_fila() -> float:
    """MODELO_INTERVALO_FILA_SEGUNDOS: de quanto em quanto tempo a fila é consultada (padrão: 10 s)."""
    return float(os.getenv("MODELO_INTERVALO_FILA_SEGUNDOS", "").strip() or "10")


def registrar_retreinamentos(SessionLocal: Callable[[], Any],
                             regioes: Optional[Sequence[str]] = None) -> list[RegistroDoRetreinamento]:
    """CU11-C2 passo 1, o caminho do agendador (e do comando `--retreinar`, que o C3-FA4 também usa)."""
    with SessionLocal() as sessao:
        return TreinamentoService(sessao).registrar_retreinamentos(regioes)


def gatilho_do_retreino() -> Optional[CronTrigger]:
    """O cron de MODELO_RETREINO_CRON, em UTC; None se desligado ("off")."""
    expressao = os.getenv("MODELO_RETREINO_CRON", "").strip() or HORARIO_PADRAO_DO_RETREINO
    return None if expressao.lower() == "off" else CronTrigger.from_crontab(expressao, timezone=timezone.utc)


def registrar_retreinamentos_perdidos(SessionLocal: Callable[[], Any],
                                      agora: Optional[datetime] = None) -> list[RegistroDoRetreinamento]:
    """Ao iniciar: o retreinamento do último disparo do cron que não rodou porque o serviço estava desligado no horário
    é registrado agora, uma vez (o APScheduler não guarda o disparo perdido)."""
    gatilho = gatilho_do_retreino()
    anterior = None if gatilho is None else ultimo_disparo(gatilho, agora or datetime.now(timezone.utc))
    if anterior is None:
        return []
    with SessionLocal() as sessao:
        return TreinamentoService(sessao).registrar_retreinamentos_perdidos(anterior)


def agendar_retreinamento(agendador: Any, SessionLocal: Callable[[], Any]) -> bool:
    """Agenda o retreinamento semanal pelo cron de MODELO_RETREINO_CRON, em UTC. Devolve False se desligado ("off").
    Com o computador dormindo no horário, o disparo atrasado roda ao acordar, uma vez só (coalesce, sem limite de
    atraso); desligado, quem o recupera é `registrar_retreinamentos_perdidos`, ao iniciar."""
    gatilho = gatilho_do_retreino()
    if gatilho is None:
        logger.info("Retreinamento agendado desligado (MODELO_RETREINO_CRON=off).")
        return False
    expressao = os.getenv("MODELO_RETREINO_CRON", "").strip() or HORARIO_PADRAO_DO_RETREINO

    def disparar() -> None:
        try:
            registrar_retreinamentos(SessionLocal)
        except Exception:
            logger.exception("CU11-C2: não foi possível registrar o retreinamento agendado.")

    agendador.add_job(disparar, gatilho, id=RETREINO_JOB_ID, replace_existing=True, coalesce=True,
                      misfire_grace_time=None)
    logger.info("Retreinamento agendado (%s, UTC).", expressao)
    return True


def atender_um(SessionLocal: Callable[[], Any], treinamentos: dict[str, TreinamentoInicial]) -> bool:
    """Retira um pedido da fila e o executa conforme o tipo. Devolve False se não havia nada a fazer."""
    with SessionLocal() as sessao:
        id_execucao = TreinamentoService(sessao).pegar_proximo()
        tipo = None if id_execucao is None else sessao.get(ExecucaoTreinamento, id_execucao).tipo
    if id_execucao is None:
        return False
    treinamento = treinamentos.get(tipo or "")
    if treinamento is None:
        with SessionLocal() as sessao:
            execucao = sessao.get(ExecucaoTreinamento, id_execucao)
            execucao.status, execucao.etapa_da_falha, execucao.concluido_em = STATUS_FALHA, ETAPA_INTERNA, agora()
            execucao.erro = f"Tipo de treinamento não suportado por este serviço: {tipo}."
            sessao.commit()
        return True
    logger.info("%s: iniciando a execução %s.", treinamento.rotulo, id_execucao)
    treinamento.executar(id_execucao)
    return True


def aguardar(SessionLocal: Callable[[], Any], ids: Sequence[int], intervalo: float = 15.0) -> None:
    """Espera as execuções terminarem e mostra o resumo de cada uma (comando `--aguardar`)."""
    pendentes = set(ids)
    while pendentes:
        with SessionLocal() as sessao:
            servico = TreinamentoService(sessao)
            for id_execucao in sorted(pendentes):
                resumo = servico.resumo(id_execucao)
                if resumo.status not in STATUS_EM_ANDAMENTO:
                    print(resumo, flush=True)
                    pendentes.discard(id_execucao)
                else:
                    logger.info("Execução %s: %s.", id_execucao, resumo.andamento)
        if pendentes:
            time.sleep(intervalo)


def servico(SessionLocal: Callable[[], Any], cfg: ConfigModelo) -> None:
    """O serviço `modelo`: o agendador do retreinamento e a fila de execuções."""
    pasta = pasta_dos_modelos()
    pasta.mkdir(parents=True, exist_ok=True)
    engine = SessionLocal.kw["bind"]
    treinamentos: dict[str, TreinamentoInicial] = {
        TIPO_INICIAL: TreinamentoInicial(engine, cfg, pasta),
        TIPO_RETREINAMENTO: Retreinamento(engine, cfg, pasta),
    }
    with SessionLocal() as sessao:
        interrompidos = TreinamentoService(sessao).encerrar_em_execucao()
    if interrompidos:
        logger.warning("CU11: %d treinamento(s) interrompido(s) pelo reinício do serviço.", interrompidos)
    preencher_liberados_sem_amostra_de_treino(engine)
    agendador = BackgroundScheduler(timezone=timezone.utc)
    agendar_retreinamento(agendador, SessionLocal)
    agendador.start()
    try:
        registrar_retreinamentos_perdidos(SessionLocal)
    except Exception:
        logger.exception("CU11-C2: não foi possível conferir se o retreinamento agendado foi perdido.")
    logger.info("Serviço modelo pronto: fila a cada %.0f s, artefatos em %s, RN07 %s.", intervalo_da_fila(),
                pasta.resolve(), "desligada" if cfg.ilvl_minimo is None else f"com nível mínimo {cfg.ilvl_minimo}")
    while True:
        try:
            if atender_um(SessionLocal, treinamentos):
                continue
        except SQLAlchemyError:
            logger.warning("Serviço modelo: banco indisponível ao consultar a fila.", exc_info=True)
        time.sleep(intervalo_da_fila())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Serviço modelo do Goblin Ledger (CU11).")
    parser.add_argument("--retreinar", nargs="*", metavar="REGIAO",
                        help="registra o retreinamento (CU11-C2) da região, pelo mesmo caminho do agendador; sem "
                             "região, de todas as que têm modelo vigente")
    parser.add_argument("--aguardar", action="store_true", help="com --retreinar: espera o fim e mostra o resumo")
    args = parser.parse_args(argv)
    cfg = ConfigModelo.do_ambiente()
    SessionLocal = init_db()  # aplica as migrações (com a trava do Alembic, como a API e o worker)
    if args.retreinar is None:
        servico(SessionLocal, cfg)
        return 0
    registros = registrar_retreinamentos(SessionLocal, args.retreinar or None)
    for registro in registros:
        print(f"{registro.regiao}: " + (f"retreinamento {registro.id_execucao} registrado na fila"
                                        if registro.id_execucao is not None else f"não registrado ({registro.motivo})"),
              flush=True)
    if args.aguardar:
        aguardar(SessionLocal, [r.id_execucao for r in registros if r.id_execucao is not None])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
