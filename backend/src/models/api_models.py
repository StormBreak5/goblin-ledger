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

class PontoDoHistorico(BaseModel):
    """CU04-C1 passo 2: um ponto da série de preços e volume do item."""
    timestamp: datetime = Field(description="Instante em UTC, com o fuso explícito.")
    price: int = Field(description="Preço em Cobre (RN01); a conversão para Ouro/Prata/Cobre é só da exibição.")
    quantity: Optional[int] = Field(default=None, description="Volume; nulo quando a fonte não o informa (CU04-C3-FA1).")
    granularity: Literal["DIARIA", "HORARIA"] = Field(description="RN16: dia inteiro em UTC (00:00 UTC) ou um instante.")


class AvisoDoHistorico(BaseModel):
    """Aviso do CU04 com o texto exato do cenário: o cliente só o apresenta."""
    codigo: Literal["SEM_HISTORICO", "DADOS_DESATUALIZADOS", "DADOS_LIMITADOS"]
    texto: str


class HistoricoDoItemResponse(BaseModel):
    """CU04-C1: série do item na janela pedida e a situação dos dados (frescor, RN09 / RN14)."""
    janela: str = Field(description="Janela aplicada: 14D, 30D, 90D, 365D ou ALL.")
    pontos: list[PontoDoHistorico]
    desatualizado: bool = Field(description="RN09 / RN14: o mercado do item está sinalizado ou passou do limiar.")
    ultima_atualizacao_em: Optional[datetime] = Field(default=None, description="Último ciclo de ingestão do mercado do item.")
    avisos: list[AvisoDoHistorico]


class ItemDetail(BaseModel):
    """CU03-C3 passo 3: dados do item selecionado, usados pela tela de detalhes."""
    id: int
    name: str
    icon_url: Optional[str] = None
