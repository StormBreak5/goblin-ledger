import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional
from urllib.parse import urlparse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.evento import (
    EXTRACAO_FALHA,
    EXTRACAO_SUCESSO,
    ORIGEM_MANUAL_EVENTO,
    REGIAO_GLOBAL,
    REGIOES_DE_EVENTO,
    TIPOS_DE_EVENTO,
    EventoJogo,
)
from src.repositories.evento_repository import EventoRepository
from src.services import security
from src.services.erros import (
    DadosInvalidosError,
    EventosNaoExtraidosError,
    ExtracaoRecenteError,
    FonteDeEventosInvalidaError,
)
from src.services.eventos import warcraft_wiki, wikipedia_expansoes
from src.services.eventos.base import (
    EstruturaNaoReconhecidaError,
    EventoExtraido,
    FonteDeEventosIndisponivelError,
    ProvedorDeEventos,
)
from src.services.eventos.datas import data_br
from src.services.eventos.pagina import baixar_pagina
from src.services.eventos.recorrentes import Recorrentes, dia_do_reinicio_da_europa, feriados_variaveis
from src.services.eventos.temporadas_blizzard import TemporadasBlizzard

logger = logging.getLogger(__name__)

# CU10-C2 passo 1: de onde os eventos podem ser extraídos.
FONTE_EXPANSOES = "EXPANSOES"  # Wikipedia
FONTE_PATCHES = "PATCHES"  # Warcraft Wiki, Patch_history
FONTE_SAZONAIS = "SAZONAIS"  # Warcraft Wiki, Holiday (mais as regras de Noblegarden e Lunar Festival)
FONTE_TEMPORADAS = "TEMPORADAS"  # API oficial da Blizzard
FONTE_RECORRENTES = "RECORRENTES"  # regras de calendário
FONTES = (FONTE_EXPANSOES, FONTE_PATCHES, FONTE_SAZONAIS, FONTE_TEMPORADAS, FONTE_RECORRENTES)
FONTES_DE_PAGINA = (FONTE_EXPANSOES, FONTE_PATCHES, FONTE_SAZONAIS)
FONTE_MANUAL = "MANUAL"

_PAGINAS = {
    FONTE_EXPANSOES: (wikipedia_expansoes.URL_PADRAO, wikipedia_expansoes.HOSTS_ACEITOS),
    FONTE_PATCHES: (warcraft_wiki.URL_HISTORICO_DE_PATCHES, warcraft_wiki.HOSTS_ACEITOS),
    FONTE_SAZONAIS: (warcraft_wiki.URL_FERIADOS, warcraft_wiki.HOSTS_ACEITOS),
}

# Cuidado com as páginas de terceiros: não são lidas de novo em menos de 10 minutos (o documento não define).
INTERVALO_MINIMO_DA_EXTRACAO = timedelta(minutes=int(os.getenv("EVENTOS_INTERVALO_MINIMO_MINUTOS", "10")))
# Os eventos gerados por ano (sazonais e regras) vão do ano em que o histórico começa (set/2022) até N anos à frente.
ANO_INICIAL = int(os.getenv("EVENTOS_ANO_INICIAL", "2022"))
ANOS_A_FRENTE = int(os.getenv("EVENTOS_ANOS_A_FRENTE", "1"))

NOME_MAXIMO = 150
VERSAO_MAXIMA = 20
ANO_MINIMO = 2004  # lançamento do jogo
ANO_MAXIMO = 2100


@dataclass
class ResumoDaExtracao:
    """CU10-C2 passo 6: os eventos registrados e o que foi ignorado por já constar (FA1)."""
    fonte: str
    encontrados: int
    registrados: list[EventoJogo]
    ignorados: int


