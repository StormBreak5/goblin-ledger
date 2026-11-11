"""CU06 – Manter Favoritos: a lista de favoritos do usuário e os alertas de preço ligados a ela."""
from datetime import datetime
from typing import Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.favorito import SITUACAO_ATIVO, AlertaPreco, Favorito
from src.models.item import Item


class FavoritoRepository:
    def __init__(self, session: Session):
        self.session = session

    def existe(self, id_usuario: int, item_id: int) -> bool:
        """CU06-C1 passo 3 / CU07-C1 passo 2: o item está na lista de favoritos do usuário."""
        return self.session.get(Favorito, (id_usuario, item_id)) is not None

    def incluir(self, id_usuario: int, item_id: int, agora: datetime) -> None:
        """CU06-C1 passo 4."""
        self.session.add(Favorito(id_usuario=id_usuario, item_id=item_id, data_inclusao=agora))
        self.session.flush()

    def quantidade_de_alertas(self, id_usuario: int, item_id: int) -> int:
        """CU06-C2 passo 2: os alertas de preço do usuário para o item, ativos ou disparados."""
        return self.session.query(func.count(AlertaPreco.id_alerta)).filter(
            AlertaPreco.id_usuario == id_usuario, AlertaPreco.item_id == item_id).scalar() or 0

    def remover(self, id_usuario: int, item_id: int) -> None:
        """CU06-C2 passos 3 e 1.4: os alertas do item e o favorito, na transação corrente (o FE1 desfaz os dois). Os alertas
        sairiam pela cascata da chave composta; a exclusão explícita deixa o passo 1.4 visível."""
        self.session.query(AlertaPreco).filter(
            AlertaPreco.id_usuario == id_usuario, AlertaPreco.item_id == item_id).delete(synchronize_session=False)
        self.session.query(Favorito).filter(
            Favorito.id_usuario == id_usuario, Favorito.item_id == item_id).delete(synchronize_session=False)
        self.session.flush()

    def do_usuario(self, id_usuario: int) -> Sequence[Favorito]:
        """CU06-C3 passo 2."""
        return self.session.query(Favorito).filter(Favorito.id_usuario == id_usuario).all()

    def itens(self, item_ids: Sequence[int]) -> dict[int, Item]:
        """CU06-C3 passo 4: nome e ícone dos itens (o cadastro guarda o identificador como texto)."""
        if not item_ids:
            return {}
        itens = self.session.query(Item).filter(Item.external_item_id.in_([str(i) for i in item_ids])).all()
        return {int(item.external_item_id): item for item in itens}

    def alertas_ativos_por_item(self, id_usuario: int) -> dict[int, int]:
        """CU06-C3 passo 3: a quantidade de alertas com a situação "Ativo" de cada item do usuário."""
        linhas = (
            self.session.query(AlertaPreco.item_id, func.count(AlertaPreco.id_alerta))
            .filter(AlertaPreco.id_usuario == id_usuario, AlertaPreco.situacao == SITUACAO_ATIVO)
            .group_by(AlertaPreco.item_id)
            .all()
        )
        return {int(item_id): int(quantidade) for item_id, quantidade in linhas}
