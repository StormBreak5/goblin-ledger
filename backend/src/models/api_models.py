from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

class OAuthTokenResponse(BaseModel):
    access_token: str
    expires_in: int

class WoWTokenResponse(BaseModel):
    price: int = Field(description="O preco é retornado originalmente em copper (cobre) pela API da Blizzard.")
    last_updated_timestamp: int

class ItemSummary(BaseModel):
    """CU03-C1 passo 5 / CU03-C2 passo 5: item apresentado na relação de resultados."""
    id: int = Field(description="Identificador numérico do item na Casa de Leilões (Item.idItem do MR).")
    name: str
    icon_url: Optional[str] = None
    last_auction_update: Optional[datetime] = Field(
        default=None,
        description="CU03-C1/C2 passo 4: data (UTC) da última atualização do leilão do item; nula se não houver dados.",
    )

class ItemSearchResponse(BaseModel):
    """CU03-C1 / CU03-C2: relação paginada de itens localizados pela busca."""
    items: list[ItemSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
    search_type: Literal["name", "id"] = Field(
        description="'id' quando o termo é numérico (CU03-C2); 'name' nos demais casos (CU03-C1 e C2-FA2)."
    )
    message: Optional[str] = Field(
        default=None,
        description="Mensagem do cenário quando nenhum item é localizado (CU03-C1-FA2 ou CU03-C2-FA1).",
    )

class ItemDetail(BaseModel):
    """CU03-C3 passo 3: dados do item selecionado, usados pela tela de detalhes."""
    id: int
    name: str
    icon_url: Optional[str] = None
