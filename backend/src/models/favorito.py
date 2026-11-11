"""CU06 – Manter Favoritos e CU07 – Manter Alerta (MR, seção 7.2 do TC).

A exclusão em cascata acompanha a conta (CU01-C3, RN20: `usuario` → `favorito` e `alerta_preco`) e o favorito
(CU06-C2-FA1: `favorito` → `alerta_preco`, pela chave composta usuário e item).
"""
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        String)

from src.repositories.database import Base

TIPO_COMPRA = "COMPRA"  # avisar quando o valor de mercado cair até o preço-alvo
TIPO_VENDA = "VENDA"  # avisar quando o valor de mercado subir até o preço-alvo
TIPOS_DE_ALERTA = (TIPO_COMPRA, TIPO_VENDA)

CANAL_WEB = "WEB"
CANAL_EMAIL = "EMAIL"
CANAL_AMBOS = "AMBOS"
CANAIS_DE_ALERTA = (CANAL_WEB, CANAL_EMAIL, CANAL_AMBOS)

SITUACAO_ATIVO = "ATIVO"
SITUACAO_DISPARADO = "DISPARADO"  # CU08: o gatilho foi atingido; não conta para a RN08 até ser reativado (CU07-C2-FA1)
SITUACOES_DE_ALERTA = (SITUACAO_ATIVO, SITUACAO_DISPARADO)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


class Favorito(Base):
    """CU06 / RF09: item da lista de favoritos do usuário. `item_id` é o identificador do item no WoW, o mesmo de
    `historical_item_prices`."""
    __tablename__ = "favorito"

    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True,
                        autoincrement=False)
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    data_inclusao = Column(DateTime(timezone=True), nullable=False, default=_agora)


class AlertaPreco(Base):
    """CU07 / RF05: alerta de preço de um item favorito. Preço-alvo em Cobre (RN01); a cota da RN08 conta só os
    `ATIVO`. O disparo (`DISPARADO`, `disparado_em`) é do CU08."""
    __tablename__ = "alerta_preco"

    id_alerta = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, nullable=False)
    tipo = Column(String(10), nullable=False)
    preco_alvo = Column(BigInteger, nullable=False)
    canal = Column(String(5), nullable=False)
    situacao = Column(String(9), nullable=False, default=SITUACAO_ATIVO)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    disparado_em = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["id_usuario", "item_id"], ["favorito.id_usuario", "favorito.item_id"],
                             ondelete="CASCADE", name="fk_alerta_preco_favorito"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_DE_ALERTA)})", name="ck_alerta_preco_tipo"),
        CheckConstraint(f"canal IN ({_lista_sql(CANAIS_DE_ALERTA)})", name="ck_alerta_preco_canal"),
        CheckConstraint(f"situacao IN ({_lista_sql(SITUACOES_DE_ALERTA)})", name="ck_alerta_preco_situacao"),
        Index("ix_alerta_preco_usuario_situacao", "id_usuario", "situacao"),
        Index("ix_alerta_preco_usuario_item", "id_usuario", "item_id"),
        Index("ix_alerta_preco_situacao_item", "situacao", "item_id"),  # CU08-C1 passo 2: os ativos dos itens do ciclo
    )
