import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.mercado import (
    CICLO_FALHA,
    CICLO_SUCESSO,
    ORIGEM_AGENDADO,
    ORIGEM_BLIZZARD,
    CicloIngestao,
)
from src.repositories.mercado_repository import MercadoRepository
from src.scraper.models import GRANULARIDADE_HORARIA
from src.services import ingestao_config, security
from src.services.api_client import ApiIndisponivelError, BlizzardApiClient, PayloadDeLeiloes
from src.services.ingestao_config import Mercado
from src.services.sanitizacao import PayloadForaDoFormatoError, ResultadoSanitizacao, sanitizar
from src.services.valor_de_mercado import primeiro_quartil_ponderado, volume_e_anomalo

logger = logging.getLogger(__name__)

STATUS_CANCELADO = "CANCELADO"  # CU09-C1-FA1: intervalo mínimo não atingido (nenhum ciclo é registrado)

ETAPA_COLETA = "COLETA"
ETAPA_SANITIZACAO = "SANITIZACAO"
ETAPA_CONSOLIDACAO = "CONSOLIDACAO"


@dataclass
class ResultadoCiclo:
    """Resumo de um ciclo de ingestão (mostrado ao Admin no CU09-C4)."""
    endpoint: str
    status: str  # SUCESSO, FALHA ou CANCELADO
    proxima_permitida: Optional[datetime] = None
    leiloes_coletados: int = 0
    leiloes_descartados: int = 0
    itens_atualizados: int = 0
    itens_anomalos: int = 0
    itens_cadastrados: int = 0
    etapa_da_falha: Optional[str] = None
    erro: Optional[str] = None


