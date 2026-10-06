import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Optional

from src.repositories.database import init_db, get_session
from src.services.api_client import BlizzardApiClient
from src.models.item import Item, mesclar_metadata
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

WOW_TOKEN_ID = 122284

def sync_items_from_blizzard(api_client: Optional[BlizzardApiClient] = None, session: Optional[Session] = None) -> None:
    """
    Sincroniza os itens leiloáveis ativos do momento lendo o dump da AH da Blizzard
    e armazena no Item para serem rastreados.
    `api_client` e `session` só são informados pelos testes; por padrão vêm das credenciais e do banco configurados.
    """
    logger.info("Iniciando sincronização de itens da Blizzard...")
    if api_client is None:
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error("Credenciais da Blizzard ausentes. Sincronização cancelada.")
            return

        api_client = BlizzardApiClient(client_id, client_secret)
    sessao_propria = session is None
    session = session or get_session()
    
    try:
        # Puxar Token
        logger.info("Adicionando WoW Token manualmente...")
        items_to_upsert = [{
            "game": "wow",
            "external_item_id": str(WOW_TOKEN_ID),
            "name": "WoW Token",
            "metadata_info": {"item_class": "Token", "expansion_id": None}
        }]
        
        # Extrair todos os IDs válidos e em circulação no momento da Casa de Leilões (Realm)
        logger.info("Extraindo IDs do dump da Casa de Leilões do Azralon...")
        realm_item_ids = api_client.fetch_active_auction_item_ids(region="us", connected_realm_id=3209)
        
        # Extrair todos os IDs de commodities válidos globalmente
        logger.info("Extraindo IDs do dump de commodities globais (US)...")
        commodity_item_ids = api_client.fetch_active_commodity_item_ids(region="us")
        
        # Combinar todos
        all_active_ids = realm_item_ids.union(commodity_item_ids)
        logger.info(f"Total combinado de IDs a serem rastreados: {len(all_active_ids)}")
        
        for item_id in all_active_ids:
            items_to_upsert.append({
                "game": "wow",
                "external_item_id": str(item_id),
                "name": f"Item {item_id}", # Idealmente, buscaríamos o nome no banco local depois ou via API.
                "metadata_info": {"source": "ah_dump"}
            })
                
        # Como pode haver 15.000 itens, inserimos em chunks para evitar sobrecarregar o DB
        if items_to_upsert:
            chunk_size = 2000
            for i in range(0, len(items_to_upsert), chunk_size):
                chunk = items_to_upsert[i:i+chunk_size]
                stmt = insert(Item).values(chunk)
                # Mescla, com o que já existe por cima: substituir o JSON apagava todo dia o ETag e a origem do CU10-C1
                # e os atributos do item. O `source` de quem cadastrou o item (importação, ingestão) também fica.
                stmt = stmt.on_conflict_do_update(
                    index_elements=['game', 'external_item_id'],
                    set_={
                        'is_active': True,
                        'metadata_info': mesclar_metadata(stmt.excluded.metadata_info, Item.metadata_info)
                    }
                )
                session.execute(stmt)
                
            session.commit()
            logger.info(f"Sincronização concluída! Total na base inserido/atualizado: {len(items_to_upsert)}")
            
            # Populate item details (name and icon) asynchronously
            from src.scraper.populate_item_details import populate_details
            populate_details()
        else:
            logger.warning("Nenhum item foi recebido para upsert.")
            
    except Exception as e:
        logger.error(f"Erro ao sincronizar itens: {e}")
        session.rollback()
        raise
    finally:
        if sessao_propria:
            session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    init_db()
    sync_items_from_blizzard()
