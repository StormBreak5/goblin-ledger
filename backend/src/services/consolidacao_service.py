"""CU11-C3 – Consolidar predições diárias: a parte que não precisa de pandas nem do TensorFlow.

- passo 2: a espera pela importação diária do worker (a consolidação não importa nada);
- passos 3 a 6 e FA2: o snapshot do dia (valor real e erro de cada predição, "N/D" sem valor real, RN13);
- FA3 (RN13): o bloqueio por degradação;
- FE1: os dias ainda não consolidados e o registro de cada dia em `consolidacao_diaria`.

O passo 7 (as previsões dos próximos 7 dias) está em src/ml/previsao.py, e a orquestração, com a transação de cada dia
e o FA4, em src/ml/consolidacao.py, que roda no serviço `modelo`.
"""
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from sqlalchemy import func, text, tuple_, update
from sqlalchemy.orm import Session

from src.ml.configuracao import ConfigModelo
from src.models.modelo import (IMPORTACAO_CONCLUIDA, IMPORTACAO_EM_ANDAMENTO, IMPORTACAO_FALHA, IMPORTACAO_NAO_RODOU,
                               MOTIVO_DEGRADACAO, SITUACAO_BLOQUEADA, SITUACAO_LIBERADA, STATUS_SUCESSO,
                               ConsolidacaoDiaria, ModeloPreditivo, ProjecaoItem)
from src.scraper.models import DISPARO_DIARIA, DISPARO_RECUPERACAO, ExecutionStatus, ScraperExecutionLog
from src.services import security

logger = logging.getLogger(__name__)

INTERVALO_DA_ESPERA_SEGUNDOS = 30.0


@dataclass(frozen=True)
class EstadoDaImportacao:
    """CU11-C3 passo 2: o que a consolidação encontrou da importação diária de hoje."""
    situacao: str
    aviso: Optional[str] = None


# Preço diário consolidado do dia: o mesmo registro que o modelo usa (série diária da Undermine, sem anomalia, RN16).
PRECO_REAL_DO_DIA = """
    SELECT h.region AS serie, h.item_id, MIN(h.price) AS preco
      FROM historical_item_prices h
     WHERE h.origem = 'UNDERMINE' AND h.granularidade = 'DIARIA' AND NOT h.anomalia
       AND h."timestamp" >= :inicio AND h."timestamp" < :fim
     GROUP BY 1, 2
"""
SERIES_DA_REGIAO = "SELECT DISTINCT serie FROM projecao_item WHERE regiao = :regiao"


