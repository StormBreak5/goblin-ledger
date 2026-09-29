from datetime import datetime
from typing import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.usuario import PAPEL_USUARIO, Usuario
from src.repositories.usuario_repository import UsuarioRepository
from src.services import mensagens, security, validacao
from src.services.erros import DadosInvalidosError, EmailJaCadastradoError, SenhaIncorretaError, SenhasDivergentesError


class UsuarioService:
    """CU01 – Manter Usuário (RF01): cadastrar, alterar e excluir a própria conta."""

    def __init__(self, session: Session, relogio: Callable[[], datetime] = security.agora):
        self.session = session
        self.relogio = relogio
        self.repository = UsuarioRepository(session)

    def cadastrar(self, email: str, senha: str, confirmacao_senha: str, regiao: str) -> Usuario:
        """CU01-C1: cadastra a conta.

        - FA1 (passo 4): campo vazio, e-mail inválido, senha fora da política, confirmação divergente ou região fora
          de US/EU (RN11) resultam em DadosInvalidosError com os campos a destacar.
        - FA2 (passo 5 / RN18): e-mail já cadastrado.
        """
        email = validacao.normalizar_email(email)
        regiao_normalizada = validacao.normalizar_regiao(regiao)
        campos = []
        if not validacao.email_valido(email):
            campos.append("email")
        if not validacao.senha_valida(senha):
            campos.append("senha")
        if not confirmacao_senha or confirmacao_senha != senha:
            campos.append("confirmacao_senha")
        if regiao_normalizada is None:
            campos.append("regiao")
        if campos:
            raise DadosInvalidosError(campos=campos)

        if self.repository.buscar_por_email(email) is not None:
            raise EmailJaCadastradoError()

        usuario = Usuario(
            email=email,
            senha_hash=security.gerar_hash_da_senha(senha),
            regiao=regiao_normalizada,
            role=PAPEL_USUARIO,
            data_criacao=self.relogio(),
        )
        self.repository.adicionar(usuario)
        try:
            self.session.commit()
        except IntegrityError as e:
            # Outro cadastro do mesmo e-mail venceu a corrida entre o passo 5 e o passo 7.
            self.session.rollback()
            raise EmailJaCadastradoError() from e
        except Exception:
            self.session.rollback()
            raise
        return usuario

    def alterar_dados(
        self, usuario: Usuario, regiao: str, senha_atual: str, nova_senha: str, confirmacao_nova_senha: str
    ) -> None:
        """CU01-C2: altera a região e, opcionalmente, a senha.

        - FA1: sem nenhum campo de senha preenchido, só a região é atualizada.
        - FA2 (passo 5): nova senha e confirmação divergentes.
        - FA3 (passo 6 / RN19): senha atual incorreta.
        O e-mail não pode ser alterado (RN18): esta operação nem o recebe.
        """
        regiao_normalizada = validacao.normalizar_regiao(regiao)
        troca_de_senha = any((senha_atual, nova_senha, confirmacao_nova_senha))

        campos = []
        if regiao_normalizada is None:
            campos.append("regiao")
        if troca_de_senha:
            if not senha_atual:
                campos.append("senha_atual")
            if not validacao.senha_valida(nova_senha):
                campos.append("nova_senha")
            if not confirmacao_nova_senha:
                campos.append("confirmacao_nova_senha")
        if campos:
            raise DadosInvalidosError(campos=campos)

        if troca_de_senha:
            if nova_senha != confirmacao_nova_senha:
                raise SenhasDivergentesError()
            if not security.senha_confere(senha_atual, usuario.senha_hash):
                raise SenhaIncorretaError(mensagens.SENHA_ATUAL_INCORRETA)
            usuario.senha_hash = security.gerar_hash_da_senha(nova_senha)

        usuario.regiao = regiao_normalizada
        try:
            self.session.commit()  # passo 8: em caso de falha, os dados anteriores são mantidos
        except Exception:
            self.session.rollback()
            raise

    def excluir_conta(self, usuario: Usuario, senha: str) -> None:
        """CU01-C3 (RN19 e RN20): confere a senha e remove, numa única transação, a conta e tudo que é dela.
        Qualquer falha desfaz as remoções."""
        if not senha or not security.senha_confere(senha, usuario.senha_hash):
            raise SenhaIncorretaError(mensagens.SENHA_INCORRETA_NA_EXCLUSAO)

        try:
            self.repository.excluir_com_dados_vinculados(usuario)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
