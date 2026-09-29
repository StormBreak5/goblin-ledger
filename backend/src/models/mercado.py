from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from src.repositories.database import Base

REGIOES_DE_MERCADO = ("US", "EU")  # RN11

# CU09-C3 passo 3 (RN04): situação do leilão.
SITUACAO_ATIVO = "ATIVO"
SITUACAO_EXPIRADO_VENDIDO = "EXPIRADO_VENDIDO"

# CU09: situação do ciclo de ingestão.
CICLO_EXECUTANDO = "EXECUTANDO"
CICLO_SUCESSO = "SUCESSO"
CICLO_FALHA = "FALHA"

ORIGEM_AGENDADO = "AGENDADO"
ORIGEM_MANUAL = "MANUAL"

# Origem de cada ponto em historical_item_prices.
ORIGEM_UNDERMINE = "UNDERMINE"
ORIGEM_BLIZZARD = "BLIZZARD"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Reino(Base):
    """CU09 (RN11): mercado monitorado (MR: Reino). `id_reino` é o id do reino conectado na Blizzard; as commodities
    de cada região são um "reino" à parte, com o id convencionado em `src.services.ingestao_config`."""
    __tablename__ = "reino"

    id_reino = Column(Integer, primary_key=True, autoincrement=False)
    nome = Column(String(45), nullable=False)
    regiao = Column(String(2), nullable=False)

    __table_args__ = (CheckConstraint("regiao IN ('US', 'EU')", name="ck_reino_regiao"),)


class Leilao(Base):
    """CU09-C3 (MR: Leilao): um leilão da Casa de Leilões, identificado pelo id da Blizzard e atualizado a cada
    ciclo. Preços em Cobre (RN01). `item_id` é o id do item no WoW, sem chave estrangeira por enquanto (como em
    historical_item_prices), até `items` ser alinhada ao MR."""
    __tablename__ = "leilao"

    id_leilao = Column(BigInteger, primary_key=True, autoincrement=True)
    id_leilao_origem = Column(BigInteger, nullable=False)
    id_reino = Column(Integer, ForeignKey("reino.id_reino"), nullable=False)
    item_id = Column(Integer, nullable=False)
    preco_bid = Column(BigInteger, nullable=True)
    preco_buyout = Column(BigInteger, nullable=True)  # total do leilão; nulo em leilões só com lance
    preco_unitario = Column(BigInteger, nullable=True)  # buyout por unidade: base do valor de mercado (RN06)
    quantidade = Column(Integer, nullable=False)
    tempo_restante = Column(String(10), nullable=True)
    situacao = Column(String(20), nullable=False, default=SITUACAO_ATIVO, server_default=SITUACAO_ATIVO)
    data_ingestao = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_reino", "id_leilao_origem", name="uq_leilao_reino_origem"),
        Index("ix_leilao_item_reino_ingestao", "item_id", "id_reino", "data_ingestao"),
        Index("ix_leilao_data_ingestao", "data_ingestao"),
        CheckConstraint("situacao IN ('ATIVO', 'EXPIRADO_VENDIDO')", name="ck_leilao_situacao"),
    )


class CicloIngestao(Base):
    """CU09-C1 / C4 (RN05): um ciclo de ingestão de um endpoint. O `iniciado_em` mais recente de cada endpoint é a
    "última requisição" usada para respeitar o intervalo mínimo de 60 minutos; também alimenta o resumo do Admin."""
    __tablename__ = "ciclo_ingestao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String(60), nullable=False)
    origem = Column(String(10), nullable=False, default=ORIGEM_AGENDADO)
    iniciado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    concluido_em = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(10), nullable=False, default=CICLO_EXECUTANDO)
    data_referencia = Column(DateTime(timezone=True), nullable=True)  # momento do snapshot (Last-Modified da Blizzard)
    leiloes_coletados = Column(Integer, nullable=False, default=0)
    leiloes_descartados = Column(Integer, nullable=False, default=0)
    itens_atualizados = Column(Integer, nullable=False, default=0)
    itens_anomalos = Column(Integer, nullable=False, default=0)
    etapa_da_falha = Column(String(20), nullable=True)
    erro = Column(Text, nullable=True)

    __table_args__ = (Index("ix_ciclo_ingestao_endpoint_inicio", "endpoint", "iniciado_em"),)


class EstadoMercado(Base):
    """CU09 (RN09 / RN14): frescor dos dados de cada mercado e a sinalização "Dados Desatualizados"."""
    __tablename__ = "estado_mercado"

    mercado = Column(String(60), primary_key=True)
    # O leilão "do último ciclo" é o que tem data_ingestao igual a ultima_atualizacao_em do seu reino.
    id_reino = Column(Integer, ForeignKey("reino.id_reino"), nullable=False, unique=True)
    ultima_atualizacao_em = Column(DateTime(timezone=True), nullable=True)
    desatualizado = Column(Boolean, nullable=False, default=False, server_default="false")
    ultima_falha_em = Column(DateTime(timezone=True), nullable=True)
