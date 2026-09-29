import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.models.usuario import Sessao, TentativaLogin, TokenRecuperacao, Usuario


class UsuarioRepository:
    """Acesso a dados dos CU01 e CU02 (usuário, sessão, token de recuperação e tentativas de login)."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------ usuário (CU01)

    def buscar_por_email(self, email: str) -> Optional[Usuario]:
        return self.session.query(Usuario).filter(Usuario.email == email).first()

    def buscar_por_id(self, id_usuario: int) -> Optional[Usuario]:
        return self.session.get(Usuario, id_usuario)

    def adicionar(self, usuario: Usuario) -> None:
        """CU01-C1 passo 7. O commit fica com o serviço (que trata a violação de unicidade do e-mail)."""
        self.session.add(usuario)

    def excluir_com_dados_vinculados(self, usuario: Usuario) -> None:
        """CU01-C3 passos 5 e 6 (RN20): remove tudo que é do usuário na transação corrente. Sessões e tokens saem por
        ON DELETE CASCADE (assim como favoritos e alertas, quando existirem); as tentativas de login não têm chave
        estrangeira (valem também para e-mails sem conta) e são removidas aqui."""
        self.limpar_tentativas(usuario.email)
        self.session.delete(usuario)
        self.session.flush()

    # ------------------------------------------------------------------ sessão (CU02-C1 / C4)

    def criar_sessao(self, id_usuario: int, emitida_em: datetime, expira_em: datetime) -> Sessao:
        sessao = Sessao(id_sessao=uuid.uuid4(), id_usuario=id_usuario, emitida_em=emitida_em, expira_em=expira_em)
        self.session.add(sessao)
        return sessao

    def buscar_sessao(self, id_sessao: uuid.UUID) -> Optional[Sessao]:
        return self.session.get(Sessao, id_sessao)

    def remover_sessoes_expiradas(self, id_usuario: int, agora: datetime) -> None:
        self.session.query(Sessao).filter(Sessao.id_usuario == id_usuario, Sessao.expira_em <= agora).delete()

    # ------------------------------------------------------------------ tentativas de login (RN21)

    def bloqueio_ativo(self, email: str, agora: datetime) -> bool:
        """CU02-C1 passo 5 / FA3: o e-mail está bloqueado por excesso de tentativas malsucedidas?"""
        bloqueado_ate = (
            self.session.query(TentativaLogin.bloqueado_ate).filter(TentativaLogin.email == email).scalar()
        )
        return bloqueado_ate is not None and bloqueado_ate > agora

    def registrar_falha(self, email: str, agora: datetime, limite: int, duracao: timedelta) -> None:
        """CU02-C1-FA2 passo 2.2 (RN21): conta uma tentativa malsucedida e, ao atingir o limite, bloqueia o e-mail.
        O contador reinicia quando um bloqueio anterior já terminou. A linha fica travada durante a atualização,
        para tentativas simultâneas não perderem contagem."""
        self.session.execute(
            insert(TentativaLogin).values(email=email, falhas=0, atualizado_em=agora).on_conflict_do_nothing()
        )
        tentativa = (
            self.session.query(TentativaLogin).filter(TentativaLogin.email == email).with_for_update().one()
        )
        if tentativa.bloqueado_ate is not None and tentativa.bloqueado_ate <= agora:
            tentativa.falhas = 0
            tentativa.bloqueado_ate = None
        tentativa.falhas += 1
        tentativa.atualizado_em = agora
        if tentativa.falhas >= limite:
            tentativa.bloqueado_ate = agora + duracao

    def limpar_tentativas(self, email: str) -> None:
        """RN21: o contador é reiniciado após um login bem-sucedido."""
        self.session.query(TentativaLogin).filter(TentativaLogin.email == email).delete()

    # ------------------------------------------------------------------ recuperação de senha (CU02-C2 / C3)

    def invalidar_tokens_ativos(self, id_usuario: int, agora: datetime) -> None:
        """RN22: a emissão de um novo link invalida os anteriores ainda não utilizados."""
        self.session.execute(
            update(TokenRecuperacao)
            .where(TokenRecuperacao.id_usuario == id_usuario, TokenRecuperacao.invalidado_em.is_(None))
            .values(invalidado_em=agora)
        )

    def criar_token(self, id_usuario: int, token_hash: str, criado_em: datetime, expira_em: datetime) -> TokenRecuperacao:
        token = TokenRecuperacao(id_usuario=id_usuario, token_hash=token_hash, criado_em=criado_em, expira_em=expira_em)
        self.session.add(token)
        self.session.flush()
        return token

    def buscar_token(self, token_hash: str) -> Optional[TokenRecuperacao]:
        return self.session.query(TokenRecuperacao).filter(TokenRecuperacao.token_hash == token_hash).first()
