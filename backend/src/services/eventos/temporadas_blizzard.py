import logging
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from src.models.evento import ORIGEM_API_BLIZZARD, REGIAO_GLOBAL, TIPO_TEMPORADA
from src.services.api_client import ApiIndisponivelError
from src.services.eventos.base import EstruturaNaoReconhecidaError, EventoExtraido, FonteDeEventosIndisponivelError
from src.services.sanitizacao import PayloadForaDoFormatoError

logger = logging.getLogger(__name__)


class ClienteDeTemporadas(Protocol):
    def fetch_json(self, regiao: str, caminho: str, timeout: int = 30) -> Any:
        ...


# (rótulo no nome, índice, detalhe, campo do início, campo do fim)
_TEMPORADAS = (
    ("Mythic+", "/data/wow/mythic-keystone/season/index", "/data/wow/mythic-keystone/season/{}", "start_timestamp", "end_timestamp"),
    ("PvP", "/data/wow/pvp-season/index", "/data/wow/pvp-season/{}", "season_start_timestamp", "season_end_timestamp"),
)


def _dia(marca_em_ms: Any) -> Optional[Any]:
    if not isinstance(marca_em_ms, (int, float)) or isinstance(marca_em_ms, bool) or marca_em_ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(marca_em_ms / 1000, tz=timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


class TemporadasBlizzard:
    """
    CU10-C2 passo 2: temporadas de Mythic+ e de PvP, pela API oficial da Blizzard (o início e o fim de cada uma; a
    temporada em curso não tem fim). Uma temporada que a API recusa ou sem data é ignorada; se o índice não puder ser
    lido, é a falha do fluxo de exceção.
    """
    origem = ORIGEM_API_BLIZZARD

    def __init__(self, cliente: ClienteDeTemporadas, regiao: str = "US"):
        self.cliente = cliente
        self.regiao = regiao

    def extrair(self) -> list[EventoExtraido]:
        eventos: list[EventoExtraido] = []
        for rotulo, indice, detalhe, campo_inicio, campo_fim in _TEMPORADAS:
            eventos.extend(self._temporadas(rotulo, indice, detalhe, campo_inicio, campo_fim))
        if not eventos:
            raise EstruturaNaoReconhecidaError("A API não devolveu nenhuma temporada com data de início.")
        return eventos

    def _temporadas(self, rotulo: str, indice: str, detalhe: str, campo_inicio: str, campo_fim: str) -> list[EventoExtraido]:
        try:
            listagem = self.cliente.fetch_json(self.regiao, indice)
        except (ApiIndisponivelError, PayloadForaDoFormatoError) as e:
            raise FonteDeEventosIndisponivelError(str(e)) from e
        temporadas = listagem.get("seasons") if isinstance(listagem, dict) else None
        if not isinstance(temporadas, list):
            raise EstruturaNaoReconhecidaError(f"Resposta de {indice} sem a lista 'seasons'.")

        eventos: list[EventoExtraido] = []
        for temporada in temporadas:
            id_temporada = temporada.get("id") if isinstance(temporada, dict) else None
            if not isinstance(id_temporada, int):
                continue
            try:
                dados = self.cliente.fetch_json(self.regiao, detalhe.format(id_temporada))
            except (ApiIndisponivelError, PayloadForaDoFormatoError) as e:
                logger.warning("CU10-C2: temporada %s %s ignorada: %s", rotulo, id_temporada, e)
                continue
            inicio = _dia(dados.get(campo_inicio)) if isinstance(dados, dict) else None
            if inicio is None:
                logger.warning("CU10-C2: temporada %s %s sem data de início; ignorada.", rotulo, id_temporada)
                continue
            fim = _dia(dados.get(campo_fim))
            nome = dados.get("season_name") or f"{rotulo} Season {id_temporada}"  # as antigas vêm sem nome
            eventos.append(EventoExtraido(
                tipo=TIPO_TEMPORADA, nome=str(nome)[:150], data_inicio=inicio, data_fim=fim if fim and fim >= inicio else None,
                regiao=REGIAO_GLOBAL, origem=ORIGEM_API_BLIZZARD, fonte=f"API da Blizzard: {detalhe.format(id_temporada)}",
            ))
        return eventos
