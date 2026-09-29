from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Integer

from src.repositories.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class AptidaoTreinamento(Base):
    """CU10-C3 (RN15): resultado da validação de cobertura histórica de cada item. O CU11 só libera o treinamento
    inicial dos itens com `apto`. `item_id` é o identificador do item no WoW, como em historical_item_prices. Não
    consta no MR do TC."""
    __tablename__ = "aptidao_treinamento"

    item_id = Column(Integer, primary_key=True, autoincrement=False)
    apto = Column(Boolean, nullable=False)
    periodo_continuo_dias = Column(Integer, nullable=False)
    inicio_periodo = Column(Date, nullable=True)
    fim_periodo = Column(Date, nullable=True)
    dias_com_dados = Column(Integer, nullable=False)
    validado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
