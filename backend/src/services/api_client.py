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
