import logging
import os
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

from src.services.erros import EmailIndisponivelError

if TYPE_CHECKING:
    from src.services.email_de_alerta import MensagemDeEmail

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SEGUNDOS = 5


class EmailService:
    """Envio de e-mail por SMTP: o link de recuperação de senha (CU02-C2 passo 7) e a notificação de alerta de preço
    atingido (CU08-C2 passo 3). Em desenvolvimento usa o Mailpit do docker-compose (porta 1025, mensagens em
    http://localhost:8025); em produção, o SMTP configurado por variáveis de ambiente (SMTP_HOST, SMTP_PORT, SMTP_USER,
    SMTP_PASSWORD, SMTP_FROM, SMTP_STARTTLS)."""

    def enviar_link_de_recuperacao(self, destinatario: str, link: str, validade_minutos: int) -> None:
        mensagem = self._mensagem(destinatario, "Goblin Ledger - Redefinição de senha")
        mensagem.set_content(
            "Recebemos um pedido para redefinir a senha da sua conta no Goblin Ledger.\n\n"
            f"Para cadastrar uma nova senha, acesse o link abaixo (válido por {validade_minutos} minutos e de uso único):\n"
            f"{link}\n\n"
            "Se você não fez esse pedido, ignore esta mensagem: a sua senha continua a mesma."
        )
        try:
            self._enviar(mensagem)
        except EmailIndisponivelError as e:
            logger.error(f"CU02-C2-FE1: falha ao enviar e-mail de recuperação via {self._servidor()}: {e}")
            raise

    def enviar_notificacao_de_alerta(self, destinatario: str, conteudo: "MensagemDeEmail") -> None:
        """CU08-C2 passo 3: envia ao e-mail cadastrado do usuário (RN18) a notificação do alerta atingido, em texto simples
        e em HTML. Levanta EmailIndisponivelError se o servidor não aceitar a mensagem (C2-FA1)."""
        mensagem = self._mensagem(destinatario, conteudo.assunto)
        mensagem.set_content(conteudo.texto)
        mensagem.add_alternative(conteudo.html, subtype="html")
        self._enviar(mensagem)

    @staticmethod
    def _mensagem(destinatario: str, assunto: str) -> EmailMessage:
        mensagem = EmailMessage()
        mensagem["Subject"] = assunto
        mensagem["From"] = os.getenv("SMTP_FROM", "nao-responda@goblinledger.local")
        mensagem["To"] = destinatario
        return mensagem

    @staticmethod
    def _servidor() -> str:
        return f"{os.getenv('SMTP_HOST', 'localhost')}:{os.getenv('SMTP_PORT', '1025')}"

    @staticmethod
    def _enviar(mensagem: EmailMessage) -> None:
        """A configuração SMTP comum aos dois e-mails."""
        host = os.getenv("SMTP_HOST", "localhost")
        port = int(os.getenv("SMTP_PORT", "1025"))
        try:
            with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SEGUNDOS) as smtp:
                if os.getenv("SMTP_STARTTLS", "false").lower() == "true":
                    smtp.starttls()
                usuario = os.getenv("SMTP_USER")
                if usuario:
                    smtp.login(usuario, os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(mensagem)
        except (OSError, smtplib.SMTPException) as e:
            raise EmailIndisponivelError(str(e)) from e
