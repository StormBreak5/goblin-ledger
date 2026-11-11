"""CU06 – Manter Favoritos (RF09): adicionar (C1), remover com os alertas do item (C2) e visualizar a lista (C3)."""
import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.api_models import FavoritoResponse, FavoritosResponse, ItemFavorito
from src.models.item_price import REGIAO_DA_FICHA, WOW_TOKEN_ID
from src.models.mercado import EstadoMercado
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.item_price_repository import ItemPriceRepository
from src.repositories.mercado_repository import MercadoRepository
from src.services import mensagens, security
from src.services.erros import FavoritoComAlertasError
from src.services.frescor import frescor_do_item
from src.services.valor_de_mercado import primeiro_quartil_ponderado

# CU06-C3: o "dia anterior" é o ponto 24 h antes do valor atual; ele só vale se estiver a no máximo esta tolerância.
UM_DIA = timedelta(hours=24)
FAVORITOS_VARIACAO_TOLERANCIA = timedelta(hours=int(os.getenv("FAVORITOS_VARIACAO_TOLERANCIA_HORAS", "2")))


def variacao_percentual(atual: Optional[int], anterior: Optional[int]) -> Optional[float]:
    """CU06-C3 passo 3: variação do valor de mercado em relação ao dia anterior, em %, com uma casa decimal."""
    if atual is None or not anterior:
        return None
    return round((atual - anterior) / anterior * 100, 1)


class FavoritoService:
    def __init__(self, session: Session, relogio: Callable[[], datetime] = security.agora,
                 tolerancia: timedelta = FAVORITOS_VARIACAO_TOLERANCIA):
        self.session = session
        self.relogio = relogio
        self.repositorio = FavoritoRepository(session)
        self.tolerancia = tolerancia

    def adicionar(self, id_usuario: int, item_id: int) -> FavoritoResponse:
        """CU06-C1 passos 3 a 5. FA2: o item já favoritado mantém o registro e o controle fica "Favoritado"."""
        if self.repositorio.existe(id_usuario, item_id):
            return FavoritoResponse(item_id=item_id, favorito=True)  # FA2
        try:
            self.repositorio.incluir(id_usuario, item_id, self.relogio())
            self.session.commit()
        except IntegrityError:
            self.session.rollback()  # dois cliques ao mesmo tempo: o outro pedido já registrou o item (FA2)
            return FavoritoResponse(item_id=item_id, favorito=True)
        except Exception:
            self.session.rollback()
            raise
        return FavoritoResponse(item_id=item_id, favorito=True, message=mensagens.FAVORITO_ADICIONADO)

    def remover(self, id_usuario: int, item_id: int, confirmar: bool) -> FavoritoResponse:
        """CU06-C2. FA1: com alertas do item e sem a confirmação, nada é removido (FavoritoComAlertasError); a tela pede a
        confirmação, e o FA2 (cancelada) é não confirmar. Confirmada, os alertas e o favorito saem numa única transação:
        uma falha desfaz os dois (FE1)."""
        if not confirmar and self.repositorio.quantidade_de_alertas(id_usuario, item_id) > 0:
            raise FavoritoComAlertasError()
        try:
            self.repositorio.remover(id_usuario, item_id)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return FavoritoResponse(item_id=item_id, favorito=False, message=mensagens.FAVORITO_REMOVIDO)

    def listar(self, id_usuario: int) -> FavoritosResponse:
        """CU06-C3 passos 2 a 4: os favoritos em ordem alfabética, com o valor de mercado atual (RN06), a variação em
        relação ao dia anterior, os alertas ativos e o frescor (FA2, RN09). FA1: lista vazia."""
        favoritos = self.repositorio.do_usuario(id_usuario)
        if not favoritos:
            return FavoritosResponse(itens=[], mensagem=mensagens.FAVORITOS_VAZIO)

        agora = self.relogio()
        ids = [f.item_id for f in favoritos]
        mercados = MercadoRepository(self.session)
        itens = self.repositorio.itens(ids)
        ofertas = mercados.leiloes_do_ultimo_ciclo_de_varios([i for i in ids if i != WOW_TOKEN_ID])
        alertas = self.repositorio.alertas_ativos_por_item(id_usuario)
        estados = mercados.estados()

        linhas: list[ItemFavorito] = []
        for item_id in ids:
            atual, anterior = self._valor_e_dia_anterior(item_id, ofertas.get(item_id, []), estados, mercados)
            desatualizado, _ = frescor_do_item(self.session, item_id, agora, estados)
            item = itens.get(item_id)
            linhas.append(ItemFavorito(
                item_id=item_id, name=item.name if item is not None else f"Item {item_id}",
                icon_url=item.icon_url if item is not None else None,
                market_value=atual, variacao_pct=variacao_percentual(atual, anterior),
                alertas_ativos=alertas.get(item_id, 0), desatualizado=desatualizado,
                aviso=mensagens.DADOS_DESATUALIZADOS if desatualizado else None,
            ))
        return FavoritosResponse(itens=sorted(linhas, key=lambda linha: (linha.name.casefold(), linha.item_id)))

    def _valor_e_dia_anterior(self, item_id: int, ofertas: list[tuple[int, int]], estados: list[EstadoMercado],
                              mercados: MercadoRepository) -> tuple[Optional[int], Optional[int]]:
        """O valor de mercado atual (RN06; para a Ficha do WoW, a última coleta) e o do dia anterior: o ponto do mesmo
        mercado mais próximo de 24 h antes do instante do valor atual, dentro da tolerância."""
        if item_id == WOW_TOKEN_ID:
            precos = ItemPriceRepository(self.session)
            ultimo = precos.latest(WOW_TOKEN_ID, REGIAO_DA_FICHA)
            if ultimo is None:
                return None, None
            ponto = precos.mais_proximo(WOW_TOKEN_ID, REGIAO_DA_FICHA, ultimo.created_at - UM_DIA, self.tolerancia)
            return ultimo.price_copper, ponto.price_copper if ponto is not None else None

        atual = primeiro_quartil_ponderado(ofertas) if ofertas else None
        id_reino = mercados.mercado_do_item(item_id)
        estado = next((e for e in estados if e.id_reino == id_reino), None) if id_reino is not None else None
        if atual is None or estado is None or estado.ultima_atualizacao_em is None:
            return atual, None
        instante = estado.ultima_atualizacao_em.astimezone(timezone.utc)
        return atual, mercados.valor_mais_proximo(item_id, id_reino, instante - UM_DIA, self.tolerancia)
