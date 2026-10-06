"""
Atributos fixos dos itens (classe, subclasse, qualidade, nível e preço de venda ao vendedor) gravados em
`items.metadata_info` para o modelo preditivo (variáveis 6, 7 e 15 a 17 e filtro da RN07), e a sincronização diária de
itens, que mescla o `metadata_info` em vez de substituí-lo (o CU10-C1 guarda nele o ETag e a origem do arquivo).

Rodam contra um PostgreSQL temporário (ver tests/conftest.py), porque a mescla usa o `||` do JSONB e o upsert usa
`ON CONFLICT`. A API da Blizzard é sempre simulada.
"""
from src.models.item import Item
from src.scraper import sync_items

ATRIBUTOS = {"item_class_id": 7, "item_subclass_id": 5, "quality": "COMMON", "level": 70, "sell_price": 1250,
             "atributos_atualizados_em": "2026-10-06T12:00:00+00:00"}


class ClienteBlizzardFalso:
    """Substitui o BlizzardApiClient na sincronização: devolve os ids ativos do reino e das commodities."""

    def __init__(self, reino: set[int], commodities: set[int]):
        self.reino, self.commodities = reino, commodities

    def fetch_active_auction_item_ids(self, region: str = "us", connected_realm_id: int = 11) -> set[int]:
        return set(self.reino)

    def fetch_active_commodity_item_ids(self, region: str = "us") -> set[int]:
        return set(self.commodities)


def _item(db_session, external_item_id: int, metadata_info, *, name: str = "Linen Cloth", icon_url: str = "icone.jpg",
          is_active: bool = True) -> Item:
    item = Item(game="wow", external_item_id=str(external_item_id), name=name, icon_url=icon_url,
                metadata_info=metadata_info, is_active=is_active)
    db_session.add(item)
    db_session.commit()
    return item


def _metadata(db_session, external_item_id: int):
    db_session.expire_all()
    return db_session.query(Item).filter_by(external_item_id=str(external_item_id)).one().metadata_info


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
