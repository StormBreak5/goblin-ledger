import logging
import os
import smtplib
from email.message import EmailMessage

from src.services.erros import EmailIndisponivelError

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SEGUNDOS = 5


class EmailService:
    """CU02-C2 passo 7: envio do e-mail de recuperação por SMTP. Em desenvolvimento usa o Mailpit do docker-compose
    (porta 1025, mensagens em http://localhost:8025); em produção, o SMTP configurado por variáveis de ambiente
    (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_STARTTLS)."""

    def enviar_link_de_recuperacao(self, destinatario: str, link: str, validade_minutos: int) -> None:
        mensagem = EmailMessage()
        mensagem["Subject"] = "Goblin Ledger - Redefinição de senha"
        mensagem["From"] = os.getenv("SMTP_FROM", "nao-responda@goblinledger.local")
        mensagem["To"] = destinatario
        mensagem.set_content(
            "Recebemos um pedido para redefinir a senha da sua conta no Goblin Ledger.\n\n"
            f"Para cadastrar uma nova senha, acesse o link abaixo (válido por {validade_minutos} minutos e de uso único):\n"
            f"{link}\n\n"
            "Se você não fez esse pedido, ignore esta mensagem: a sua senha continua a mesma."
        )

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
            logger.error(f"CU02-C2-FE1: falha ao enviar e-mail de recuperação via {host}:{port}: {e}")
            raise EmailIndisponivelError(str(e)) from e
