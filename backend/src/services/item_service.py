import math
import re
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from src.scraper.models import HistoricalItemPrice
from src.models.item import Item
from src.models.api_models import ItemDetail, ItemSearchResponse, ItemSummary
from src.repositories.item_repository import ItemRepository
from src.repositories.mercado_repository import MercadoRepository
from src.services.valor_de_mercado import primeiro_quartil_ponderado

# CU03: parâmetros da busca (RF02 - Termo de Busca: texto de até 100 caracteres).
SEARCH_MIN_LENGTH = 3
SEARCH_MAX_LENGTH = 100
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# CU03: mensagens exibidas ao usuário, exatamente como nos cenários do documento.
MSG_TERMO_INSUFICIENTE = "Digite ao menos três caracteres para pesquisar"  # C1-FA1
MSG_NENHUM_ITEM_POR_NOME = "Nenhum item encontrado para o termo pesquisado"  # C1-FA2
MSG_NENHUM_ITEM_POR_ID = "Nenhum item corresponde ao identificador informado"  # C2-FA1
MSG_FALHA_NA_BUSCA = "Não foi possível realizar a busca no momento. Tente novamente mais tarde"  # C1-FE1 / C2-FE1
MSG_ITEM_INDISPONIVEL = "Item indisponível. Realize uma nova busca"  # C3-FE1

_ONLY_ASCII_DIGITS = re.compile(r"[0-9]+")


class InvalidSearchTermError(ValueError):
    """CU03-C1-FA1: termo de busca com menos de três caracteres."""


class ItemNotFoundError(LookupError):
    """CU03-C3-FE1: item não localizado no banco de dados."""


class ItemService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ItemRepository(session)

    def get_item_history(self, item_id: int, region: str = "US", window: str = "14D"):
        """
        Busca o histórico de preços e volumes de um item específico na janela de tempo especificada.
        """
        # Parse window
        days = 14
        if window == 'ALL':
            days = None
        elif window.endswith('D'):
            try:
                days = int(window[:-1])
            except ValueError:
                pass
        
        query = self.session.query(HistoricalItemPrice).filter(
            HistoricalItemPrice.item_id == item_id
        )
        
        if days is not None:
            # O backend trata tudo em UTC
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(HistoricalItemPrice.timestamp >= cutoff_date)
            
        query = query.order_by(HistoricalItemPrice.timestamp.asc())
        
        results = query.all()
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                # O banco guarda UTC sem fuso. Sem o "+00:00" o navegador leria o horário como local (3 h de erro em
                # GMT-3); com ele o JavaScript converte para o fuso de quem está vendo.
                "timestamp": r.timestamp.replace(tzinfo=timezone.utc).isoformat(),
                "price": r.price,
                "quantity": r.quantity,
                # RN16: "DIARIA" é o dia inteiro em UTC (00:00 UTC); "HORARIA" é um instante.
                "granularity": r.granularidade,
            })
            
        return formatted_results

    def search_items(self, query: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> ItemSearchResponse:
        """CU03-C1 / CU03-C2 (RF02): busca itens por nome ou por identificador numérico, com paginação.

        - C1-FA1: termo com menos de três caracteres não executa a consulta.
        - C2 passo 2: termo somente numérico é interpretado como identificador de item.
        - C2-FA2: termo com letras e números é tratado como busca textual (C1).
        """
        term = (query or "").strip()
        if len(term) < SEARCH_MIN_LENGTH:
            raise InvalidSearchTermError(MSG_TERMO_INSUFICIENTE)

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        if _ONLY_ASCII_DIGITS.fullmatch(term):
            return self._search_by_id(term, page, page_size)
        return self._search_by_name(term, page, page_size)

    def _search_by_name(self, term: str, page: int, page_size: int) -> ItemSearchResponse:
        """CU03-C1 passos 2 a 5 (normaliza o termo, consulta, recupera a última atualização, pagina)."""
        items, total = self.repository.search_by_name(term, offset=(page - 1) * page_size, limit=page_size)
        return self._build_response(
            items, total, page, page_size, search_type="name", empty_message=MSG_NENHUM_ITEM_POR_NOME
        )

    def _search_by_id(self, term: str, page: int, page_size: int) -> ItemSearchResponse:
        """CU03-C2 passos 3 a 5: o item correspondente ao identificador é o resultado único da busca."""
        item = self.repository.find_by_external_id(str(int(term)))
        items = [item] if item is not None and page == 1 else []
        total = 1 if item is not None else 0
        return self._build_response(
            items, total, page, page_size, search_type="id", empty_message=MSG_NENHUM_ITEM_POR_ID
        )

    def _build_response(
        self,
        items: list[Item],
        total: int,
        page: int,
        page_size: int,
        search_type: str,
        empty_message: str,
    ) -> ItemSearchResponse:
        """CU03-C1/C2 passos 4 e 5: anexa a data da última atualização do leilão e monta a página de resultados."""
        last_updates = self.repository.last_auction_update(item.external_item_id for item in items)
        return ItemSearchResponse(
            items=[
                ItemSummary(
                    id=int(item.external_item_id),
                    name=item.name,
                    icon_url=item.icon_url,
                    last_auction_update=last_updates.get(item.external_item_id),
                )
                for item in items
            ],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size),
            search_type=search_type,
            message=empty_message if total == 0 else None,
        )

    def get_item(self, item_id: int) -> ItemDetail:
        """CU03-C3 passo 3 / C3-FE1: dados do item selecionado; levanta ItemNotFoundError se ele não existir mais."""
        item = self.repository.find_by_external_id(str(item_id))
        if item is None:
            raise ItemNotFoundError(MSG_ITEM_INDISPONIVEL)
        return ItemDetail(id=int(item.external_item_id), name=item.name, icon_url=item.icon_url)

    def get_current_auctions(self, item_id: int, region: str = "3209"):
        """
        CU09 (observações): os leilões atuais do item vêm do banco próprio, alimentado pelo ciclo de ingestão da
        Blizzard, e não mais da Undermine Exchange. Considera os leilões do último ciclo de cada mercado; o valor
        de mercado é o primeiro quartil dos preços (RN06). `region` é mantido por compatibilidade e não é usado.
        """
        ofertas = MercadoRepository(self.session).leiloes_do_ultimo_ciclo(int(item_id))
        if not ofertas:
            return {"min_price": 0, "total_quantity": 0, "market_value": None}
        return {
            "min_price": min(preco for preco, _ in ofertas),
            "total_quantity": sum(quantidade for _, quantidade in ofertas),
            "market_value": primeiro_quartil_ponderado(ofertas),
        }
