"""Atalhos compartilhados pelos testes do CU10-C2 (eventos de atualização do jogo): páginas de referência e API falsas."""
import json
from pathlib import Path
from typing import Optional

from src.services.api_client import ApiIndisponivelError
from src.services.eventos import warcraft_wiki, wikipedia_expansoes

FIXTURES = Path(__file__).parent / "fixtures"

URL_EXPANSOES = wikipedia_expansoes.URL_PADRAO
URL_PATCHES = warcraft_wiki.URL_HISTORICO_DE_PATCHES
URL_FERIADOS = warcraft_wiki.URL_FERIADOS


def fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


class PaginasFalsas:
    """Substitui a leitura das páginas de referência: devolve trechos reais das páginas (tests/fixtures), ou falha como
    se a fonte estivesse fora do ar. Nenhum teste acessa a internet."""

    def __init__(self) -> None:
        self.paginas = {
            URL_EXPANSOES: fixture("wikipedia_world_of_warcraft.html"),
            URL_PATCHES: fixture("warcraft_wiki_patch_history.html"),
            URL_FERIADOS: fixture("warcraft_wiki_holiday.html"),
        }
        self.erro: Optional[Exception] = None
        self.chamadas: list[str] = []

    def __call__(self, url: str) -> str:
        from src.services.eventos.base import FonteDeEventosIndisponivelError

        self.chamadas.append(url)
        if self.erro is not None:
            raise self.erro
        if url not in self.paginas:
            raise FonteDeEventosIndisponivelError(f"HTTP 404 em {url}")
        return self.paginas[url]


def respostas_das_temporadas() -> dict:
    """Respostas reais da API da Blizzard (reduzidas): temporadas de Mythic+ e de PvP, com uma recusada (403)."""
    return json.loads(fixture("blizzard_temporadas.json"))


def responder_json(respostas: dict, caminho: str):
    """Como `BlizzardApiClient.fetch_json`: o JSON do caminho, ou ApiIndisponivelError (4xx ou caminho desconhecido)."""
    if caminho not in respostas:
        raise ApiIndisponivelError(f"HTTP 404 em {caminho}")
    resposta = respostas[caminho]
    if isinstance(resposta, dict) and "__erro__" in resposta:
        raise ApiIndisponivelError(f"HTTP {resposta['__erro__']} em {caminho}")
    return resposta
