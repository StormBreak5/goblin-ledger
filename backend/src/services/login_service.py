import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.models.usuario import Usuario
from src.repositories.usuario_repository import UsuarioRepository
from src.services import security, validacao
from src.services.email_service import EmailService
from src.services.erros import (
    ContaBloqueadaError,
    CredenciaisInvalidasError,
    DadosInvalidosError,
    EmailIndisponivelError,
    EmailInvalidoError,
    LinkInvalidoError,
    SenhasDivergentesError,
    SessaoInvalidaError,
)

logger = logging.getLogger(__name__)

MAX_TENTATIVAS_MALSUCEDIDAS = 5  # RN21
DURACAO_DO_BLOQUEIO = timedelta(minutes=15)  # RN21
VALIDADE_DO_LINK = timedelta(minutes=10)  # RN22


class ServicoDeEmailIndisponivelError(Exception):
    """CU02-C2-FE1: o e-mail de recuperação não pôde ser enviado (o token já foi invalidado)."""


@dataclass
class SessaoIniciada:
    token: str
    expira_em: datetime
    usuario: Usuario


class LoginService:
    """CU02 – Realizar Login (RF01): autenticar, recuperar e redefinir a senha e encerrar a sessão."""

    def __init__(
        self,
        session: Session,
        relogio: Callable[[], datetime] = security.agora,
        email_service: Optional[EmailService] = None,
    ):
        self.session = session
        self.relogio = relogio
        self.email_service = email_service or EmailService()
        self.repository = UsuarioRepository(session)

    # ------------------------------------------------------------------ CU02-C1: autenticar

    def autenticar(self, email: str, senha: str) -> SessaoIniciada:
        """CU02-C1: autentica o usuário e inicia a sessão (JWT de 24 h).

        - FA1 (passo 4): campo vazio ou e-mail em formato inválido.
        - FA3 (passo 5 / RN21): conta com bloqueio temporário ativo.
        - FA2 (passos 5 e 6): e-mail sem conta ou senha incorreta resultam na mesma resposta genérica, e a tentativa
          malsucedida é registrada.
        """
        email = validacao.normalizar_email(email)
        campos = []
        if not validacao.email_valido(email):
            campos.append("email")
        if not senha:
            campos.append("senha")
        if campos:
            raise DadosInvalidosError(campos=campos)

        agora = self.relogio()
        try:
            if self.repository.bloqueio_ativo(email, agora):
                raise ContaBloqueadaError()

            usuario = self.repository.buscar_por_email(email)
            if usuario is None:
                security.gastar_tempo_de_verificacao(senha)
            elif security.senha_confere(senha, usuario.senha_hash):
                return self._iniciar_sessao(usuario, agora)

            self.repository.registrar_falha(email, agora, MAX_TENTATIVAS_MALSUCEDIDAS, DURACAO_DO_BLOQUEIO)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        raise CredenciaisInvalidasError()

    def _iniciar_sessao(self, usuario: Usuario, agora: datetime) -> SessaoIniciada:
        """CU02-C1 passo 7. Reinicia o contador de tentativas (RN21)."""
        self.repository.limpar_tentativas(usuario.email)
        self.repository.remover_sessoes_expiradas(usuario.id_usuario, agora)
        sessao = self.repository.criar_sessao(usuario.id_usuario, agora, agora + security.DURACAO_DA_SESSAO)
        self.session.commit()
        token = security.emitir_token(usuario.id_usuario, sessao.id_sessao, sessao.emitida_em, sessao.expira_em)
        return SessaoIniciada(token=token, expira_em=sessao.expira_em, usuario=usuario)

    # ------------------------------------------------------------------ CU02-C4: sessão

    def usuario_da_sessao(self, token: Optional[str]) -> Usuario:
        """Identifica o usuário do token nas rotas autenticadas. Token ausente, adulterado, expirado (24 h) ou de
        sessão encerrada resulta em SessaoInvalidaError (CU02-C4-FA1)."""
        conteudo = security.ler_token(token) if token else None
        if conteudo is None:
            raise SessaoInvalidaError()
        try:
            sessao = self.repository.buscar_sessao(_como_uuid(conteudo.get("jti")))
        except ValueError:
            raise SessaoInvalidaError()
        if sessao is None or sessao.revogada_em is not None or sessao.expira_em <= self.relogio():
            raise SessaoInvalidaError()
        usuario = self.repository.buscar_por_id(sessao.id_usuario)
        if usuario is None:
            raise SessaoInvalidaError()
        return usuario

    def encerrar_sessao(self, token: Optional[str]) -> None:
        """CU02-C4 passo 2: invalida a sessão. Encerrar uma sessão que já não vale (expirada ou desconhecida) não é
        erro: o resultado, a sessão inválida, é o mesmo."""
        conteudo = security.ler_token(token) if token else None
        if conteudo is None:
            return
        try:
            sessao = self.repository.buscar_sessao(_como_uuid(conteudo.get("jti")))
        except ValueError:
            return
        if sessao is not None and sessao.revogada_em is None:
            sessao.revogada_em = self.relogio()
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise

    # ------------------------------------------------------------------ CU02-C2: solicitar recuperação

    def solicitar_recuperacao(self, email: str, url_base_do_link: str) -> None:
        """CU02-C2: gera o token de recuperação e envia o link. O resultado é o mesmo para e-mail cadastrado e não
        cadastrado (FA2), para não revelar quem tem conta.

        - FA1 (passo 4): e-mail em formato inválido.
        - FE1 (passo 7): falha no envio invalida o token e levanta ServicoDeEmailIndisponivelError.
        """
        email = validacao.normalizar_email(email)
        if not validacao.email_valido(email):
            raise EmailInvalidoError()

        usuario = self.repository.buscar_por_email(email)
        if usuario is None:
            return  # FA2: não gera token nem envia mensagem

        agora = self.relogio()
        token = security.gerar_token_de_recuperacao()
        try:
            self.repository.invalidar_tokens_ativos(usuario.id_usuario, agora)  # RN22
            registro = self.repository.criar_token(
                usuario.id_usuario, security.hash_do_token(token), agora, agora + VALIDADE_DO_LINK
            )
            self.session.commit()  # o link só é enviado depois que o token existe no banco
        except Exception:
            self.session.rollback()
            raise

        link = f"{url_base_do_link.rstrip('/')}/redefinir-senha?token={token}"
        try:
            self.email_service.enviar_link_de_recuperacao(usuario.email, link, int(VALIDADE_DO_LINK.total_seconds() // 60))
        except EmailIndisponivelError as e:
            registro.invalidado_em = self.relogio()
            self.session.commit()
            raise ServicoDeEmailIndisponivelError() from e

    # ------------------------------------------------------------------ CU02-C3: redefinir senha

    def validar_token_de_recuperacao(self, token: str):
        """CU02-C3 passo 2 (RN22): o token existe, está dentro do prazo e ainda não foi usado ou substituído?
        Caso contrário, LinkInvalidoError (FA1)."""
        registro = self.repository.buscar_token(security.hash_do_token(token)) if token else None
        if registro is None or registro.invalidado_em is not None or registro.expira_em <= self.relogio():
            raise LinkInvalidoError()
        return registro

    def redefinir_senha(self, token: str, nova_senha: str, confirmacao_nova_senha: str) -> None:
        """CU02-C3: cadastra a nova senha e invalida o token (uso único).

        - FA1 (passo 2): link inválido, expirado ou já utilizado (verificado antes de qualquer outra coisa).
        - FA2 (passo 5): nova senha e confirmação divergentes.
        - FE1 (passo 7): falha de banco mantém a senha anterior e o token válido (uma única transação).
        """
        registro = self.validar_token_de_recuperacao(token)

        campos = []
        if not validacao.senha_valida(nova_senha):
            campos.append("nova_senha")
        if not confirmacao_nova_senha:
            campos.append("confirmacao_nova_senha")
        if campos:
            raise DadosInvalidosError(campos=campos)
        if nova_senha != confirmacao_nova_senha:
            raise SenhasDivergentesError()

        try:
            usuario = self.repository.buscar_por_id(registro.id_usuario)
            usuario.senha_hash = security.gerar_hash_da_senha(nova_senha)
            registro.invalidado_em = self.relogio()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


def _como_uuid(valor) -> uuid.UUID:
    return uuid.UUID(str(valor))


def url_do_frontend() -> str:
    """Endereço do frontend usado no link do e-mail de recuperação (FRONTEND_URL)."""
    return os.getenv("FRONTEND_URL", "http://localhost:3000")
