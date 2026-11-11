"""RN09 / RN14 – frescor dos dados de mercado de um item, usado pela tela do item (CU04-C1 passo 4) e pela lista de
favoritos (CU06-C3-FA2)."""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.models.item_price import REGIAO_DA_FICHA, WOW_TOKEN_ID
from src.models.mercado import EstadoMercado
from src.repositories.item_price_repository import ItemPriceRepository
from src.repositories.mercado_repository import MercadoRepository
from src.services import ingestao_config


def frescor_do_item(session: Session, item_id: int, agora: datetime,
                    estados: Optional[Sequence[EstadoMercado]] = None) -> tuple[bool, Optional[datetime]]:
    """
    Compara o momento com o último ciclo de ingestão do mercado do item. Fica "desatualizado" se o mercado está
    sinalizado por falha (RN14) ou se o ciclo passou do limiar (RN09). A Ficha do WoW usa a idade do último preço; um item
    que o ciclo da Blizzard nunca coletou usa o ciclo mais recente de qualquer mercado. `estados` evita reler os
    mercados quando a função é chamada para vários itens.
    """
    limiar = ingestao_config.LIMIAR_DE_DADOS_DESATUALIZADOS
    if item_id == WOW_TOKEN_ID:
        ultimo = ItemPriceRepository(session).latest(WOW_TOKEN_ID, REGIAO_DA_FICHA)
        ultima = ultimo.created_at if ultimo is not None else None
        return ultima is None or agora - ultima > limiar, ultima

    repositorio = MercadoRepository(session)
    estados = repositorio.estados() if estados is None else estados
    id_reino = repositorio.mercado_do_item(item_id)
    estado = next((e for e in estados if e.id_reino == id_reino), None) if id_reino is not None else None
    if estado is not None:
        ultima = estado.ultima_atualizacao_em
        return estado.desatualizado or ultima is None or agora - ultima > limiar, ultima
    ultimas = [e.ultima_atualizacao_em for e in estados if e.ultima_atualizacao_em is not None]
    ultima = max(ultimas) if ultimas else None
    return ultima is None or agora - ultima > limiar, ultima
