from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Index, Integer, String, Text, UniqueConstraint

from src.repositories.database import Base

# CU10-C2 (RN17): tipo do evento. Patches e expansões são o que o documento exige; os demais são as datas que também
# mexem nos preços dos itens (temporadas, eventos sazonais e as rotinas semanais e mensais do jogo).
TIPO_EXPANSAO = "EXPANSAO"
TIPO_PATCH = "PATCH"
TIPO_TEMPORADA = "TEMPORADA"
TIPO_EVENTO_SAZONAL = "EVENTO_SAZONAL"
TIPO_RECORRENTE = "RECORRENTE"
TIPO_OUTRO = "OUTRO"
TIPOS_DE_EVENTO = (TIPO_EXPANSAO, TIPO_PATCH, TIPO_TEMPORADA, TIPO_EVENTO_SAZONAL, TIPO_RECORRENTE, TIPO_OUTRO)

# Região a que o evento se aplica: as duas regiões do sistema (RN11) ou as duas.
REGIAO_GLOBAL = "GLOBAL"
REGIOES_DE_EVENTO = ("US", "EU", REGIAO_GLOBAL)

# De onde o evento veio.
ORIGEM_WIKIPEDIA = "WIKIPEDIA"
ORIGEM_WARCRAFT_WIKI = "WARCRAFT_WIKI"
ORIGEM_API_BLIZZARD = "API_BLIZZARD"
ORIGEM_REGRA = "REGRA"  # gerado por uma regra de data (reinício semanal, Feira de Negrilua, Posto de Troca)
ORIGEM_MANUAL_EVENTO = "MANUAL"
ORIGENS_DE_EVENTO = (
    ORIGEM_WIKIPEDIA, ORIGEM_WARCRAFT_WIKI, ORIGEM_API_BLIZZARD, ORIGEM_REGRA, ORIGEM_MANUAL_EVENTO,
)

EXTRACAO_SUCESSO = "SUCESSO"
EXTRACAO_FALHA = "FALHA"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


class EventoJogo(Base):
    """CU10-C2 (RN17): um evento do jogo com data que pode influenciar os preços. O CU11 lê o tipo e a data como
    variáveis categóricas. Não consta no MR do TC (o documento traz só a necessidade)."""
    __tablename__ = "evento_jogo"

    id_evento = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(20), nullable=False)
    nome = Column(String(150), nullable=False)
    versao = Column(String(20), nullable=True)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=True)
    regiao = Column(String(6), nullable=False, default=REGIAO_GLOBAL, server_default=REGIAO_GLOBAL)
    origem = Column(String(15), nullable=False)
    fonte = Column(String(255), nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)

    __table_args__ = (
        UniqueConstraint("tipo", "nome", "data_inicio", "regiao", name="uq_evento_jogo"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_DE_EVENTO)})", name="ck_evento_jogo_tipo"),
        CheckConstraint(f"regiao IN ({_lista_sql(REGIOES_DE_EVENTO)})", name="ck_evento_jogo_regiao"),
        CheckConstraint(f"origem IN ({_lista_sql(ORIGENS_DE_EVENTO)})", name="ck_evento_jogo_origem"),
        CheckConstraint("data_fim IS NULL OR data_fim >= data_inicio", name="ck_evento_jogo_periodo"),
        Index("ix_evento_jogo_data_inicio", "data_inicio"),
    )


class ExtracaoEvento(Base):
    """CU10-C2: registro de cada extração de eventos (o "log" do documento). Também limita a frequência com que a
    mesma página é lida."""
    __tablename__ = "extracao_evento"

    id_extracao = Column(Integer, primary_key=True, autoincrement=True)
    fonte = Column(String(20), nullable=False)
    url = Column(String(500), nullable=True)
    iniciada_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    concluida_em = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(10), nullable=False)
    eventos_encontrados = Column(Integer, nullable=False, default=0)
    eventos_registrados = Column(Integer, nullable=False, default=0)
    eventos_ignorados = Column(Integer, nullable=False, default=0)
    erro = Column(Text, nullable=True)

    __table_args__ = (Index("ix_extracao_evento_fonte_inicio", "fonte", "iniciada_em"),)
