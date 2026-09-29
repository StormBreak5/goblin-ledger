"""
CU09-C1 – cliente da API da Blizzard: retentativas do FE1 (só erro de rede e 5xx), Retry-After, Last-Modified.
"""
import pytest
import requests

from src.services.api_client import ApiIndisponivelError, BlizzardApiClient
from src.services.sanitizacao import PayloadForaDoFormatoError

LAST_MODIFIED = "Tue, 29 Sep 2026 12:00:00 GMT"


def _resposta(mocker, status=200, cabecalhos=None, json=None, json_invalido=False):
    resposta = mocker.Mock(status_code=status, headers=cabecalhos or {})
    if json_invalido:
        resposta.json.side_effect = ValueError("não é JSON")
    else:
        resposta.json.return_value = json if json is not None else {"auctions": []}
    return resposta


@pytest.fixture
def cliente(mocker):
    esperas: list[float] = []
    api = BlizzardApiClient("id", "segredo", dormir=esperas.append)
    mocker.patch.object(api.auth_manager, "get_token", return_value="token")
    api.esperas = esperas
    return api


def test_cu09_c1_fluxo_principal_coleta_os_dois_endpoints_com_o_last_modified(cliente, mocker):
    requisicao = mocker.patch(
        "src.services.api_client.requests.get",
        return_value=_resposta(mocker, cabecalhos={"Last-Modified": LAST_MODIFIED}, json={"auctions": [{"id": 1}]}),
    )

    reino = cliente.fetch_connected_realm_auctions("US", 3209)
    commodities = cliente.fetch_commodity_auctions("us")

    urls = [chamada.args[0] for chamada in requisicao.call_args_list]
    assert urls[0] == "https://us.api.blizzard.com/data/wow/connected-realm/3209/auctions?namespace=dynamic-us&locale=en_US"
    assert urls[1] == "https://us.api.blizzard.com/data/wow/auctions/commodities?namespace=dynamic-us&locale=en_US"
    assert requisicao.call_args_list[0].kwargs["headers"] == {"Authorization": "Bearer token"}
    assert reino.payload == {"auctions": [{"id": 1}]} and commodities.last_modified.isoformat() == "2026-09-29T12:00:00+00:00"


def test_cu09_c1_fe1_retentativas_em_5xx_com_espera_crescente(cliente, mocker):
    mocker.patch(
        "src.services.api_client.requests.get",
        side_effect=[_resposta(mocker, 503), _resposta(mocker, 502), _resposta(mocker, 200)],
    )

    resultado = cliente.fetch_connected_realm_auctions("us", 3209)

    assert resultado.payload == {"auctions": []}
    assert cliente.esperas == [5, 15]  # 2 falhas, 2 esperas (5 s e 15 s) e a terceira tentativa deu certo


def test_cu09_c1_fe1_falha_persistente_levanta_erro_apos_quatro_tentativas(cliente, mocker):
    requisicao = mocker.patch("src.services.api_client.requests.get", return_value=_resposta(mocker, 500))

    with pytest.raises(ApiIndisponivelError) as erro:
        cliente.fetch_commodity_auctions("us")

    assert requisicao.call_count == 4 and cliente.esperas == [5, 15, 45]
    assert "4 tentativas" in str(erro.value) and "HTTP 500" in str(erro.value)


def test_cu09_c1_fe1_tempo_limite_e_falha_de_rede_tambem_sao_tentados_de_novo(cliente, mocker):
    mocker.patch(
        "src.services.api_client.requests.get",
        side_effect=[requests.Timeout("lento"), requests.ConnectionError("sem rede"), _resposta(mocker, 200)],
    )

    assert cliente.fetch_connected_realm_auctions("us", 1).payload == {"auctions": []}
    assert cliente.esperas == [5, 15]


def test_cu09_c1_fe1_falha_ao_obter_o_token_tambem_e_tentada_de_novo(cliente, mocker):
    cliente.auth_manager.get_token.side_effect = [requests.ConnectionError("oauth fora"), "token"]
    mocker.patch("src.services.api_client.requests.get", return_value=_resposta(mocker, 200))

    assert cliente.fetch_connected_realm_auctions("us", 1).payload == {"auctions": []}
    assert cliente.esperas == [5]


def test_cu09_c1_fe1_429_respeita_o_retry_after(cliente, mocker):
    mocker.patch(
        "src.services.api_client.requests.get",
        side_effect=[_resposta(mocker, 429, {"Retry-After": "30"}), _resposta(mocker, 429, {"Retry-After": "900"}), _resposta(mocker, 200)],
    )

    cliente.fetch_commodity_auctions("us")

    assert cliente.esperas == [30, 60]  # o Retry-After vale, limitado a 60 s


def test_cu09_c1_fe1_erro_4xx_nao_e_tentado_de_novo(cliente, mocker):
    requisicao = mocker.patch("src.services.api_client.requests.get", return_value=_resposta(mocker, 404))

    with pytest.raises(ApiIndisponivelError):
        cliente.fetch_connected_realm_auctions("us", 999999)

    assert requisicao.call_count == 1 and cliente.esperas == []


def test_cu09_c2_fe1_resposta_que_nao_e_json_e_payload_fora_do_formato(cliente, mocker):
    mocker.patch("src.services.api_client.requests.get", return_value=_resposta(mocker, 200, json_invalido=True))

    with pytest.raises(PayloadForaDoFormatoError):
        cliente.fetch_commodity_auctions("us")


def test_cu09_c1_regiao_eu_usa_o_host_e_o_locale_europeus(cliente, mocker):
    requisicao = mocker.patch("src.services.api_client.requests.get", return_value=_resposta(mocker, 200))

    cliente.fetch_connected_realm_auctions("EU", 1305)

    assert requisicao.call_args.args[0] == (
        "https://eu.api.blizzard.com/data/wow/connected-realm/1305/auctions?namespace=dynamic-eu&locale=en_GB"
    )
