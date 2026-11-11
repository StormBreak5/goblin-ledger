"""CU08 – Manter Notificações: os alertas a verificar, o disparo único (RN07), as notificações e o envio por e-mail."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from src.models.favorito import CANAL_AMBOS, CANAL_WEB, SITUACAO_ATIVO, SITUACAO_DISPARADO, AlertaPreco
from src.models.notificacao import ENVIO_PENDENTE, Notificacao
from src.models.usuario import Usuario

CANAIS_DA_TELA = (CANAL_WEB, CANAL_AMBOS)  # C3: as notificações exibidas no sino


@dataclass(frozen=True)
class PendenteDeEnvio:
    """CU08-C2 passo 1: uma notificação com e-mail ainda não enviada, com o destinatário (RN18)."""
    id_notificacao: int
    tentativas: int
    email: str
    item_id: int
    tipo: str
    preco_alvo: int
    valor_mercado: int
    disparada_em: datetime


class NotificacaoRepository:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------ C1

    def alertas_ativos_dos_itens(self, item_ids: Sequence[int]) -> list[AlertaPreco]:
        """CU08-C1 passo 2: os alertas "Ativo" dos itens do ciclo, em ordem de id (a mesma ordem de travamento em ciclos
        simultâneos)."""
        if not item_ids:
            return []
        return (self.session.query(AlertaPreco)
                .filter(AlertaPreco.situacao == SITUACAO_ATIVO, AlertaPreco.item_id.in_(list(item_ids)))
                .order_by(AlertaPreco.id_alerta).all())

    def disparar(self, alerta: AlertaPreco, agora: datetime) -> Optional[str]:
        """CU08-C1 passo 6 (RN07, disparo único): "Ativo" → "Disparado" só se o alerta ainda estiver ativo e com o tipo e o
        preço-alvo verificados. Devolve o canal, ou None se outro ciclo já o disparou ou o usuário o alterou nesse meio
        tempo (CU07-C2): nesse caso não há notificação. Um ciclo simultâneo fica bloqueado nesta linha até o fim desta
        transação e, depois, não a altera."""
        resultado = self.session.execute(
            update(AlertaPreco)
            .where(
                AlertaPreco.id_alerta == alerta.id_alerta,
                AlertaPreco.situacao == SITUACAO_ATIVO,
                AlertaPreco.tipo == alerta.tipo,
                AlertaPreco.preco_alvo == alerta.preco_alvo,
            )
            .values(situacao=SITUACAO_DISPARADO, disparado_em=agora)
            .returning(AlertaPreco.canal)
            .execution_options(synchronize_session=False)
        ).first()
        return None if resultado is None else resultado[0]

    def registrar(self, notificacao: Notificacao) -> None:
        """CU08-C1 passo 5."""
        self.session.add(notificacao)
        self.session.flush()

    # ------------------------------------------------------------------ C2

    def pendentes_de_envio(self) -> list[PendenteDeEnvio]:
        """CU08-C2 passo 1: as notificações com e-mail ainda não enviadas, inclusive as de ciclos anteriores, com o e-mail
        cadastrado do usuário (RN18)."""
        linhas = (
            self.session.query(Notificacao, Usuario.email)
            .join(Usuario, Usuario.id_usuario == Notificacao.id_usuario)
            .filter(Notificacao.envio_email == ENVIO_PENDENTE)
            .order_by(Notificacao.id_notificacao)
            .all()
        )
        return [
            PendenteDeEnvio(
                id_notificacao=n.id_notificacao, tentativas=n.tentativas_email, email=email, item_id=n.item_id, tipo=n.tipo,
                preco_alvo=int(n.preco_alvo), valor_mercado=int(n.valor_mercado), disparada_em=n.disparada_em,
            )
            for n, email in linhas
        ]

    def travar_pendente(self, id_notificacao: int, tentativas: int) -> Optional[Notificacao]:
        """CU08-C2: trava a notificação até o fim da transação, se ela continuar pendente e com as tentativas lidas no passo
        1. None se outra rotina já a pegou (sem e-mail duplicado nem duas tentativas na mesma rodada)."""
        return (self.session.query(Notificacao)
                .filter(Notificacao.id_notificacao == id_notificacao, Notificacao.envio_email == ENVIO_PENDENTE,
                        Notificacao.tentativas_email == tentativas)
                .with_for_update(skip_locked=True)
                .one_or_none())

    # ------------------------------------------------------------------ C3

    def nao_lidas(self, id_usuario: int) -> int:
        """CU08-C3 passo 1: as notificações da tela ainda não lidas."""
        return self.session.query(func.count(Notificacao.id_notificacao)).filter(
            Notificacao.id_usuario == id_usuario, Notificacao.canal.in_(CANAIS_DA_TELA),
            Notificacao.lida_em.is_(None)).scalar() or 0

    def da_tela(self, id_usuario: int) -> list[Notificacao]:
        """CU08-C3 passo 3: as notificações do usuário com o canal tela, da mais recente para a mais antiga."""
        return (self.session.query(Notificacao)
                .filter(Notificacao.id_usuario == id_usuario, Notificacao.canal.in_(CANAIS_DA_TELA))
                .order_by(Notificacao.disparada_em.desc(), Notificacao.id_notificacao.desc()).all())

    def marcar_lidas(self, id_usuario: int, ids: Sequence[int], agora: datetime) -> int:
        """CU08-C3 passo 5: marca como lidas as notificações exibidas, só as do próprio usuário e ainda não lidas."""
        if not ids:
            return 0
        return self.session.query(Notificacao).filter(
            Notificacao.id_usuario == id_usuario, Notificacao.id_notificacao.in_(list(ids)),
            Notificacao.canal.in_(CANAIS_DA_TELA), Notificacao.lida_em.is_(None),
        ).update({Notificacao.lida_em: agora}, synchronize_session=False)
