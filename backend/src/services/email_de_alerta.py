"""CU08-C2 passo 2: a mensagem do e-mail de um alerta de preço atingido (Figura 18 do TC), em texto simples e em HTML."""
import os
from dataclasses import dataclass
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from src.models.favorito import TIPO_COMPRA
from src.services.moeda import formatar_moeda

FUSO_DE_BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPO_DO_ALERTA = {
    "COMPRA": "Compra (preço cair até o alvo)",
    "VENDA": "Venda (preço subir até o alvo)",
}
AVISO_DE_REATIVACAO = ('O alerta foi desativado após o disparo. Para voltar a acompanhar o preço, reative-o na seção '
                       '"Alertas de preço" da tela do item.')
RODAPE = ("Você recebeu este e-mail porque configurou um alerta de preço no Goblin Ledger com notificação por e-mail.")
TEXTO_DO_BOTAO = "Ver o item no Goblin Ledger"


@dataclass(frozen=True)
class MensagemDeEmail:
    assunto: str
    texto: str
    html: str


def endereco_do_frontend() -> str:
    """O mesmo FRONTEND_URL do link de recuperação de senha (CU02-C2)."""
    return os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def data_e_hora_de_brasilia(instante: datetime) -> str:
    """`dd/mm/aaaa às hh:mm` no horário de Brasília (o backend guarda UTC)."""
    local = instante.astimezone(FUSO_DE_BRASILIA)
    return local.strftime("%d/%m/%Y às %H:%M")


def montar_email_de_alerta(
    nome_do_item: str, item_id: int, tipo: str, preco_alvo: int, valor_mercado: int, disparada_em: datetime
) -> MensagemDeEmail:
    """CU08-C2 passo 2: o nome do item, o tipo de gatilho, o preço-alvo e o valor de mercado que o atingiu, em Ouro, Prata
    e Cobre (RN01), a data e a hora do disparo e o link para a tela de detalhes do item."""
    frontend = endereco_do_frontend()
    link = f"{frontend}/item/{item_id}"
    acao = "compra" if tipo == TIPO_COMPRA else "venda"
    linhas = [
        ("Item", nome_do_item),
        ("Tipo do alerta", TIPO_DO_ALERTA[tipo]),
        ("Preço-alvo", formatar_moeda(preco_alvo)),
        ("Valor de mercado", formatar_moeda(valor_mercado)),
        ("Data e hora", data_e_hora_de_brasilia(disparada_em)),
    ]
    assunto = f"Alerta de preço atingido – {nome_do_item}"
    frase = f"O valor de mercado do item {nome_do_item} atingiu o preço do seu alerta de {acao}."

    texto = "\n".join([
        "Seu alerta de preço foi atingido",
        "",
        f"Olá! {frase}",
        "",
        *(f"{rotulo}: {valor}" for rotulo, valor in linhas),
        "",
        f"{TEXTO_DO_BOTAO}: {link}",
        "",
        AVISO_DE_REATIVACAO,
        "",
        RODAPE,
    ])

    def linha_html(rotulo: str, valor: str) -> str:
        cor = "#B7791F" if rotulo in ("Preço-alvo", "Valor de mercado") else "#161124"
        return (
            '<tr style="border-bottom:1px solid #ECEAF2;">'
            f'<td style="padding:10px 0;color:#8A84A3;width:40%;">{escape(rotulo)}</td>'
            f'<td style="padding:10px 0;font-weight:600;color:{cor};">{escape(valor)}</td></tr>'
        )

    html = f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>{escape(assunto)}</title></head>
<body style="margin:0;background:#ECEAF2;font-family:Inter,Arial,sans-serif;">
<div style="padding:48px 12px;">
<div style="max-width:600px;margin:0 auto;background:#FFFFFF;border-radius:10px;overflow:hidden;">
<div style="background:#161124;padding:20px 28px;">
<img src="{escape(frontend)}/logo.png" alt="" width="36" height="36" style="vertical-align:middle;margin-right:12px;">
<span style="color:#FFFFFF;font-weight:700;letter-spacing:2px;vertical-align:middle;">GOBLIN LEDGER</span>
</div>
<div style="padding:28px 28px 8px;color:#2A2438;">
<h1 style="font-size:22px;margin:0 0 10px;color:#161124;font-weight:500;">Seu alerta de preço foi atingido</h1>
<p style="font-size:15px;line-height:1.6;margin:0;">Olá! O valor de mercado do item <b>{escape(nome_do_item)}</b> atingiu o preço do seu alerta de {acao}.</p>
<table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px;"><tbody>
{"".join(linha_html(rotulo, valor) for rotulo, valor in linhas)}
</tbody></table>
<a href="{escape(link)}" style="display:inline-block;background:#FBBF24;color:#161124;font-weight:700;padding:12px 22px;border-radius:8px;text-decoration:none;font-size:14px;">{TEXTO_DO_BOTAO}</a>
<p style="font-size:13px;line-height:1.6;color:#5B5570;margin:22px 0 0;">{escape(AVISO_DE_REATIVACAO)}</p>
</div>
<div style="padding:18px 28px 24px;font-size:12px;color:#8A84A3;">{escape(RODAPE)}</div>
</div>
</div>
</body>
</html>"""
    return MensagemDeEmail(assunto=assunto, texto=texto, html=html)
