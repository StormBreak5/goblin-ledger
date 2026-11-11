"""
Atributos fixos dos itens (classe, subclasse, qualidade, nível e preço de venda ao vendedor) gravados em
`items.metadata_info` para o modelo preditivo (variáveis 6, 7 e 15 a 17), e a sincronização diária de
itens, que mescla o `metadata_info` em vez de substituí-lo (o CU10-C1 guarda nele o ETag e a origem do arquivo).

Rodam contra um PostgreSQL temporário (ver tests/conftest.py), porque a mescla usa o `||` do JSONB e o upsert usa
`ON CONFLICT`. A API da Blizzard é sempre simulada.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
import pytest

from src.models.item import Item
from src.scraper import populate_item_details, sync_items
from src.scraper.populate_item_details import populate_details, selecionar_itens

ATRIBUTOS = {"item_class_id": 7, "item_subclass_id": 5, "quality": "COMMON", "level": 70, "sell_price": 1250,
             "atributos_atualizados_em": "2026-10-06T12:00:00+00:00"}
AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
ID_NA_URL = re.compile(r"/item/(\d+)\?")


def resposta_do_item(item_id: int, nome: str, classe: int = 7, subclasse: int = 5, qualidade: str = "COMMON",
                     nivel: int = 70, venda: Optional[int] = 1250) -> dict[str, Any]:
    """Resposta de /data/wow/item/{id} no formato da API da Blizzard (com locale, o nome vem como texto)."""
    resposta = {
        "id": item_id, "name": nome, "level": nivel, "required_level": 1, "purchase_price": 5000,
        "quality": {"type": qualidade, "name": qualidade.title()},
        "item_class": {"key": {"href": "https://us.api.blizzard.com/data/wow/item-class/7"}, "name": "Classe", "id": classe},
        "item_subclass": {"key": {"href": "https://us.api.blizzard.com/data/wow/item-class/7/item-subclass/5"},
                          "name": "Subclasse", "id": subclasse},
    }
    if venda is not None:
        resposta["sell_price"] = venda
    return resposta


class RespostaFalsa:
    def __init__(self, status: int, corpo: dict[str, Any]):
        self.status, self.corpo = status, corpo

    async def __aenter__(self) -> "RespostaFalsa":
        return self

    async def __aexit__(self, *excecao) -> bool:
        return False

    async def json(self) -> dict[str, Any]:
        return self.corpo


class ApiDeItensFalsa:
    """
    Substitui a `aiohttp.ClientSession` do preenchimento: responde aos endpoints de item e de mídia como a API da
    Blizzard. `itens[id]` é a resposta do item; `status[id]` força outro código ("rede" simula a conexão caindo).
    Item sem resposta cadastrada dá 404. `urls` guarda as requisições feitas.
    """

    def __init__(self) -> None:
        self.itens: dict[int, dict[str, Any]] = {}
        self.status: dict[int, Any] = {}
        self.urls: list[str] = []

    def __call__(self, *args, **kwargs) -> "ApiDeItensFalsa":
        return self

    async def __aenter__(self) -> "ApiDeItensFalsa":
        return self

    async def __aexit__(self, *excecao) -> bool:
        return False

    def get(self, url: str, headers: Optional[dict[str, str]] = None) -> RespostaFalsa:
        self.urls.append(url)
        item_id = int(ID_NA_URL.search(url).group(1))
        status = self.status.get(item_id, 200 if item_id in self.itens else 404)
        if status == "rede":
            raise aiohttp.ClientConnectionError("Connection reset by peer")
        if status != 200:
            return RespostaFalsa(status, {"code": status})
        if "/media/item/" in url:
            icone = f"https://render.worldofwarcraft.com/us/icons/56/{item_id}.jpg"
            return RespostaFalsa(200, {"assets": [{"key": "icon", "value": icone}]})
        return RespostaFalsa(200, self.itens[item_id])

    def consultados(self, endpoint: str = "/data/wow/item/") -> list[int]:
        return sorted(int(ID_NA_URL.search(url).group(1)) for url in self.urls if endpoint in url)


class ClienteBlizzardFalso:
    """Substitui o BlizzardApiClient na sincronização: devolve os ids ativos do reino e das commodities."""

    def __init__(self, reino: set[int], commodities: set[int]):
        self.reino, self.commodities = reino, commodities

    def fetch_active_auction_item_ids(self, region: str = "us", connected_realm_id: int = 11) -> set[int]:
        return set(self.reino)

    def fetch_active_commodity_item_ids(self, region: str = "us") -> set[int]:
        return set(self.commodities)


@pytest.fixture
def api(mocker) -> ApiDeItensFalsa:
    falsa = ApiDeItensFalsa()
    mocker.patch.object(populate_item_details.aiohttp, "ClientSession", falsa)
    mocker.patch.object(populate_item_details, "PAUSA_ENTRE_ITENS_SEGUNDOS", 0)
    return falsa


def _item(db_session, external_item_id: int, metadata_info, *, name: str = "Linen Cloth", icon_url: Optional[str] = "icone.jpg",
          is_active: bool = True) -> Item:
    item = Item(game="wow", external_item_id=str(external_item_id), name=name, icon_url=icon_url,
                metadata_info=metadata_info, is_active=is_active)
    db_session.add(item)
    db_session.commit()
    return item


def _metadata(db_session, external_item_id: int):
    db_session.expire_all()
    return db_session.query(Item).filter_by(external_item_id=str(external_item_id)).one().metadata_info


def _preencher(db_session):
    return populate_details(db_session=db_session, token="token-de-teste", relogio=lambda: AGORA)


def test_atributos_populate_grava_atributos_do_item(db_session, api):
    _item(db_session, 2589, {"source": "ingestao"}, name="Item 2589", icon_url=None)
    _item(db_session, 212243, {"source": "ah_dump"}, icon_url=None)
    api.itens[2589] = resposta_do_item(2589, "Linen Cloth")
    api.itens[212243] = resposta_do_item(212243, "Tome of Insight", classe=0, subclasse=8, qualidade="EPIC", nivel=616, venda=None)

    resumo = _preencher(db_session)

    assert (resumo.selecionados, resumo.gravados, resumo.indisponiveis, resumo.com_erro) == (2, 2, 0, 0)
    db_session.expire_all()
    item = db_session.query(Item).filter_by(external_item_id="2589").one()
    assert (item.name, item.icon_url) == ("Linen Cloth", "https://render.worldofwarcraft.com/us/icons/56/2589.jpg")
    assert item.metadata_info == {
        "source": "ingestao", "item_class_id": 7, "item_subclass_id": 5, "quality": "COMMON", "level": 70,
        "sell_price": 1250, "atributos_atualizados_em": "2026-10-06T12:00:00+00:00",
    }
    sem_preco_de_venda = _metadata(db_session, 212243)
    assert (sem_preco_de_venda["item_class_id"], sem_preco_de_venda["quality"], sem_preco_de_venda["level"]) == (0, "EPIC", 616)
    assert sem_preco_de_venda["sell_price"] is None  # a resposta não trouxe o preço de venda ao vendedor


def test_atributos_populate_mescla_metadata_sem_apagar_etag(db_session, api):
    do_cu10 = {"source": "ah_dump", "last_etag": '"6abc0233-1413"', "source_region": "32512"}
    icone = "https://render.worldofwarcraft.com/us/icons/56/inv_fabric_wool_01.jpg"
    _item(db_session, 2592, dict(do_cu10), name="Wool Cloth", icon_url=icone)
    api.itens[2592] = resposta_do_item(2592, "Wool Cloth", venda=33)

    _preencher(db_session)

    db_session.expire_all()
    item = db_session.query(Item).filter_by(external_item_id="2592").one()
    assert item.metadata_info == {**do_cu10, "item_class_id": 7, "item_subclass_id": 5, "quality": "COMMON", "level": 70,
                                  "sell_price": 33, "atributos_atualizados_em": "2026-10-06T12:00:00+00:00"}
    assert item.icon_url == icone  # o ícone que já existia fica


def test_atributos_populate_seleciona_itens_sem_atributos(db_session, api):
    _item(db_session, 2589, {"source": "ah_dump", **ATRIBUTOS})  # completo: fica fora
    _item(db_session, 2592, {"source": "ah_dump"})  # nome e ícone, sem atributos
    _item(db_session, 2604, dict(ATRIBUTOS), name="Item 2604", icon_url=None)  # atributos, mas nome provisório e sem ícone
    _item(db_session, 2605, None)  # metadata nulo
    _item(db_session, 2606, {"atributos_indisponiveis": True}, name="Item 2606", icon_url=None)  # a API já disse que não tem
    for item_id in (2589, 2592, 2604, 2605, 2606):
        api.itens[item_id] = resposta_do_item(item_id, f"Nome {item_id}")

    assert sorted(item.item_id for item in selecionar_itens(db_session)) == [2592, 2604, 2605]

    _preencher(db_session)

    assert api.consultados() == [2592, 2604, 2605]
    assert api.consultados("/media/item/") == [2604]  # o ícone só é pedido para quem não tem
    assert selecionar_itens(db_session) == []


def test_atributos_item_inexistente_na_api_nao_interrompe(db_session, api, caplog):
    _item(db_session, 2589, {"source": "ah_dump"})
    _item(db_session, 999999, {"source": "ah_dump", "last_etag": '"etag-999999"'}, name="Item 999999", icon_url=None)
    _item(db_session, 2592, {"source": "ah_dump"})
    api.itens[2589] = resposta_do_item(2589, "Linen Cloth")
    api.itens[2592] = resposta_do_item(2592, "Wool Cloth")

    with caplog.at_level(logging.WARNING, logger=populate_item_details.__name__):
        resumo = _preencher(db_session)

    assert (resumo.gravados, resumo.indisponiveis, resumo.com_erro) == (2, 1, 0)
    assert _metadata(db_session, 2589)["item_class_id"] == 7
    assert _metadata(db_session, 2592)["item_class_id"] == 7
    assert _metadata(db_session, 999999) == {
        "source": "ah_dump", "last_etag": '"etag-999999"', "atributos_indisponiveis": True,
        "atributos_atualizados_em": "2026-10-06T12:00:00+00:00",
    }
    assert any("999999" in registro.getMessage() and "404" in registro.getMessage() for registro in caplog.records)

    api.urls.clear()
    segunda = _preencher(db_session)
    assert (segunda.selecionados, api.urls) == (0, [])  # o item marcado não é consultado de novo


def test_atributos_erro_temporario_nao_marca_indisponivel(db_session, api):
    for item_id, falha in ((2589, 429), (2592, 503), (2604, "rede")):
        _item(db_session, item_id, {"source": "ah_dump"})
        api.status[item_id] = falha

    resumo = _preencher(db_session)

    assert (resumo.gravados, resumo.indisponiveis, resumo.com_erro) == (0, 0, 3)
    for item_id in (2589, 2592, 2604):
        assert _metadata(db_session, item_id) == {"source": "ah_dump"}
    assert sorted(item.item_id for item in selecionar_itens(db_session)) == [2589, 2592, 2604]  # ficam para a próxima


def test_atributos_sync_items_preserva_metadata_existente(db_session, mocker):
    mocker.patch("src.scraper.populate_item_details.populate_details")  # nunca chama a Blizzard
    com_tudo = {"source": "importacao", "last_etag": '"etag-2589"', "source_region": "32512", **ATRIBUTOS}
    _item(db_session, 2589, com_tudo, is_active=False)
    _item(db_session, 2592, {"last_etag": '"etag-2592"', "source_region": "3209"})
    _item(db_session, 2604, None)  # JSON `null` gravado pelo ORM: vale como objeto vazio

    sync_items.sync_items_from_blizzard(api_client=ClienteBlizzardFalso({2589, 2604, 4306}, {2592}), session=db_session)

    db_session.expire_all()
    assert _metadata(db_session, 2589) == com_tudo  # atributos, ETag, origem e quem cadastrou: nada se perde
    assert db_session.query(Item).filter_by(external_item_id="2589").one().is_active
    assert _metadata(db_session, 2592) == {"last_etag": '"etag-2592"', "source_region": "3209", "source": "ah_dump"}
    assert _metadata(db_session, 2604) == {"source": "ah_dump"}
    novo = db_session.query(Item).filter_by(external_item_id="4306").one()
    assert (novo.name, novo.metadata_info) == ("Item 4306", {"source": "ah_dump"})
    assert _metadata(db_session, sync_items.WOW_TOKEN_ID) == {"item_class": "Token", "expansion_id": None}
