import pytest
from src.services.api_client import BlizzardApiClient
from src.models.api_models import WoWTokenResponse
import requests

def test_blizzard_api_client_success(mocker):
    # Arrange
    mock_get = mocker.patch("requests.get")
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"price": 3140000000, "last_updated_timestamp": 1690000000}
    mock_get.return_value = mock_response

    # Fake auth helper
    mocker.patch("src.services.api_client.AuthTokenManager.get_token", return_value="token")

    client = BlizzardApiClient(client_id="x", client_secret="y")
    
    # Act
    token_data = client.get_wow_token_price(region="us")

    # Assert
    assert isinstance(token_data, WoWTokenResponse)
    assert token_data.price == 3140000000
    assert token_data.last_updated_timestamp == 1690000000
    expected_url = "https://us.api.blizzard.com/data/wow/token/index?namespace=dynamic-us&locale=en_US"
    mock_get.assert_called_once_with(expected_url, headers={"Authorization": "Bearer token"}, timeout=10)