class EventoService:
    """CU10-C2 – Registrar eventos de atualização do jogo (RF11 / RN17): extração das fontes de referência e
    cadastro manual."""

    def __init__(
        self,
        session: Session,
        relogio: Callable[[], datetime] = security.agora,
        baixar_pagina_de: Callable[[str], str] = baixar_pagina,
        fabrica_de_cliente_blizzard: Optional[Callable] = None,
    ):
        self.session = session
        self.relogio = relogio
        self._baixar_pagina = baixar_pagina_de
        self._fabrica_de_cliente = fabrica_de_cliente_blizzard
        self.repository = EventoRepository(session)

    # ------------------------------------------------------------------ passos 1 a 6: extração

    def extrair(self, fonte: str, url: Optional[str] = None) -> ResumoDaExtracao:
        """
        Extrai os eventos da fonte, converte as datas, confere quais já estão registrados e registra os novos. Falha
        prevista da fonte (FE1) não registra nenhum evento; falha de banco desfaz o registro e propaga.
        """
        fonte = (fonte or "").strip().upper()
        if fonte not in FONTES:
            raise FonteDeEventosInvalidaError()
        endereco = self._endereco(fonte, url)

        inicio = self.relogio()
        self._respeitar_intervalo(fonte, endereco, inicio)

        try:
            eventos = self._provedor(fonte, endereco, inicio).extrair()
        except (EstruturaNaoReconhecidaError, FonteDeEventosIndisponivelError) as e:
            self._registrar_falha(fonte, endereco, inicio, e)
            raise EventosNaoExtraidosError() from e
        return self._registrar(fonte, endereco, inicio, eventos)

    def _endereco(self, fonte: str, url: Optional[str]) -> Optional[str]:
        """A página a ler: a informada ou a padrão da fonte. Só as páginas de referência conhecidas são lidas: qualquer
        outro endereço é uma página que o Provider não reconhece (FE1), sem chegar a ser consultada."""
        if fonte not in FONTES_DE_PAGINA:
            return None
        padrao, hosts = _PAGINAS[fonte]
        if not url or not url.strip():
            return padrao
        analisada = urlparse(url.strip())
        if analisada.scheme not in ("http", "https") or (analisada.hostname or "").lower() not in hosts:
            logger.error("CU10-C2-FE1: endereço não reconhecido para %s: %s", fonte, url)
            self._registrar_falha(fonte, url.strip()[:500], self.relogio(), EstruturaNaoReconhecidaError("Endereço não reconhecido."))
            raise EventosNaoExtraidosError()
        return url.strip()

    def _respeitar_intervalo(self, fonte: str, endereco: Optional[str], agora: datetime) -> None:
        if fonte not in FONTES_DE_PAGINA:
            return
        ultima = self.repository.ultima_extracao(fonte, endereco)
        if ultima is not None and agora - ultima < INTERVALO_MINIMO_DA_EXTRACAO:
            raise ExtracaoRecenteError()

    def _provedor(self, fonte: str, endereco: Optional[str], agora: datetime) -> ProvedorDeEventos:
        ano_final = agora.year + ANOS_A_FRENTE
        if fonte == FONTE_EXPANSOES:
            return wikipedia_expansoes.WikipediaExpansoes(endereco, self._baixar_pagina)
        if fonte == FONTE_PATCHES:
            return warcraft_wiki.WarcraftWikiPatches(endereco, self._baixar_pagina)
        if fonte == FONTE_SAZONAIS:
            return _Sazonais(warcraft_wiki.WarcraftWikiFeriados(endereco, self._baixar_pagina, ANO_INICIAL, ano_final), ANO_INICIAL, ano_final)
        if fonte == FONTE_TEMPORADAS:
            if self._fabrica_de_cliente is None:
                raise EstruturaNaoReconhecidaError("Cliente da API da Blizzard não configurado.")
            return TemporadasBlizzard(self._fabrica_de_cliente())
        return Recorrentes(ANO_INICIAL, ano_final, dia_do_reinicio_da_europa())

    def _registrar(self, fonte: str, endereco: Optional[str], inicio: datetime, eventos: list[EventoExtraido]) -> ResumoDaExtracao:
        """Passos 4 a 6 numa única transação: se o banco falhar, nenhum evento fica registrado."""
        try:
            registrados, ignorados = self.repository.registrar(eventos, self.relogio())
            self.repository.registrar_extracao(
                fonte, endereco, inicio, self.relogio(), EXTRACAO_SUCESSO,
                encontrados=len(eventos), registrados=len(registrados), ignorados=ignorados,
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception("CU10-C2: falha de banco ao registrar os eventos de %s; nada foi registrado.", fonte)
            raise
        logger.info("CU10-C2: %s: %d eventos lidos, %d registrados, %d já constavam.", fonte, len(eventos), len(registrados), ignorados)
        return ResumoDaExtracao(fonte, len(eventos), registrados, ignorados)

    def _registrar_falha(self, fonte: str, endereco: Optional[str], inicio: datetime, erro: Exception) -> None:
        """CU10-C2-FE1: a falha vai para o log (o do sistema e o da extração). Não registra nenhum evento."""
        logger.error("CU10-C2-FE1: não foi possível extrair os eventos de %s (%s): %s", fonte, endereco or "sem página", erro)
        try:
            self.repository.registrar_extracao(fonte, endereco, inicio, self.relogio(), EXTRACAO_FALHA, erro=str(erro)[:2000])
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception("CU10-C2-FE1: não foi possível gravar o log da extração.")

    # ------------------------------------------------------------------ FA2: cadastro manual

    def cadastrar_manual(
        self,
        nome: str,
        versao: Optional[str],
        tipo: str,
        data_inicio: str,
        data_fim: Optional[str] = None,
        regiao: str = REGIAO_GLOBAL,
    ) -> ResumoDaExtracao:
        """CU10-C2-FA2: o Admin informa o evento; o sistema valida os dados (2.2) e segue pelo mesmo caminho da extração
        (conversão da data, conferência de duplicado e registro)."""
        campos: list[str] = []
        nome_limpo = (nome or "").strip()
        if not nome_limpo or len(nome_limpo) > NOME_MAXIMO:
            campos.append("nome")
        versao_limpa = (versao or "").strip() or None
        if versao_limpa is not None and len(versao_limpa) > VERSAO_MAXIMA:
            campos.append("versao")
        tipo_normalizado = (tipo or "").strip().upper()
        if tipo_normalizado not in TIPOS_DE_EVENTO:
            campos.append("tipo")
        regiao_normalizada = (regiao or "").strip().upper()
        if regiao_normalizada not in REGIOES_DE_EVENTO:
            campos.append("regiao")
        inicio = _data_plausivel(data_inicio)
        if inicio is None:
            campos.append("data_inicio")
        fim: Optional[date] = None
        if data_fim is not None and data_fim.strip():
            fim = _data_plausivel(data_fim)
            if fim is None or (inicio is not None and fim < inicio):
                campos.append("data_fim")
        if campos:
            raise DadosInvalidosError(campos=campos)

        agora = self.relogio()
        evento = EventoExtraido(
            tipo=tipo_normalizado, nome=nome_limpo, versao=versao_limpa, data_inicio=inicio, data_fim=fim,
            regiao=regiao_normalizada, origem=ORIGEM_MANUAL_EVENTO, fonte="Cadastro manual pelo Admin",
        )
        return self._registrar(FONTE_MANUAL, None, agora, [evento])

    # ------------------------------------------------------------------ consulta

    def listar(self, tipo: Optional[str] = None, regiao: Optional[str] = None, limite: int = 100, deslocamento: int = 0):
        return self.repository.listar((tipo or "").strip().upper() or None, (regiao or "").strip().upper() or None, limite, deslocamento)


def _data_plausivel(texto: Optional[str]) -> Optional[date]:
    """DD/MM/AAAA de uma data que existe e cai entre o lançamento do jogo e o fim do século."""
    valor = data_br(texto or "")
    return valor if valor is not None and ANO_MINIMO <= valor.year <= ANO_MAXIMO else None


class _Sazonais:
    """Eventos sazonais: os períodos fixos da página `Holiday` da Warcraft Wiki mais as regras dos dois que variam."""
    origem = warcraft_wiki.WarcraftWikiFeriados.origem

    def __init__(self, feriados: warcraft_wiki.WarcraftWikiFeriados, ano_inicial: int, ano_final: int):
        self.feriados = feriados
        self.ano_inicial = ano_inicial
        self.ano_final = ano_final

    def extrair(self) -> list[EventoExtraido]:
        return self.feriados.extrair() + feriados_variaveis(self.ano_inicial, self.ano_final)
