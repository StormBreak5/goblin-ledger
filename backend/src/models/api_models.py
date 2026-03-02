from pydantic import BaseModel, Field

class OAuthTokenResponse(BaseModel):
    access_token: str
    expires_in: int

class WoWTokenResponse(BaseModel):
    price: int = Field(description="O preco é retornado originalmente em copper (cobre) pela API da Blizzard.")
    last_updated_timestamp: int
