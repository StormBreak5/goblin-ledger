import logging
import re
from typing import Callable

from src.models.evento import ORIGEM_WIKIPEDIA, REGIAO_GLOBAL, TIPO_EXPANSAO
from src.services.eventos.base import EstruturaNaoReconhecidaError, EventoExtraido
from src.services.eventos.datas import data_em_ingles
from src.services.eventos.leitor_html import ler_tabelas

logger = logging.getLogger(__name__)

URL_PADRAO = "https://en.wikipedia.org/wiki/World_of_Warcraft"
HOSTS_ACEITOS = ("en.wikipedia.org",)
NOME_DO_JOGO_BASE = "World of Warcraft"

_LANCAMENTO_AMERICAS = re.compile(r"(?:AU\s*/\s*NA|NA|US)\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
_LANCAMENTO_EUROPA = re.compile(r"\bEU\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")


class WikipediaExpansoes:
    """
    CU10-C2 passo 2: expansões do jogo, da tabela "Expansions for World of Warcraft" (título e data de lançamento) do
    artigo da Wikipedia. O lançamento do jogo base vem da caixa de informações e é opcional: se ela mudar, só ele deixa
    de vir. A data da tabela é única, então a região é GLOBAL; a caixa distingue as Américas (US) da Europa (EU).
    """
    origem = ORIGEM_WIKIPEDIA

    def __init__(self, url: str, baixar_pagina: Callable[[str], str]):
        self.url = url
        self._baixar_pagina = baixar_pagina

    def extrair(self) -> list[EventoExtraido]:
        tabelas = ler_tabelas(self._baixar_pagina(self.url))
        expansoes = next(
            (tabela for tabela in tabelas if tabela.cabecalho[:2] == ["title", "release date"]), None
        )
        if expansoes is None:
            raise EstruturaNaoReconhecidaError("Tabela de expansões (Title / Release date) não encontrada na página.")

        eventos: list[EventoExtraido] = []
        for linha in expansoes.linhas[1:]:
            data = data_em_ingles(linha[1]) if len(linha) > 1 else None
            if not linha or not linha[0] or data is None:
                logger.warning("CU10-C2: linha da tabela de expansões ignorada (sem título ou data legível): %s", linha)
                continue
            eventos.append(EventoExtraido(
                tipo=TIPO_EXPANSAO, nome=linha[0], data_inicio=data, regiao=REGIAO_GLOBAL,
                origem=ORIGEM_WIKIPEDIA, fonte=self.url,
            ))
        if not eventos:
            raise EstruturaNaoReconhecidaError("A tabela de expansões não trouxe nenhuma data legível.")

        eventos.extend(self._jogo_base(tabelas))
        return eventos

    def _jogo_base(self, tabelas) -> list[EventoExtraido]:
        """Lançamento do jogo original, da linha "Release" da caixa de informações (Américas e Europa)."""
        for tabela in tabelas:
            for linha in tabela.linhas:
                if len(linha) >= 2 and linha[0].lower() == "release":
                    americas, europa = _LANCAMENTO_AMERICAS.search(linha[1]), _LANCAMENTO_EUROPA.search(linha[1])
                    encontrados = []
                    for regiao, achado in (("US", americas), ("EU", europa)):
                        data = data_em_ingles(achado.group(1)) if achado else None
                        if data is not None:
                            encontrados.append(EventoExtraido(
                                tipo=TIPO_EXPANSAO, nome=NOME_DO_JOGO_BASE, data_inicio=data, regiao=regiao,
                                origem=ORIGEM_WIKIPEDIA, fonte=self.url,
                            ))
                    if encontrados:
                        return encontrados
        logger.warning("CU10-C2: a caixa de informações não trouxe o lançamento do jogo base; só as expansões foram lidas.")
        return []
