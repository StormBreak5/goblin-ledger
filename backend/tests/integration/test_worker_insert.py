import pytest
from unittest.mock import patch
from src.repositories.item_price_repository import ItemPriceRepository
from src.models.item_price import ItemPrice
from src.models.api_models import WoWTokenResponse

@pytest.fixture
def mock_session(mocker):
    return mocker.Mock()

def test_repository_insert(mock_session):
    # Arrange
    repo = ItemPriceRepository(mock_session)
    fake_response = WoWTokenResponse(price=3140000000, last_updated_timestamp=1690000000)

    # Act
    repo.save_price(item_id=122284, region="us", token_response=fake_response)

    # Assert
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    # Validar objeto inserido
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, ItemPrice)
    assert added_obj.price_copper == 3140000000
    assert added_obj.item_id == 122284
    assert added_obj.region == "us"
