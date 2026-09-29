import requests
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Optional

from src.services import ingestao_config
from src.services.auth import AuthTokenManager
from src.services.sanitizacao import PayloadForaDoFormatoError
from src.models.api_models import WoWTokenResponse

logger = logging.getLogger(__name__)

TIMEOUT_LEILOES_SEGUNDOS = 60
TIMEOUT_COMMODITIES_SEGUNDOS = 180
ESPERA_MAXIMA_RETRY_AFTER = 60


class ApiIndisponivelError(Exception):
    """CU09-C1-FE1: a API não respondeu (5xx, tempo limite ou falha de rede) mesmo após as retentativas."""


@dataclass
class PayloadDeLeiloes:
    """Payload bruto de um endpoint da Casa de Leilões e o momento do snapshot (cabeçalho Last-Modified)."""
    payload: Any
    last_modified: Optional[datetime]


class BlizzardApiClient:
    def __init__(self, client_id: str, client_secret: str, dormir: Callable[[float], None] = time.sleep):
        self.auth_manager = AuthTokenManager(client_id, client_secret)
        self._dormir = dormir

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

    # ------------------------------------------------------------------ CU09-C1: leilões

    @staticmethod
    def _host_e_locale(regiao: str) -> tuple[str, str]:
        regiao = regiao.lower()
        return regiao, "en_US" if regiao == "us" else "en_GB"

    def _obter_com_retentativas(self, url: str, timeout: int) -> requests.Response:
        """
        CU09-C1 passos 3 a 5 e FE1: obtém o token e faz a requisição. Falha de rede, tempo limite, 5xx e 429 são
        tentadas de novo com espera crescente (5, 15 e 45 s; no 429 vale o Retry-After, até 60 s). Se persistir,
        levanta ApiIndisponivelError. Outros erros 4xx não melhoram tentando de novo e falham na hora.
        """
        esperas = ingestao_config.ESPERAS_ENTRE_TENTATIVAS
        ultimo_erro = "sem resposta"
        for tentativa in range(len(esperas) + 1):
            espera_extra = 0.0
            try:
                token = self.auth_manager.get_token()
                resposta = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
                if resposta.status_code == 429:
                    espera_extra = min(float(resposta.headers.get("Retry-After", 0) or 0), ESPERA_MAXIMA_RETRY_AFTER)
                    ultimo_erro = "HTTP 429 (limite de requisições)"
                elif resposta.status_code >= 500:
                    ultimo_erro = f"HTTP {resposta.status_code}"
                elif resposta.status_code >= 400:
                    raise ApiIndisponivelError(f"HTTP {resposta.status_code} em {url}")
                else:
                    return resposta
            except requests.RequestException as e:
                ultimo_erro = f"{type(e).__name__}: {e}"

            if tentativa < len(esperas):
                espera = max(esperas[tentativa], espera_extra)
                logger.warning("CU09-C1-FE1: falha (%s); nova tentativa em %ss.", ultimo_erro, espera)
                self._dormir(espera)
        raise ApiIndisponivelError(f"A API não respondeu após {len(esperas) + 1} tentativas: {ultimo_erro}")

    def _coletar(self, url: str, timeout: int) -> PayloadDeLeiloes:
        resposta = self._obter_com_retentativas(url, timeout)
        try:
            payload = resposta.json()
        except ValueError as e:
            raise PayloadForaDoFormatoError(f"Resposta que não é JSON: {e}") from e
        cabecalho = resposta.headers.get("Last-Modified")
        try:
            last_modified = parsedate_to_datetime(cabecalho) if cabecalho else None
        except (TypeError, ValueError):
            last_modified = None
        return PayloadDeLeiloes(payload=payload, last_modified=last_modified)

    def fetch_json(self, regiao: str, caminho: str, timeout: int = 30) -> Any:
        """CU10-C2: consulta de dados dinâmicos do jogo (namespace `dynamic-{região}`), como as temporadas de Mythic+ e
        de PvP. Falha de rede, tempo limite e 5xx são tentadas de novo; 4xx (inclusive 403) levanta ApiIndisponivelError."""
        host, locale = self._host_e_locale(regiao)
        url = f"https://{host}.api.blizzard.com{caminho}?namespace=dynamic-{host}&locale={locale}"
        resposta = self._obter_com_retentativas(url, timeout)
        try:
            return resposta.json()
        except ValueError as e:
            raise PayloadForaDoFormatoError(f"Resposta que não é JSON: {e}") from e

    def fetch_connected_realm_auctions(self, regiao: str, id_reino: int) -> PayloadDeLeiloes:
        """CU09-C1 passo 5: snapshot completo dos leilões do reino conectado (uma única resposta, sem paginação)."""
        host, locale = self._host_e_locale(regiao)
        url = (
            f"https://{host}.api.blizzard.com/data/wow/connected-realm/{id_reino}/auctions"
            f"?namespace=dynamic-{host}&locale={locale}"
        )
        return self._coletar(url, TIMEOUT_LEILOES_SEGUNDOS)

    def fetch_commodity_auctions(self, regiao: str) -> PayloadDeLeiloes:
        """CU09-C1 passo 5: snapshot completo das commodities da região (globais, fora dos reinos)."""
        host, locale = self._host_e_locale(regiao)
        url = f"https://{host}.api.blizzard.com/data/wow/auctions/commodities?namespace=dynamic-{host}&locale={locale}"
        return self._coletar(url, TIMEOUT_COMMODITIES_SEGUNDOS)
