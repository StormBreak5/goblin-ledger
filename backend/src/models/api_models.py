from datetime import date, datetime
from typing import Literal, Optional, Union

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
    dados_limitados: bool = Field(description="CU04-C2-FA1: o histórico do item não cobre a janela pedida (nunca em ALL).")
    desatualizado: bool = Field(description="RN09 / RN14: o mercado do item está sinalizado ou passou do limiar.")
    ultima_atualizacao_em: Optional[datetime] = Field(default=None, description="Último ciclo de ingestão do mercado do item.")
    avisos: list[AvisoDoHistorico]


SituacaoDaProjecao = Literal[
    "DISPONIVEL",           # CU05-C1 fluxo principal (e FA7, com `desatualizada`)
    "MODELO_NAO_TREINADO",  # FA1
    "NAO_ELEGIVEL",         # FA2 (RN02 / RN27)
    "REPROVADA",            # FA3 (RN10)
    "EM_AVALIACAO",         # FA4 (RN10)
    "SUSPENSA",             # FA5 (RN13)
    "NAO_DISPONIVEL",       # FA6
]


class PredicaoDoDia(BaseModel):
    """CU05-C1 passo 3: a predição de um dia, gravada pelo CU11-C3."""
    data_prevista: date = Field(description="Dia previsto (o dia inteiro, em UTC).")
    preco_previsto: int = Field(description="Menor preço diário previsto, em Cobre (RN01).")
    variacao_pct: float = Field(description="Variação em relação ao preço diário do dia de referência, em %, com 1 casa.")


class AvisoDaProjecao(BaseModel):
    """CU05-C1 passo 7 e FA7: texto exibido junto à projeção; o cliente só o apresenta."""
    codigo: Literal["ORIGEM", "ERRO_TIPICO", "ESTIMATIVA", "DESATUALIZADA"]
    texto: str


class ProjecaoDoItemResponse(BaseModel):
    """CU05-C1: a projeção do item para os próximos 7 dias ou o motivo da indisponibilidade (mensagem do cenário)."""
    situacao: SituacaoDaProjecao
    mensagem: Optional[str] = Field(default=None, description="FA1 a FA6: texto exibido no lugar da projeção.")
    data_referencia: Optional[date] = Field(default=None, description="Dia de referência D da projeção (o último preço diário).")
    preco_referencia: Optional[int] = Field(default=None, description="Preço diário de D, em Cobre: o ponto de partida.")
    erro_tipico_pct: Optional[int] = Field(default=None, description="MdAPE do item (RN10), em %, arredondado.")
    desatualizada: bool = Field(default=False, description="FA7: D ficou mais de PROJECAO_DESATUALIZADA_DIAS atrás.")
    predicoes: list[PredicaoDoDia] = Field(default_factory=list, description="Só os dias a partir de hoje (UTC), em ordem.")
    avisos: list[AvisoDaProjecao] = Field(default_factory=list)


class ItemDetail(BaseModel):
    """CU03-C3 passo 3: dados do item selecionado, usados pela tela de detalhes."""
    id: int
    name: str
    icon_url: Optional[str] = None
    favorito: Optional[bool] = Field(
        default=None,
        description="CU06: se o item está nos favoritos do usuário; só com uma sessão válida (sem ela, fica de fora).",
    )


class FavoritoResponse(BaseModel):
    """CU06-C1 / C2: o estado do controle ("Favoritado" ou "Favoritar") e a mensagem do cenário, se houver."""
    item_id: int
    favorito: bool
    message: Optional[str] = Field(default=None, description="Nula no CU06-C1-FA2 (o item já estava nos favoritos).")


class AlertaRequest(BaseModel):
    """CU07-C1 passo 5 / C2 passo 3: o tipo de gatilho, o preço-alvo em Ouro, Prata e Cobre e o canal. Os campos são
    opcionais e soltos de propósito: a validação é do serviço, que responde com a mensagem do FA3 (e não com o erro
    padrão de validação)."""
    tipo: Optional[str] = None
    canal: Optional[str] = None
    ouro: Optional[Union[int, float, str]] = None
    prata: Optional[Union[int, float, str]] = None
    cobre: Optional[Union[int, float, str]] = None


class Alerta(BaseModel):
    """CU07: um alerta de preço, com o preço-alvo em Cobre (RN01)."""
    id_alerta: int
    item_id: int
    tipo: Literal["COMPRA", "VENDA"]
    preco_alvo: int
    canal: Literal["WEB", "EMAIL", "AMBOS"]
    situacao: Literal["ATIVO", "DISPARADO"]
    disparado_em: Optional[datetime] = None


class AlertasDoItemResponse(BaseModel):
    """A seção "Alertas de preço" da tela do item: os alertas do usuário para o item e a cota da RN08."""
    alertas: list[Alerta]
    ativos_do_usuario: int = Field(description="RN08: alertas ativos do usuário em todos os itens.")
    limite: int


class FormularioDoAlertaResponse(BaseModel):
    """CU07-C1 passo 4 / C2 passo 2: o valor de mercado atual do item como referência (RN06, em Cobre) e, na alteração,
    os dados atuais do alerta."""
    item_id: int
    market_value: Optional[int] = None
    alerta: Optional[Alerta] = None


class AlertaSalvoResponse(BaseModel):
    """CU07-C1 passo 8 / C2 passo 6: o alerta gravado e a mensagem do cenário."""
    alerta: Alerta
    message: str


class ItemFavorito(BaseModel):
    """CU06-C3 passo 4: um item da lista de favoritos e a situação de mercado dele."""
    item_id: int
    name: str
    icon_url: Optional[str] = None
    market_value: Optional[int] = Field(default=None, description="Valor de mercado atual (RN06), em Cobre (RN01).")
    variacao_pct: Optional[float] = Field(default=None, description="Em relação ao dia anterior, em %; nula sem dado.")
    alertas_ativos: int
    desatualizado: bool = Field(description="CU06-C3-FA2 (RN09 / RN14).")
    aviso: Optional[str] = Field(default=None, description="O selo do FA2, com o texto do cenário.")


class FavoritosResponse(BaseModel):
    """CU06-C3: a lista de favoritos em ordem alfabética, ou a mensagem do FA1."""
    itens: list[ItemFavorito]
    mensagem: Optional[str] = None


class Notificacao(BaseModel):
    """CU08-C3 passo 4: uma notificação do sino, com o item, o tipo de gatilho, o preço-alvo e o valor de mercado que o
    atingiu (em Cobre, RN01) e a data e a hora do disparo."""
    id_notificacao: int
    item_id: int
    name: str
    icon_url: Optional[str] = None
    tipo: Literal["COMPRA", "VENDA"]
    preco_alvo: int
    valor_mercado: int
    disparada_em: datetime
    lida: bool


class NotificacoesResponse(BaseModel):
    """CU08-C3: as notificações da tela, da mais recente para a mais antiga, as não lidas e a mensagem do FA1."""
    notificacoes: list[Notificacao]
    nao_lidas: int
    mensagem: Optional[str] = None


class NaoLidasResponse(BaseModel):
    """CU08-C3 passos 1 e 5: o contador do sino."""
    nao_lidas: int


class MarcarLidasRequest(BaseModel):
    """CU08-C3 passo 5: os ids das notificações exibidas."""
    ids: list[int] = Field(default_factory=list, max_length=1000)
