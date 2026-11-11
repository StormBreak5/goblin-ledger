"""CU05 – Consultar Previsão Preditiva: leitura das tabelas do CU11 (versão vigente, situação da projeção do item e
predições diárias) e da série diária da Undermine (preço de partida e critérios de elegibilidade)."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Sequence

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.models.mercado import Reino
from src.models.modelo import ModeloPreditivo, PredicaoDiaria, ProjecaoItem
from src.services.ingestao_config import COMMODITIES_ID_POR_REGIAO

# A série diária usada pelo modelo (RN16): só a Undermine, diária, sem os volumes anômalos (RN12), como em
# src/ml/dados.py (SQL_PRECOS).
_SERIE_DIARIA = "origem = 'UNDERMINE' AND granularidade = 'DIARIA' AND NOT anomalia"

_SERIES_DO_ITEM = text(f"""
    SELECT DISTINCT region FROM historical_item_prices
     WHERE item_id = :item_id AND {_SERIE_DIARIA} AND "timestamp" < :hoje
""")

_ULTIMO_DIA_DA_BASE = text(f"""
    SELECT max("timestamp")::date FROM historical_item_prices
     WHERE region = ANY(:series) AND {_SERIE_DIARIA} AND "timestamp" < :hoje
""")

# Um registro por dia (o menor preço e a maior quantidade do dia), como em src/ml/dados.py (padronizar_precos).
_CRITERIOS_DA_SERIE = text(f"""
    WITH diario AS (
        SELECT ("timestamp")::date AS dia, max(quantity) AS quantidade
          FROM historical_item_prices
         WHERE region = :serie AND item_id = :item_id AND {_SERIE_DIARIA} AND "timestamp" < :hoje
         GROUP BY 1
    )
    SELECT min(dia) AS primeiro_registro,
           avg(quantidade) FILTER (WHERE dia > :inicio_recente) AS quantidade_media_recente
      FROM diario
""")

_PRECO_DIARIO = text(f"""
    SELECT min(price) FROM historical_item_prices
     WHERE region = :serie AND item_id = :item_id AND {_SERIE_DIARIA}
       AND "timestamp" >= :dia AND "timestamp" < :dia_seguinte
""")


@dataclass(frozen=True)
class DadosDaSerie:
    """RN02 e RN27 de uma série do item, nos dados de hoje (sem decidir: a regra fica no serviço)."""
    serie: str
    ultimo_dia_da_base: Optional[date]
    primeiro_registro: Optional[date]
    quantidade_media_recente: Optional[float]


class ProjecaoRepository:
    def __init__(self, session: Session):
        self.session = session

    def vigente(self, regiao: str) -> Optional[ModeloPreditivo]:
        """CU05-C1 passo 2 (FA1): a versão vigente do modelo na região (só uma por região, RN26)."""
        return self.session.query(ModeloPreditivo).filter_by(regiao=regiao, vigente=True).one_or_none()

    def projecoes_do_item(self, item_id: int, regiao: str) -> Sequence[ProjecaoItem]:
        """CU05-C1 passo 2: a situação da projeção de cada série do item na região (RN10, RN13)."""
        return (self.session.query(ProjecaoItem)
                .filter(ProjecaoItem.item_id == item_id, ProjecaoItem.regiao == regiao)
                .order_by(ProjecaoItem.serie).all())

    def predicoes_mais_recentes(self, serie: str, item_id: int, versao: int) -> Sequence[PredicaoDiaria]:
        """CU05-C1 passo 3: as predições do dia de referência mais recente do item, pela versão vigente, em ordem."""
        do_item = (PredicaoDiaria.serie == serie, PredicaoDiaria.item_id == item_id, PredicaoDiaria.versao == versao)
        ultima = self.session.query(func.max(PredicaoDiaria.data_previsao)).filter(*do_item).scalar()
        if ultima is None:
            return []
        return (self.session.query(PredicaoDiaria).filter(*do_item, PredicaoDiaria.data_previsao == ultima)
                .order_by(PredicaoDiaria.data_prevista).all())

    def preco_diario(self, serie: str, item_id: int, dia: date) -> Optional[int]:
        """CU05-C1 passo 5: o preço diário de D (o menor do dia, em Cobre), a mesma base das predições do CU11-C3."""
        preco = self.session.execute(_PRECO_DIARIO, {
            "serie": serie, "item_id": item_id, "dia": dia, "dia_seguinte": dia + timedelta(days=1),
        }).scalar()
        return None if preco is None else int(preco)

    def series_da_regiao(self, regiao: str) -> list[str]:
        """RN11: as séries de uma região, como em `regiao_por_serie` (src/ml/dados.py): o id das commodities da região,
        os reinos conectados dela e o próprio código da região."""
        reinos = [str(id_reino) for (id_reino,) in self.session.query(Reino.id_reino).filter(Reino.regiao == regiao)]
        commodities = COMMODITIES_ID_POR_REGIAO.get(regiao)
        return sorted({*reinos, regiao, *([str(commodities)] if commodities is not None else [])})

    def series_do_item(self, item_id: int, regiao: str, hoje: date) -> list[str]:
        """As séries diárias do item na região, só com os dias encerrados (RN25)."""
        da_regiao = set(self.series_da_regiao(regiao))
        series = self.session.execute(_SERIES_DO_ITEM, {"item_id": item_id, "hoje": hoje}).scalars()
        return sorted(str(s) for s in series if str(s) in da_regiao)

    def dados_da_serie(self, serie: str, item_id: int, regiao: str, hoje: date, dias_recentes: int) -> DadosDaSerie:
        """CU05-C1-FA2: o que a RN02 e a RN27 olham, com as definições de `criterios_dos_itens` (src/ml/selecao.py):
        o último dia da base é o da região inteira, e não o do item."""
        fim = self.session.execute(_ULTIMO_DIA_DA_BASE, {"series": self.series_da_regiao(regiao), "hoje": hoje}).scalar()
        if fim is None:
            return DadosDaSerie(serie, None, None, None)
        linha = self.session.execute(_CRITERIOS_DA_SERIE, {
            "serie": serie, "item_id": item_id, "hoje": hoje, "inicio_recente": fim - timedelta(days=dias_recentes),
        }).one()
        media = None if linha.quantidade_media_recente is None else float(linha.quantidade_media_recente)
        return DadosDaSerie(serie, fim, linha.primeiro_registro, media)
