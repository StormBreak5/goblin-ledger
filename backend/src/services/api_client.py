import requests
import logging
from src.services.auth import AuthTokenManager
from src.models.api_models import WoWTokenResponse

logger = logging.getLogger(__name__)

class BlizzardApiClient:
    def __init__(self, client_id: str, client_secret: str):
        self.auth_manager = AuthTokenManager(client_id, client_secret)

    def get_wow_token_price(self, region: str = "us") -> WoWTokenResponse:
        """
        Consome a API de Token dinâmica e devolve o modelo validado.
        Atualmente focado no namespace 'dynamic-us'.
        """
        token = self.auth_manager.get_token()
        
        namespace = f"dynamic-{region}"
        # Mapeando locale genericamente de região, porém poderia ser expandido no futuro.
        locale = "en_US" if region == "us" else "en_GB" 
        
        url = f"https://{region}.api.blizzard.com/data/wow/token/index?namespace={namespace}&locale={locale}"
        
        logger.info(f"Buscando preço do WoW token na url: {url}")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return WoWTokenResponse(**data)

    def fetch_active_auction_item_ids(self, region: str = "us", connected_realm_id: int = 11) -> set:
        """
        Busca todos os leilões ativos de um reino de alta população (ex: Tichondrius US - 11).
        Como os leilões de commodities (stackáveis) são globais por região, e os equipamentos
        são por reino, bater em um reino de alta população nos garante a lista de praticamente
        TODOS os IDs que possuem liquidez e valor na economia atual, perfeitamente filtrados.
        """
        token = self.auth_manager.get_token()
        namespace = f"dynamic-{region}"
        locale = "en_US" if region == "us" else "en_GB"
        
        url = (
            f"https://{region}.api.blizzard.com/data/wow/connected-realm/{connected_realm_id}/auctions"
            f"?namespace={namespace}&locale={locale}"
        )
        
        logger.info(f"Buscando dump da casa de leilões do reino {connected_realm_id} para extração de IDs...")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        auctions = data.get("auctions", [])
        unique_item_ids = {a.get("item", {}).get("id") for a in auctions if a.get("item", {}).get("id")}
        
        logger.info(f"Total de {len(unique_item_ids)} itens ÚNICOS leiloáveis encontrados ativos no momento.")
        return unique_item_ids

    def fetch_active_commodity_item_ids(self, region: str = "us") -> set:
        """
        Busca todos os leilões ativos de commodities da região inteira.
        Esses itens não aparecem no endpoint de connected-realm.
        """
        token = self.auth_manager.get_token()
        namespace = f"dynamic-{region}"
        locale = "en_US" if region == "us" else "en_GB"
        
        url = (
            f"https://{region}.api.blizzard.com/data/wow/auctions/commodities"
            f"?namespace={namespace}&locale={locale}"
        )
        
        logger.info(f"Buscando dump de commodities da região {region} para extração de IDs...")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        auctions = data.get("auctions", [])
        unique_item_ids = {a.get("item", {}).get("id") for a in auctions if a.get("item", {}).get("id")}
        
        logger.info(f"Total de {len(unique_item_ids)} commodities ÚNICAS encontradas ativas no momento.")
        return unique_item_ids
