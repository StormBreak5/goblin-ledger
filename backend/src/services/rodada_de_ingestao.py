import logging
from datetime import datetime
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from src.models.mercado import ORIGEM_AGENDADO
from src.repositories.mercado_repository import MercadoRepository
from src.services import security
from src.services.agendamento import planejar, proximo_disparo
from src.services.api_client import BlizzardApiClient
from src.services.ingestao_config import Mercado
from src.services.ingestao_service import IngestaoService

logger = logging.getLogger(__name__)


def executar_rodada(
    session: Session,
    cliente: BlizzardApiClient,
    mercados: Sequence[Mercado],
    recuperar_com_backfill: Callable[[], None],
    relogio: Callable[[], datetime] = security.agora,
    preencher_itens_novos: Callable[[], None] = lambda: None,
) -> datetime:
    """
    Uma rodada do agendador (ao iniciar o worker e a cada disparo): decide pelo `planejar` se é preciso recompor o
    histórico pelo backfill (mais de 48 h desde a última coleta) e quais endpoints já podem ser coletados (RN05),
    executa e devolve quando o worker deve rodar de novo. Um endpoint que falha não impede os demais (RN14).
    Se algum ciclo cadastrou itens novos (C3-FA1), `preencher_itens_novos` completa o nome e o ícone deles.
    """
    repository = MercadoRepository(session)
    chaves = [mercado.chave for mercado in mercados]
    agora = relogio()
    plano = planejar(
        agora, repository.ultima_coleta(), repository.ultimas_requisicoes(chaves), repository.ultimo_backfill_iniciado()
    )

    if plano.recuperar_com_backfill:
        logger.warning("Mais de 48 h desde a última coleta: recompondo o histórico pelo backfill antes do ciclo.")
        try:
            recuperar_com_backfill()
        except Exception:
            logger.exception("A recuperação pelo backfill falhou; o ciclo da Blizzard segue mesmo assim.")

    servico = IngestaoService(session, cliente, relogio)
    itens_novos = 0
    for mercado in mercados:
        if mercado.chave not in plano.mercados_a_coletar:
            logger.info("CU09-C1: %s ainda não pode ser consultado (RN05); fica para o próximo ciclo.", mercado.chave)
            continue
        try:
            itens_novos += servico.executar(mercado, ORIGEM_AGENDADO).itens_cadastrados
        except Exception:
            session.rollback()
            logger.exception("CU09: erro inesperado no ciclo de %s.", mercado.chave)

    if itens_novos:
        try:
            preencher_itens_novos()
        except Exception:
            logger.exception("Não foi possível preencher o nome e o ícone dos itens novos; fica para a sincronização diária.")

    return proximo_disparo(relogio(), repository.ultimas_requisicoes(chaves))
