import logging
import re
from datetime import date
from typing import Callable

from src.models.evento import (
    ORIGEM_WARCRAFT_WIKI,
    REGIAO_GLOBAL,
    TIPO_EVENTO_SAZONAL,
    TIPO_PATCH,
)
from src.services.eventos.base import EstruturaNaoReconhecidaError, EventoExtraido
from src.services.eventos.datas import data_em_ingles, dias_e_meses
from src.services.eventos.leitor_html import Tabela, ler_tabelas

logger = logging.getLogger(__name__)

URL_HISTORICO_DE_PATCHES = "https://warcraft.wiki.gg/wiki/Patch_history"
URL_FERIADOS = "https://warcraft.wiki.gg/wiki/Holiday"
HOSTS_ACEITOS = ("warcraft.wiki.gg",)

_VERSAO = re.compile(r"\d+(?:\.\d+){1,3}")
_PRE_PATCH = re.compile(r"pre-?patch", re.IGNORECASE)
_SO_NA_EUROPA = re.compile(r"only in europe", re.IGNORECASE)


class WarcraftWikiPatches:
    """
    CU10-C2 passo 2: patches do jogo, das tabelas por expansão de `Patch_history` (Patch, Release date, Version,
    Interface, Highlights). O pré-patch é reconhecido pela descrição da linha e recebe o aviso no nome. Só o HTML da
    página é lido (a API da wiki está bloqueada no robots.txt).
    """
    origem = ORIGEM_WARCRAFT_WIKI

    def __init__(self, url: str, baixar_pagina: Callable[[str], str]):
        self.url = url
        self._baixar_pagina = baixar_pagina

    def extrair(self) -> list[EventoExtraido]:
        tabelas = [
            tabela for tabela in ler_tabelas(self._baixar_pagina(self.url)) if tabela.cabecalho[:2] == ["patch", "release date"]
        ]
        if not tabelas:
            raise EstruturaNaoReconhecidaError("Nenhuma tabela de patches (Patch / Release date) na página.")

        eventos: list[EventoExtraido] = []
        for tabela in tabelas:
            for linha in tabela.linhas[1:]:
                versao = _VERSAO.search(linha[0]) if linha else None
                data = data_em_ingles(linha[1]) if len(linha) > 1 else None
                if versao is None or data is None:
                    logger.warning("CU10-C2: linha de patch ignorada (versão ou data ilegível): %s", linha[:2])
                    continue
                pre_patch = len(linha) > 4 and _PRE_PATCH.search(linha[4]) is not None
                eventos.append(EventoExtraido(
                    tipo=TIPO_PATCH, nome=f"Patch {versao.group(0)}" + (" (pre-patch)" if pre_patch else ""),
                    versao=versao.group(0), data_inicio=data, regiao=REGIAO_GLOBAL,
                    origem=ORIGEM_WARCRAFT_WIKI, fonte=self.url,
                ))
        if not eventos:
            raise EstruturaNaoReconhecidaError("As tabelas de patches não trouxeram nenhuma data legível.")
        return eventos


def _periodo_no_ano(ano: int, inicio: tuple[int, int], fim: tuple[int, int]) -> tuple[date, date]:
    """Período anual em dia e mês; se o fim vier antes do início (Winter Veil, 15/dez a 2/jan), termina no ano seguinte."""
    data_inicio = date(ano, *inicio)
    return data_inicio, date(ano + (1 if fim < inicio else 0), *fim)


class WarcraftWikiFeriados:
    """
    CU10-C2 passo 2: eventos sazonais do jogo, da tabela "Azeroth event / Time period" da página `Holiday`. Os que têm
    período fixo ("7th Feb - 20th Feb", "19th Sept") viram um evento por ano, de `ano_inicial` a `ano_final`. Os de
    período variável (Lunar Festival, Noblegarden) não têm data na página: entram pelas regras de `recorrentes`.
    """
    origem = ORIGEM_WARCRAFT_WIKI

    def __init__(self, url: str, baixar_pagina: Callable[[str], str], ano_inicial: int, ano_final: int):
        self.url = url
        self._baixar_pagina = baixar_pagina
        self.ano_inicial = ano_inicial
        self.ano_final = ano_final

    @staticmethod
    def _tabela_de_eventos(tabelas: list[Tabela]):
        return next((tabela for tabela in tabelas if tabela.cabecalho[:2] == ["azeroth event", "time period"]), None)

    def extrair(self) -> list[EventoExtraido]:
        tabela = self._tabela_de_eventos(ler_tabelas(self._baixar_pagina(self.url)))
        if tabela is None:
            raise EstruturaNaoReconhecidaError("Tabela de eventos sazonais (Azeroth event / Time period) não encontrada.")

        eventos: list[EventoExtraido] = []
        for linha in tabela.linhas[1:]:
            if len(linha) < 2 or not linha[0]:
                continue
            periodo = dias_e_meses(linha[1])
            if not periodo or "varies" in linha[1].lower():
                logger.info("CU10-C2: %s tem período variável (%s); fica a cargo das regras.", linha[0], linha[1])
                continue
            inicio, fim = periodo[0], periodo[-1]
            regiao = "EU" if any(_SO_NA_EUROPA.search(celula) for celula in linha[2:]) else REGIAO_GLOBAL
            for ano in range(self.ano_inicial, self.ano_final + 1):
                try:
                    data_inicio, data_fim = _periodo_no_ano(ano, inicio, fim)
                except ValueError:
                    continue  # dia inexistente no ano
                eventos.append(EventoExtraido(
                    tipo=TIPO_EVENTO_SAZONAL, nome=linha[0], data_inicio=data_inicio,
                    data_fim=data_fim if data_fim != data_inicio else None, regiao=regiao,
                    origem=ORIGEM_WARCRAFT_WIKI, fonte=self.url,
                ))
        if not eventos:
            raise EstruturaNaoReconhecidaError("A tabela de eventos sazonais não trouxe nenhum período legível.")
        return eventos
