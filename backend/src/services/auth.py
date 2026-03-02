import requests
import time
import logging
from requests.auth import HTTPBasicAuth
from src.models.api_models import OAuthTokenResponse

logger = logging.getLogger(__name__)

class AuthTokenManager:
    def __init__(self, client_id: str, client_secret: str, region: str = "us"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self._cached_token = None
        self._token_expires_at = 0

    def get_token(self) -> str:
        """Retorna o token cachedado ou busca um novo se tiver espirado."""
        if self._cached_token and time.time() < self._token_expires_at:
            return self._cached_token

        logger.info("Token expirado ou nulo. Solicitando novo OAuth token na Blizzard...")
        
        token_url = f"https://oauth.battle.net/token"
        
        response = requests.post(
            token_url,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=10
        )
        
        response.raise_for_status()
        
        data = OAuthTokenResponse(**response.json())
        self._cached_token = data.access_token
        
        # Guardaremos com uma margem de seguranca de 60 segundos pra evitar o edge-case de expirar "logo antes" de usar
        self._token_expires_at = time.time() + data.expires_in - 60
        
        return self._cached_token
