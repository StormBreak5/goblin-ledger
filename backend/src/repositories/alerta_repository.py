"""CU07 – Manter Alerta: os alertas de preço do usuário e a trava da cota (RN08)."""
from typing import Any, Optional, Sequence

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.models.favorito import SITUACAO_ATIVO, AlertaPreco


class AlertaRepository:
    def __init__(self, session: Session):
        self.session = session

    def travar_usuario(self, id_usuario: int) -> None:
        """RN08: bloqueia a linha do usuário até o fim da transação, para a contagem dos alertas ativos e a gravação não
        serem intercaladas por outro pedido do mesmo usuário (dois pedidos simultâneos não passam do limite).
        `FOR NO KEY UPDATE` (e não `FOR UPDATE`): serializa os pedidos do usuário do mesmo jeito, mas não bloqueia a
        conferência da chave estrangeira de quem grava uma notificação desse usuário (CU08-C1), o que travaria os dois
        lados quando o ciclo dispara o mesmo alerta que o usuário está salvando."""
        self.session.execute(text("SELECT id_usuario FROM usuario WHERE id_usuario = :id FOR NO KEY UPDATE"),
                             {"id": id_usuario})

    def ativos(self, id_usuario: int) -> int:
        """RN08: os alertas com a situação "Ativo" do usuário, em todos os itens."""
        return self.session.query(func.count(AlertaPreco.id_alerta)).filter(
            AlertaPreco.id_usuario == id_usuario, AlertaPreco.situacao == SITUACAO_ATIVO).scalar() or 0

    def do_item(self, id_usuario: int, item_id: int) -> Sequence[AlertaPreco]:
        """A seção "Alertas de preço" da tela do item: os alertas do usuário para o item, do mais antigo ao mais novo."""
        return (self.session.query(AlertaPreco)
                .filter(AlertaPreco.id_usuario == id_usuario, AlertaPreco.item_id == item_id)
                .order_by(AlertaPreco.criado_em, AlertaPreco.id_alerta).all())

    def do_usuario(self, id_usuario: int, id_alerta: int) -> Optional[AlertaPreco]:
        """O alerta, só se for do usuário (o de outro usuário fica invisível)."""
        return self.session.query(AlertaPreco).filter(
            AlertaPreco.id_alerta == id_alerta, AlertaPreco.id_usuario == id_usuario).one_or_none()

    def incluir(self, alerta: AlertaPreco) -> None:
        """CU07-C1 passo 7."""
        self.session.add(alerta)
        self.session.flush()

    def atualizar(self, alerta: AlertaPreco, campos: dict[str, Any]) -> None:
        """CU07-C2 passo 5."""
        for nome, valor in campos.items():
            setattr(alerta, nome, valor)
        self.session.flush()

    def remover(self, alerta: AlertaPreco) -> None:
        """CU07-C3 passo 4."""
        self.session.delete(alerta)
        self.session.flush()