class IngestaoService:
    """CU09 – Cadastrar Dados de Mercado (RF07 / RF10): coleta (C1), sanitização (C2) e consolidação (C3) dos
    leilões de um mercado da Blizzard."""

    def __init__(
        self,
        session: Session,
        cliente: BlizzardApiClient,
        relogio: Callable[[], datetime] = security.agora,
    ):
        self.session = session
        self.cliente = cliente
        self.relogio = relogio
        self.repository = MercadoRepository(session)

    def executar(self, mercado: Mercado, origem: str = ORIGEM_AGENDADO) -> ResultadoCiclo:
        """Executa o ciclo completo de um endpoint. Falhas previstas viram resultado FALHA (com a etapa e o erro) e a
        sinalização "Dados Desatualizados" (RN14); o intervalo mínimo não atingido vira CANCELADO (C1-FA1)."""
        agora = self.relogio()
        self.repository.garantir_mercados([mercado])
        self.session.commit()

        ciclo, proxima = self.repository.iniciar_ciclo(mercado.chave, origem, agora, ingestao_config.INTERVALO_MINIMO)
        if ciclo is None:
            logger.info("CU09-C1-FA1: %s foi consultado há menos de 60 min; próxima coleta a partir de %s.", mercado.chave, proxima)
            return ResultadoCiclo(mercado.chave, STATUS_CANCELADO, proxima_permitida=proxima)
        id_ciclo = ciclo.id

        try:
            coletado = self._coletar(mercado)
        except ApiIndisponivelError as e:
            return self._falhar(id_ciclo, mercado, ETAPA_COLETA, e)
        except PayloadForaDoFormatoError as e:  # resposta que não é JSON
            return self._falhar(id_ciclo, mercado, ETAPA_SANITIZACAO, e)

        try:
            sanitizado = sanitizar(coletado.payload, mercado.tipo)
        except PayloadForaDoFormatoError as e:
            return self._falhar(id_ciclo, mercado, ETAPA_SANITIZACAO, e)
        coletado.payload = None  # o payload bruto pode ter centenas de MB: libera antes de consolidar

        if sanitizado.taxa_de_descarte > ingestao_config.LIMITE_DE_DESCARTE:
            logger.warning(
                "CU09-C2-FA1: %s descartou %d de %d registros (%.1f%%, limite %.1f%%); lote registrado para auditoria.",
                mercado.chave, sanitizado.descartados, sanitizado.total,
                sanitizado.taxa_de_descarte * 100, ingestao_config.LIMITE_DE_DESCARTE * 100,
            )

        try:
            return self._consolidar(id_ciclo, mercado, sanitizado, coletado.last_modified, agora)
        except SQLAlchemyError as e:
            self.session.rollback()
            return self._falhar(id_ciclo, mercado, ETAPA_CONSOLIDACAO, e)

    # ------------------------------------------------------------------ C1: coletar

    def _coletar(self, mercado: Mercado) -> PayloadDeLeiloes:
        if mercado.tipo == ingestao_config.TIPO_COMMODITIES:
            return self.cliente.fetch_commodity_auctions(mercado.regiao)
        return self.cliente.fetch_connected_realm_auctions(mercado.regiao, mercado.id_reino)

    # ------------------------------------------------------------------ C3: consolidar

    def _consolidar(
        self,
        id_ciclo: int,
        mercado: Mercado,
        sanitizado: ResultadoSanitizacao,
        last_modified: Optional[datetime],
        agora: datetime,
    ) -> ResultadoCiclo:
        """CU09-C3 passos 1 a 6 numa única transação: se qualquer passo falhar, nada é gravado (FE1)."""
        referencia = (last_modified or agora).astimezone(timezone.utc)
        referencia_sem_fuso = referencia.replace(tzinfo=None)  # historical_item_prices guarda UTC sem fuso
        regiao_do_historico = str(mercado.id_reino)
        leiloes = sanitizado.leiloes

        # Passo 1 e FA1: identifica os itens; os que não existem são cadastrados.
        ids_do_ciclo = {leilao.item_id for leilao in leiloes}
        novos = ids_do_ciclo - self.repository.itens_cadastrados(ids_do_ciclo)
        if novos:
            self.repository.cadastrar_itens(novos)

        # Passos 2 e 3: registra os leilões ativos do ciclo e classifica os sem atualização há mais de 48 h (RN04).
        self.repository.registrar_leiloes(mercado.id_reino, leiloes, referencia)
        self.repository.classificar_expirados(agora - ingestao_config.PRAZO_DO_LEILAO)

        # Passo 4: valor de mercado de cada item (RN06) e volume do ciclo.
        ofertas: dict[int, list[tuple[int, int]]] = {}
        volumes: dict[int, int] = {}
        for leilao in leiloes:
            volumes[leilao.item_id] = volumes.get(leilao.item_id, 0) + leilao.quantidade
            if leilao.preco_unitario is not None:
                ofertas.setdefault(leilao.item_id, []).append((leilao.preco_unitario, leilao.quantidade))

        estatisticas = self.repository.estatisticas_de_volume(
            regiao_do_historico, (agora - ingestao_config.ANOMALIA_JANELA).replace(tzinfo=None)
        )
        pontos = []
        anomalos = 0
        for item_id, oferta in ofertas.items():
            valor = primeiro_quartil_ponderado(oferta)
            if valor is None:
                continue
            mediana, quantidade_de_pontos = estatisticas.get(item_id, (None, 0))
            anomalo = volume_e_anomalo(volumes[item_id], mediana, quantidade_de_pontos)  # C2 passo 4 (RN12)
            anomalos += anomalo
            # CU10 (RN16): o ponto do ciclo é horário; sem a coluna no INSERT ele herdaria o padrão "DIARIA".
            pontos.append((
                item_id, regiao_do_historico, referencia_sem_fuso, valor, volumes[item_id], ORIGEM_BLIZZARD, anomalo,
                GRANULARIDADE_HORARIA,
            ))
        self.repository.registrar_pontos_de_historico(pontos)

        # Passos 5 e 6: data e hora da última atualização do mercado (RN09) e conclusão do ciclo.
        self.repository.registrar_atualizacao(mercado.chave, referencia)
        ciclo = self.session.get(CicloIngestao, id_ciclo)
        ciclo.status = CICLO_SUCESSO
        ciclo.concluido_em = self.relogio()
        ciclo.data_referencia = referencia
        ciclo.leiloes_coletados = len(leiloes)
        ciclo.leiloes_descartados = sanitizado.descartados
        ciclo.itens_atualizados = len(pontos)
        ciclo.itens_anomalos = anomalos
        self.session.commit()

        self._remover_expirados_antigos(agora)
        logger.info(
            "CU09: ciclo de %s concluído: %d leilões (%d descartados), %d itens atualizados, %d anomalias, %d itens cadastrados.",
            mercado.chave, len(leiloes), sanitizado.descartados, len(pontos), anomalos, len(novos),
        )
        return ResultadoCiclo(
            mercado.chave, CICLO_SUCESSO,
            leiloes_coletados=len(leiloes), leiloes_descartados=sanitizado.descartados,
            itens_atualizados=len(pontos), itens_anomalos=anomalos, itens_cadastrados=len(novos),
        )

    def _remover_expirados_antigos(self, agora: datetime) -> None:
        """Retenção dos leilões brutos já classificados (o resumo horário permanece). Falha aqui não invalida o ciclo."""
        try:
            removidos = self.repository.remover_expirados_antigos(agora - ingestao_config.RETENCAO_DE_LEILOES)
            self.session.commit()
            if removidos:
                logger.info("CU09: %d leilões Expirado/Vendido além da retenção foram removidos.", removidos)
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception("CU09: não foi possível aplicar a retenção dos leilões antigos.")

    # ------------------------------------------------------------------ falhas (FE1 dos três cenários)

    def _falhar(self, id_ciclo: int, mercado: Mercado, etapa: str, erro: Exception) -> ResultadoCiclo:
        """Isola a falha: registra a etapa e o erro, mantém os dados do ciclo anterior (nada foi alterado) e ativa
        "Dados Desatualizados" para o mercado (RN14)."""
        logger.error("CU09: falha na etapa %s do ciclo de %s: %s", etapa, mercado.chave, erro)
        agora = self.relogio()
        try:
            self.session.rollback()
            ciclo = self.session.get(CicloIngestao, id_ciclo)
            ciclo.status = CICLO_FALHA
            ciclo.concluido_em = agora
            ciclo.etapa_da_falha = etapa
            ciclo.erro = str(erro)[:2000]
            self.repository.sinalizar_desatualizado(mercado.chave, agora)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception("CU09: não foi possível registrar a falha do ciclo de %s.", mercado.chave)
        return ResultadoCiclo(mercado.chave, CICLO_FALHA, etapa_da_falha=etapa, erro=str(erro))
