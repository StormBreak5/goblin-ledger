import pytest
from src.services.auth import AuthTokenManager
import requests

def test_auth_token_manager_success(mocker):
    # Arrange
    mock_post = mocker.patch("requests.post")
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "fake_token_123", "expires_in": 86400}
    mock_post.return_value = mock_response

    manager = AuthTokenManager("fake_client", "fake_secret")
    
    # Act
    token = manager.get_token()

    # Assert
    assert token == "fake_token_123"
    assert manager._cached_token == "fake_token_123"
    assert manager._token_expires_at is not None
    mock_post.assert_called_once()

def test_auth_token_manager_reuses_valid_token(mocker):
    # Arrange
    manager = AuthTokenManager("c", "s")
    manager._cached_token = "valid_cached_token"
    # Pega timestamp bem no futuro
    import time
    manager._token_expires_at = time.time() + 3600
    
    mock_post = mocker.patch("requests.post")
    
    # Act
    token = manager.get_token()

    # Assert
    assert token == "valid_cached_token"
    mock_post.assert_not_called()

def test_auth_token_manager_handles_http_error(mocker):
    # Arrange
    mock_post = mocker.patch("requests.post")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Unauthorized")
    mock_post.return_value = mock_response

    manager = AuthTokenManager("fake", "fake")
    
    # Act & Assert
    with pytest.raises(requests.exceptions.HTTPError):
        manager.get_token()
