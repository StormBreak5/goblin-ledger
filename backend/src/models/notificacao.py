"""CU08 – Manter Notificações (MR, seção 7.2 do TC).

A notificação guarda os dados do disparo e continua no histórico do usuário quando o alerta é excluído (CU07-C3) ou o
favorito é removido (CU06-C2): `id_alerta` vira nulo (`ON DELETE SET NULL`). Sai com a conta (CU01-C3, RN20).
"""
from sqlalchemy import (BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String,
                        text)

from src.models.favorito import CANAIS_DE_ALERTA, CANAL_WEB, TIPOS_DE_ALERTA
from src.repositories.database import Base

# CU08-C2: situação do envio por e-mail (nula quando o canal é só a tela).
ENVIO_PENDENTE = "PENDENTE"
ENVIO_ENVIADO = "ENVIADO"
ENVIO_FALHOU = "FALHOU"  # C2-FA1: após a última tentativa sem sucesso
SITUACOES_DE_ENVIO = (ENVIO_PENDENTE, ENVIO_ENVIADO, ENVIO_FALHOU)


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


class Notificacao(Base):
    """CU08 / RF06: o disparo de um alerta de preço (C1), o envio por e-mail (C2) e a leitura pela tela (C3). Preço-alvo e
    valor de mercado em Cobre (RN01)."""
    __tablename__ = "notificacao"

    id_notificacao = Column(Integer, primary_key=True, autoincrement=True)
    id_alerta = Column(Integer, ForeignKey("alerta_preco.id_alerta", ondelete="SET NULL"), nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, nullable=False)
    tipo = Column(String(10), nullable=False)
    preco_alvo = Column(BigInteger, nullable=False)
    valor_mercado = Column(BigInteger, nullable=False)  # o valor de mercado (RN06) que atingiu o alvo
    canal = Column(String(20), nullable=False)
    disparada_em = Column(DateTime(timezone=True), nullable=False)
    lida_em = Column(DateTime(timezone=True), nullable=True)
    envio_email = Column(String(8), nullable=True)
    tentativas_email = Column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    enviada_em = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_DE_ALERTA)})", name="ck_notificacao_tipo"),
        CheckConstraint(f"canal IN ({_lista_sql(CANAIS_DE_ALERTA)})", name="ck_notificacao_canal"),
        CheckConstraint(f"envio_email IN ({_lista_sql(SITUACOES_DE_ENVIO)})", name="ck_notificacao_envio_email"),
        # Só a tela não tem envio por e-mail; os canais com e-mail sempre têm.
        CheckConstraint(f"(canal = '{CANAL_WEB}') = (envio_email IS NULL)", name="ck_notificacao_envio_do_canal"),
        Index("ix_notificacao_usuario_disparada", "id_usuario", "disparada_em"),  # C3
        Index("ix_notificacao_envio_pendente", "id_notificacao",
              postgresql_where=text(f"envio_email = '{ENVIO_PENDENTE}'")),  # C2 passo 1
    )
