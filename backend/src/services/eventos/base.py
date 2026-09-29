from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from src.models.evento import REGIAO_GLOBAL


class EstruturaNaoReconhecidaError(Exception):
    """CU10-C2-FE1: a página (ou a resposta da API) não tem a estrutura esperada, como depois de uma mudança de layout."""


class FonteDeEventosIndisponivelError(Exception):
    """CU10-C2-FE1: a fonte não respondeu (rede fora do ar, tempo limite ou erro HTTP)."""


@dataclass(frozen=True)
class EventoExtraido:
    """Um evento lido de uma fonte, antes de ser conferido e registrado (CU10-C2 passos 2 a 5)."""
    tipo: str
    nome: str
    data_inicio: date
    origem: str
    fonte: str
    versao: Optional[str] = None
    data_fim: Optional[date] = None
    regiao: str = REGIAO_GLOBAL

    @property
    def chave(self) -> tuple:
        """O que identifica o evento na base histórica (passo 4 / FA1): o mesmo tipo, nome, data e região."""
        return (self.tipo, self.nome, self.data_inicio, self.regiao)


class ProvedorDeEventos(Protocol):
    """O Provider do CU10-C2: extrai a relação de eventos de uma fonte."""
    origem: str

    def extrair(self) -> list[EventoExtraido]:
        ...