class ConsolidacaoService:
    """CU11-C3: passos 2 a 6, FA2, FA3 e o registro dos dias (FE1)."""

    def __init__(self, session: Session, cfg: ConfigModelo,
                 relogio: Callable[[], datetime] = security.agora) -> None:
        self.session = session
        self.cfg = cfg
        self.relogio = relogio

    # ------------------------------------------------------------------------------------------------- passo 2
    def aguardar_importacao_diaria(self, limite_minutos: Optional[float] = None, desligada: bool = False,
                                   intervalo: float = INTERVALO_DA_ESPERA_SEGUNDOS,
                                   dormir: Callable[[float], Any] = time.sleep) -> EstadoDaImportacao:
        """CU11-C3 passo 2: a consolidação usa a importação incremental diária do worker (CU10-C1) e confere se a de
        hoje terminou. Em andamento (ou ainda não começada, como quando o computador acaba de ligar e o worker vai rodar
        a importação perdida), espera até o limite. Se ela falhou ou não rodou, segue com um aviso: os valores reais que
        faltarem ficam "N/D" (FA2). Com a importação diária desligada, não espera."""
        limite = timedelta(minutes=self.cfg.consolidacao_espera_minutos if limite_minutos is None else limite_minutos)
        prazo = self.relogio() + limite
        inicio_de_hoje = datetime.combine(self.relogio().date(), datetime.min.time())  # gravado em UTC, sem fuso
        while True:
            ultima = (
                self.session.query(ScraperExecutionLog)
                .filter(ScraperExecutionLog.triggered_by.in_((DISPARO_DIARIA, DISPARO_RECUPERACAO)),
                        ScraperExecutionLog.execution_start >= inicio_de_hoje)
                .order_by(ScraperExecutionLog.execution_start.desc()).first()
            )
            status = None if ultima is None else ultima.status
            self.session.rollback()  # a próxima consulta enxerga o que o worker gravou nesse meio-tempo
            if status == ExecutionStatus.SUCCESS:
                return EstadoDaImportacao(IMPORTACAO_CONCLUIDA)
            if status == ExecutionStatus.FAILED:
                return EstadoDaImportacao(IMPORTACAO_FALHA, "a importação diária de hoje falhou; os valores reais que "
                                                            "faltarem ficam N/D")
            if status is None and desligada:
                return EstadoDaImportacao(IMPORTACAO_NAO_RODOU, "a importação diária está desligada; os valores reais "
                                                                "que faltarem ficam N/D")
            if self.relogio() >= prazo:
                if status == ExecutionStatus.RUNNING:
                    return EstadoDaImportacao(IMPORTACAO_EM_ANDAMENTO, f"a importação diária de hoje ainda estava em "
                                                                       f"andamento depois de {limite}; os valores "
                                                                       f"reais que faltarem ficam N/D")
                return EstadoDaImportacao(IMPORTACAO_NAO_RODOU, "a importação diária de hoje não rodou; os valores "
                                                                "reais que faltarem ficam N/D")
            dormir(intervalo)

    # --------------------------------------------------------------------------------------------------- FE1
    def dias_pendentes(self, regiao: str, dia_de_referencia: date) -> list[date]:
        """FE1: os dias ainda não consolidados, na ordem: do dia seguinte ao último consolidado com sucesso até o dia de
        referência. Sem nenhum sucesso, a partir do primeiro dia que falhou; sem nenhuma consolidação, só o dia de
        referência."""
        ultimo = (
            self.session.query(func.max(ConsolidacaoDiaria.dia))
            .filter(ConsolidacaoDiaria.regiao == regiao, ConsolidacaoDiaria.status == STATUS_SUCESSO).scalar()
        )
        if ultimo is not None:
            inicio = ultimo + timedelta(days=1)
        else:
            primeira_falha = (self.session.query(func.min(ConsolidacaoDiaria.dia))
                              .filter(ConsolidacaoDiaria.regiao == regiao).scalar())
            inicio = min(primeira_falha, dia_de_referencia) if primeira_falha is not None else dia_de_referencia
        return [inicio + timedelta(days=k) for k in range((dia_de_referencia - inicio).days + 1)]

    def registrar(self, regiao: str, dia: date, status: str, **campos: Any) -> ConsolidacaoDiaria:
        """O registro do dia em `consolidacao_diaria` (um por região e dia; o reprocessamento do FE1 o substitui)."""
        registro = (self.session.query(ConsolidacaoDiaria)
                    .filter(ConsolidacaoDiaria.regiao == regiao, ConsolidacaoDiaria.dia == dia).one_or_none())
        if registro is None:
            registro = ConsolidacaoDiaria(regiao=regiao, dia=dia, iniciado_em=campos.pop("iniciado_em", self.relogio()))
            self.session.add(registro)
        else:
            registro.iniciado_em = campos.pop("iniciado_em", registro.iniciado_em)
        registro.status = status
        registro.concluido_em = self.relogio()
        for campo, valor in campos.items():
            setattr(registro, campo, valor)
        self.session.flush()
        return registro

    def consolidacoes_perdidas(self, desde: datetime) -> list[str]:
        """Disparo perdido (computador desligado no horário do agendador): as regiões com modelo vigente sem nenhuma
        consolidação concluída desde `desde`, o último disparo do cron."""
        vigentes = sorted(r for (r,) in self.session.query(ModeloPreditivo.regiao)
                          .filter(ModeloPreditivo.vigente.is_(True)))
        feitas = {r for (r,) in self.session.query(ConsolidacaoDiaria.regiao).filter(
            ConsolidacaoDiaria.status == STATUS_SUCESSO, ConsolidacaoDiaria.concluido_em >= desde)}
        self.session.rollback()
        return [regiao for regiao in vigentes if regiao not in feitas]

    # ------------------------------------------------------------------------------------------ passos 3 a 6
    def contar_liberados(self, regiao: str) -> int:
        return int(self.session.query(func.count()).select_from(ProjecaoItem).filter(
            ProjecaoItem.regiao == regiao, ProjecaoItem.situacao == SITUACAO_LIBERADA).scalar() or 0)

    def liberados(self, regiao: str) -> set[tuple[str, int]]:
        return {(str(s), int(i)) for s, i in self.session.query(ProjecaoItem.serie, ProjecaoItem.item_id).filter(
            ProjecaoItem.regiao == regiao, ProjecaoItem.situacao == SITUACAO_LIBERADA)}

    def preencher_valores_reais(self, regiao: str, dia: date) -> tuple[int, int, int]:
        """CU11-C3 passos 3 a 6 (RN13) e FA2: cada predição com `data_prevista` no dia, de qualquer versão do modelo,
        recebe o preço diário consolidado do item no dia (`preco_real`) e o erro `|previsto − real| ÷ real`. Sem preço
        real, os dois ficam nulos ("N/D"). Devolve as predições do dia, as preenchidas e as "N/D"."""
        agora = self.relogio()
        inicio = datetime.combine(dia, datetime.min.time())
        parametros = {"regiao": regiao, "dia": dia, "inicio": inicio, "fim": inicio + timedelta(days=1), "agora": agora}
        do_dia = int(self.session.execute(text(
            f"SELECT count(*) FROM predicao_diaria WHERE data_prevista = :dia AND serie IN ({SERIES_DA_REGIAO})"),
            parametros).scalar() or 0)
        if do_dia == 0:
            return 0, 0, 0
        preenchidas = self.session.execute(text(f"""
            UPDATE predicao_diaria AS p
               SET preco_real = r.preco, erro_pct = abs(p.preco_previsto - r.preco)::float8 / r.preco,
                   consolidado_em = :agora
              FROM ({PRECO_REAL_DO_DIA}) AS r
             WHERE p.data_prevista = :dia AND p.serie IN ({SERIES_DA_REGIAO})
               AND p.serie = r.serie AND p.item_id = r.item_id AND r.preco > 0
        """), parametros).rowcount
        nd = self.session.execute(text(f"""
            UPDATE predicao_diaria SET preco_real = NULL, erro_pct = NULL, consolidado_em = :agora
             WHERE data_prevista = :dia AND serie IN ({SERIES_DA_REGIAO}) AND consolidado_em IS NULL
        """), parametros).rowcount
        return do_dia, int(preenchidas), int(nd)

    # --------------------------------------------------------------------------------------------------- FA3
    def aplicar_degradacao(self, regiao: str, dia: date) -> list[tuple[str, int]]:
        """CU11-C3-FA3 (RN13): o erro do item é a mediana do `erro_pct` das predições com `data_prevista` nos últimos 7
        dias (do dia − 6 ao dia), em todos os horizontes, da versão que deu a situação atual do item (as de versões
        anteriores não julgam o modelo novo). Acima do limiar da RN10, com ao menos MODELO_DEGRADACAO_MINIMO_ALVOS erros
        (um único dia ruim não bloqueia), a projeção fica bloqueada por "degradação" até o próximo retreinamento.
        Devolve os itens bloqueados."""
        bloqueados = [(str(s), int(i)) for s, i in self.session.execute(text("""
            SELECT p.serie, p.item_id
              FROM predicao_diaria AS p
              JOIN projecao_item AS pi ON pi.serie = p.serie AND pi.item_id = p.item_id
             WHERE pi.regiao = :regiao AND pi.situacao = :liberada AND p.versao = pi.versao
               AND p.data_prevista BETWEEN :inicio AND :dia AND p.erro_pct IS NOT NULL
             GROUP BY p.serie, p.item_id
            HAVING count(*) >= :minimo AND percentile_cont(0.5) WITHIN GROUP (ORDER BY p.erro_pct) > :limiar
        """), {"regiao": regiao, "liberada": SITUACAO_LIBERADA, "dia": dia,
               "inicio": dia - timedelta(days=self.cfg.degradacao_dias - 1),
               "minimo": self.cfg.degradacao_minimo_alvos, "limiar": self.cfg.limiar_rn10})]
        for inicio in range(0, len(bloqueados), 5000):
            self.session.execute(
                update(ProjecaoItem)
                .where(ProjecaoItem.regiao == regiao,
                       tuple_(ProjecaoItem.serie, ProjecaoItem.item_id).in_(bloqueados[inicio:inicio + 5000]))
                .values(situacao=SITUACAO_BLOQUEADA, motivo=MOTIVO_DEGRADACAO, atualizado_em=self.relogio()))
        if bloqueados:
            logger.info("CU11-C3-FA3: %d itens de %s bloqueados por degradação em %s.", len(bloqueados), regiao, dia)
        return bloqueados
