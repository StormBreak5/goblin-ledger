from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.cobertura import AptidaoTreinamento
from src.models.item import Item

# Maior período contínuo de cada item: os registros são reduzidos a um por dia (qualquer região, origem ou granularidade) e
# os dias separados por até `lacuna` dias sem registro pertencem ao mesmo período ("desconsiderando lacunas na série").
# Cada "ilha" é um período; vence a mais longa (e, no empate, a mais recente).
_PERIODOS = text(
    """
    WITH dias AS (
        SELECT item_id, timestamp::date AS dia
        FROM historical_item_prices
        WHERE item_id = ANY(:ids)
        GROUP BY item_id, timestamp::date
    ), marcados AS (
        SELECT item_id, dia,
               CASE WHEN dia - lag(dia) OVER (PARTITION BY item_id ORDER BY dia) <= :lacuna + 1 THEN 0 ELSE 1 END AS novo
        FROM dias
    ), grupos AS (
        SELECT item_id, dia, sum(novo) OVER (PARTITION BY item_id ORDER BY dia) AS grupo
        FROM marcados
    ), periodos AS (
        SELECT item_id, grupo, min(dia) AS inicio, max(dia) AS fim, count(*) AS dias_com_dados
        FROM grupos
        GROUP BY item_id, grupo
    )
    SELECT DISTINCT ON (item_id) item_id, inicio, fim, (fim - inicio + 1) AS periodo_dias, dias_com_dados
    FROM periodos
    ORDER BY item_id, (fim - inicio) DESC, inicio DESC
    """
)

ID_MAXIMO_DE_ITEM = 2_147_483_647


@dataclass(frozen=True)
class PeriodoDoItem:
    """O maior período contínuo de registros de um item (CU10-C3 passo 3)."""
    item_id: int
    inicio: date
    fim: date
    periodo_dias: int
    dias_com_dados: int


@dataclass(frozen=True)
class AptidaoDoItem:
    item_id: int
    nome: Optional[str]
    apto: bool
    periodo_continuo_dias: int
    inicio_periodo: Optional[date]
    fim_periodo: Optional[date]
    dias_com_dados: int
    validado_em: datetime


class CoberturaRepository:
    """Acesso a dados do CU10-C3: períodos contínuos do histórico e o resultado da validação de cada item."""

    def __init__(self, session: Session):
        self.session = session

    def itens_ativos(self, excluir: Sequence[int] = ()) -> dict[int, str]:
        """CU10-C3 passo 2: os itens do WoW ativos (id no jogo -> nome). Só os de identificador numérico."""
        itens: dict[int, str] = {}
        consulta = self.session.query(Item.external_item_id, Item.name).filter(Item.game == "wow", Item.is_active.is_(True))
        for external_item_id, nome in consulta:
            if external_item_id.isdigit() and int(external_item_id) <= ID_MAXIMO_DE_ITEM and int(external_item_id) not in excluir:
                itens[int(external_item_id)] = nome
        return itens

    def periodos_continuos(self, ids: Sequence[int], lacuna_maxima_dias: int) -> dict[int, PeriodoDoItem]:
        """CU10-C3 passos 2 e 3: o maior período contínuo de registros de cada item que tenha algum. Falha de banco propaga."""
        if not ids:
            return {}
        linhas = self.session.execute(_PERIODOS, {"ids": list(ids), "lacuna": lacuna_maxima_dias})
        return {
            linha.item_id: PeriodoDoItem(linha.item_id, linha.inicio, linha.fim, linha.periodo_dias, linha.dias_com_dados)
            for linha in linhas
        }

    def substituir_resultado(self, aptidoes: Sequence[AptidaoTreinamento]) -> None:
        """CU10-C3 passos 5 e 6: grava a classificação de cada item no lugar da anterior. Não confirma a transação: se
        algo falhar no meio, o resultado anterior continua valendo."""
        self.session.query(AptidaoTreinamento).delete(synchronize_session=False)
        self.session.add_all(aptidoes)
        self.session.flush()

    def resultado(
        self, apto: Optional[bool], deslocamento: int, limite: int
    ) -> tuple[int, int, int, Optional[datetime], list[AptidaoDoItem]]:
        """A última validação: (total, aptos, inaptos, momento da validação, página de itens). Os itens vêm do maior
        período para o menor; o total e os aptos valem para a validação inteira, e não só para o filtro."""
        totais = self.session.execute(
            text("SELECT count(*), count(*) FILTER (WHERE apto), max(validado_em) FROM aptidao_treinamento")
        ).one()
        consulta = self.session.query(AptidaoTreinamento)
        if apto is not None:
            consulta = consulta.filter(AptidaoTreinamento.apto.is_(apto))
        aptidoes = (
            consulta.order_by(AptidaoTreinamento.periodo_continuo_dias.desc(), AptidaoTreinamento.item_id)
            .offset(deslocamento)
            .limit(limite)
            .all()
        )
        nomes = self._nomes([aptidao.item_id for aptidao in aptidoes])
        itens = [
            AptidaoDoItem(
                a.item_id, nomes.get(a.item_id), a.apto, a.periodo_continuo_dias, a.inicio_periodo, a.fim_periodo,
                a.dias_com_dados, a.validado_em,
            )
            for a in aptidoes
        ]
        total, aptos, validado_em = totais[0], totais[1], totais[2]
        return total, aptos, total - aptos, validado_em, itens

    def _nomes(self, ids: Sequence[int]) -> dict[int, str]:
        if not ids:
            return {}
        textos = [str(item_id) for item_id in ids]
        linhas = self.session.query(Item.external_item_id, Item.name).filter(Item.game == "wow", Item.external_item_id.in_(textos))
        return {int(external_item_id): nome for external_item_id, nome in linhas if external_item_id.isdigit()}
