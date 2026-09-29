"""Atalhos compartilhados pelos testes do CU09."""
import copy
from datetime import datetime
from typing import Optional

from src.services.api_client import PayloadDeLeiloes
from src.services.ingestao_config import TIPO_COMMODITIES, TIPO_LEILOES, Mercado

MERCADO_REINO = Mercado(TIPO_LEILOES, "US", 3209, "US reino 3209")
MERCADO_COMMODITIES = Mercado(TIPO_COMMODITIES, "US", 32512, "US commodities")


def leilao_de_reino(id_leilao: int, item_id: int, buyout: Optional[int], quantidade: int = 1, bid: Optional[int] = None) -> dict:
    """Registro no formato da API de leilões do reino conectado (preços em cobre)."""
    registro = {"id": id_leilao, "item": {"id": item_id}, "quantity": quantidade, "time_left": "LONG"}
    if buyout is not None:
        registro["buyout"] = buyout
    if bid is not None:
        registro["bid"] = bid
    return registro


def leilao_de_commodity(id_leilao: int, item_id: int, preco_unitario: int, quantidade: int) -> dict:
    """Registro no formato da API de commodities (preço unitário em cobre)."""
    return {"id": id_leilao, "item": {"id": item_id}, "quantity": quantidade, "unit_price": preco_unitario, "time_left": "SHORT"}


class ClienteBlizzardFalso:
    """Substitui a API da Blizzard: devolve os payloads configurados, ou falha como se estivesse fora do ar."""

    def __init__(self, relogio) -> None:
        self.relogio = relogio
        self.payload_do_reino: dict = {"auctions": []}
        self.payload_das_commodities: dict = {"auctions": []}
        self.last_modified: Optional[datetime] = None  # None: o snapshot é do "agora" do relógio falso
        self.erro: Optional[Exception] = None
        self.chamadas: list[str] = []

    def _responder(self, chave: str, payload) -> PayloadDeLeiloes:
        self.chamadas.append(chave)
        if self.erro is not None:
            raise self.erro
        return PayloadDeLeiloes(payload=copy.deepcopy(payload), last_modified=self.last_modified or self.relogio())

    def fetch_connected_realm_auctions(self, regiao: str, id_reino: int) -> PayloadDeLeiloes:
        return self._responder(f"auctions:{regiao.lower()}:{id_reino}", self.payload_do_reino)

    def fetch_commodity_auctions(self, regiao: str) -> PayloadDeLeiloes:
        return self._responder(f"commodities:{regiao.lower()}", self.payload_das_commodities)
