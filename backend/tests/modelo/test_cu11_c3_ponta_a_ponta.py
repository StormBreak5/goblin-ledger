"""
Plano de testes do CU11 – Treinar Modelo, Cenário 03 (consolidar predições diárias), de ponta a ponta: o passo 7 (as
previsões dos próximos 7 dias), o FA1, o FA4, o FE1 e o agendamento. Os passos 2 a 6, o FA2 e o FA3 também têm testes no
host (tests/integration/test_cu11_c3_consolidacao.py). Rodam no serviço `modelo`, contra um PostgreSQL temporário.

A versão vigente é o C1 sintético de 06/10/2026 (série até 05/10, todos os itens liberados). A consolidação de 06/10
tem D = 05/10. Um treinador de previsão falso devolve, para cada item, a previsão pedida ("ingenua" = o preço de D;
"ruim" = 50% acima), para o teste saber o preço previsto em Cobre.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pandas")
pytest.importorskip("tensorflow")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from apoio_treino import CFG, FORA_DO_TREINO, TreinadorFalso, executar, projecoes  # noqa: E402
from sinteticos import gerar, gravar_no_banco, serie_constante  # noqa: E402
from src.ml.consolidacao import Consolidacao  # noqa: E402
from src.ml.rede import TreinadorKeras  # noqa: E402
from src.models.modelo import ConsolidacaoDiaria, ExecucaoTreinamento, PredicaoDiaria, ProjecaoItem  # noqa: E402
from src.scraper.models import ExecutionStatus, ScraperExecutionLog  # noqa: E402

DIA_DO_C1 = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
D = date(2026, 10, 5)
ESTAVEL, CARO = 300_010, 300_011  # itens de preço quase constante: o preço de D é o da série


class TreinadorDePrevisao(TreinadorFalso):
    """A "rede" da versão vigente, carregada pela consolidação: devolve a previsão pedida para cada item."""

    def __init__(self, padrao: str = "ingenua", modos: Optional[dict[int, str]] = None) -> None:
        super().__init__(modos=modos, padrao=padrao)

    def carregar(self, caminho: Path) -> Any:
        return {"padrao": self.padrao, "modos": {str(k): v for k, v in self.modos.items()}}


def cenario_c3() -> dict[str, pd.DataFrame]:
    """6 itens sintéticos e 2 de preço quase constante, até 08/10/2026 (o C1 de 06/10 usa até 05/10)."""
    dados = gerar(n_itens=6, inicio="2024-01-01", fim="2026-10-08", semente=5)
    dados["precos"]["quantidade"] = dados["precos"]["quantidade"].clip(lower=100)
    extras = [serie_constante(ESTAVEL, "2024-01-01", "2026-10-08", preco=10_000, ruido=0.02, semente=10),
              serie_constante(CARO, "2024-01-01", "2026-10-08", preco=20_000, ruido=0.02, semente=11)]
    dados["precos"] = pd.concat([dados["precos"], *extras], ignore_index=True)
    return dados


def vigente(pg_engine, db_session, relogio, pasta: Path, treinador: Any = None) -> int:
    """O C1 de 06/10/2026: a versão vigente e os itens liberados."""
    dados = cenario_c3()
    gravar_no_banco(db_session, dados, set(dados["precos"]["item_id"].astype(int)) - {FORA_DO_TREINO})
    relogio.agora = DIA_DO_C1
    resumo = executar(pg_engine, db_session, relogio, pasta, treinador or TreinadorFalso())
    assert resumo.status == "SUCESSO", resumo.erro
    return resumo.modelo.versao


def importacao_de_hoje(db_session, relogio) -> None:
    """A importação diária do worker (02:00 UTC) já terminou hoje."""
    inicio = datetime.combine(relogio().date(), datetime.min.time()) + timedelta(hours=2)
    db_session.add(ScraperExecutionLog(execution_start=inicio, execution_end=inicio, status=ExecutionStatus.SUCCESS,
                                       triggered_by="DIARIA", region="3209"))
    db_session.commit()


def consolidar(pg_engine, relogio, treinador: Any = None):  # type: ignore[no-untyped-def]
    return Consolidacao(pg_engine, CFG, treinador or TreinadorDePrevisao(), relogio,
                        dormir=lambda s: relogio.avancar(seconds=s)).executar()


def preco_do_dia(db_session, item_id: int, dia: date) -> int:
    return int(db_session.execute(text(
        "SELECT MIN(price) FROM historical_item_prices WHERE item_id = :i AND origem = 'UNDERMINE' "
        "AND granularidade = 'DIARIA' AND \"timestamp\"::date = :d"), {"i": item_id, "d": dia}).scalar())


def predicao(db_session, item_id: int, versao: int, data_prevista: date, h: int, previsto: int,
             erro: Optional[float] = None) -> None:
    db_session.add(PredicaoDiaria(data_previsao=data_prevista - timedelta(days=h), serie="32512", item_id=item_id,
                                  versao=versao, h=h, data_prevista=data_prevista, preco_previsto=previsto,
                                  erro_pct=erro, preco_real=None if erro is None else 1,
                                  consolidado_em=None if erro is None else DIA_DO_C1))
    db_session.commit()


def test_cu11_c3_fa1_sem_predicao_do_dia(pg_engine, db_session, relogio, tmp_path):
    """FA1: nos primeiros dias, ainda não há predição para o dia encerrado: o sistema segue para o passo 7 e grava as
    primeiras previsões."""
    versao = vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    liberados = sum(1 for p in projecoes(db_session).values() if p.situacao == "LIBERADA")

    resumo = consolidar(pg_engine, relogio)

    [dia] = resumo.dias
    assert (dia.dia, dia.status, dia.predicoes_do_dia, dia.itens_bloqueados_degradacao) == (D, "SUCESSO", 0, 0)
    assert dia.previsoes_gravadas == (liberados - dia.itens_sem_janela) * 7 and dia.previsoes_gravadas > 0
    registro = db_session.query(ConsolidacaoDiaria).one()
    assert (registro.dia, registro.status, registro.versao, registro.importacao_diaria) == (D, "SUCESSO", versao,
                                                                                            "CONCLUIDA")
    assert {(p.data_previsao, p.versao) for p in db_session.query(PredicaoDiaria)} == {(D, versao)}


def test_cu11_c3_gera_previsoes_dos_proximos_7_dias_em_cobre_rn01(pg_engine, db_session, relogio, tmp_path):
    """Passo 7: para cada item liberado, as predições de D+1 a D+7 em Cobre (RN01): preço de D × exp(log-retorno
    previsto). O item bloqueado não recebe previsão."""
    versao = vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    db_session.query(ProjecaoItem).filter(ProjecaoItem.item_id == 200_001).update(
        {"situacao": "BLOQUEADA", "motivo": "degradação"})
    db_session.commit()

    consolidar(pg_engine, relogio, TreinadorDePrevisao("ingenua", modos={CARO: "ruim"}))

    linhas = db_session.query(PredicaoDiaria).order_by(PredicaoDiaria.item_id, PredicaoDiaria.h).all()
    por_item: dict[int, list[PredicaoDiaria]] = {}
    for linha in linhas:
        por_item.setdefault(linha.item_id, []).append(linha)
    assert 200_001 not in por_item
    for item_id, previsoes in por_item.items():
        assert [p.h for p in previsoes] == list(range(1, 8))
        assert [p.data_prevista for p in previsoes] == [D + timedelta(days=h) for h in range(1, 8)]
        assert {(p.data_previsao, p.versao, p.preco_real, p.erro_pct) for p in previsoes} == {(D, versao, None, None)}
    assert {p.preco_previsto for p in por_item[ESTAVEL]} == {preco_do_dia(db_session, ESTAVEL, D)}  # ingênuo: o de D
    assert {p.preco_previsto for p in por_item[CARO]} == {int(np.rint(1.5 * preco_do_dia(db_session, CARO, D)))}
    assert all(isinstance(p.preco_previsto, int) for p in linhas)


def test_cu11_c3_previsao_usa_so_dados_ate_o_dia_de_referencia_rn25(pg_engine, db_session, relogio, tmp_path, mocker):
    """RN25: a previsão de D usa só os dados até D, e só o trecho necessário (MODELO_PREVISAO_HISTORICO_DIAS): mudar os
    preços depois de D ou antes do trecho não muda nenhuma previsão. Com a LSTM mínima de verdade."""
    from src.ml import previsao

    vigente(pg_engine, db_session, relogio, tmp_path, TreinadorKeras())
    db_session.query(ProjecaoItem).update({"situacao": "LIBERADA", "motivo": None})  # a rede de 1 época não libera
    db_session.commit()
    importacao_de_hoje(db_session, relogio)
    leituras = mocker.spy(previsao, "carregar_banco")

    consolidar(pg_engine, relogio, TreinadorKeras())
    antes = {(p.item_id, p.h): p.preco_previsto for p in db_session.query(PredicaoDiaria)}

    assert leituras.call_args.kwargs["ate"] == D + timedelta(days=1)
    assert leituras.call_args.kwargs["desde"] == D - timedelta(days=CFG.previsao_historico_dias - 1)
    assert antes and all(v > 0 for v in antes.values())
    db_session.execute(text("UPDATE historical_item_prices SET price = price * 7 WHERE \"timestamp\" >= :depois "
                            "OR \"timestamp\" < :antes"),
                       {"depois": datetime(2026, 10, 6), "antes": datetime.combine(
                           D - timedelta(days=CFG.previsao_historico_dias), datetime.min.time())})
    db_session.query(PredicaoDiaria).delete()
    db_session.query(ConsolidacaoDiaria).delete()
    db_session.commit()

    consolidar(pg_engine, relogio, TreinadorKeras())

    assert {(p.item_id, p.h): p.preco_previsto for p in db_session.query(PredicaoDiaria)} == antes


def test_cu11_c3_fa4_degradacao_generalizada_antecipa_retreino(pg_engine, db_session, relogio, tmp_path):
    """FA4: os itens bloqueados por degradação no dia passam de 20% dos liberados no início do dia: o retreinamento
    (C2) é registrado pelo mesmo caminho do agendador, sem duplicar o que já está na fila."""
    versao = vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    degradados = [ESTAVEL, CARO]  # 2 de 8 liberados (25%)
    for item_id in degradados:
        for k in range(1, 7):
            for h in (1, 2, 3):
                predicao(db_session, item_id, versao, D - timedelta(days=k), h, 1, erro=0.40)
        predicao(db_session, item_id, versao, D, 1, 1)  # previsão de D muito errada: o erro do dia também é alto

    resumo = consolidar(pg_engine, relogio)

    [dia] = resumo.dias
    assert dia.itens_bloqueados_degradacao == 2 and dia.itens_liberados_no_inicio == 8
    assert dia.retreinamento_antecipado
    execucoes = db_session.query(ExecucaoTreinamento).filter(ExecucaoTreinamento.tipo == "RETREINAMENTO").all()
    assert [(e.disparo, e.regiao, e.status) for e in execucoes] == [("AGENDADO", "US", "AGUARDANDO")]
    registro = db_session.query(ConsolidacaoDiaria).one()
    assert registro.retreinamento_antecipado and registro.id_execucao_retreinamento == execucoes[0].id
    assert {p.item_id: (p.situacao, p.motivo) for p in projecoes(db_session).values()
            if p.item_id in degradados} == {i: ("BLOQUEADA", "degradação") for i in degradados}


def test_cu11_c3_fe1_falha_no_banco_reprocessa(pg_engine, db_session, relogio, tmp_path, mocker):
    """FE1: a falha desfaz os registros do dia (nada preenchido, nenhuma previsão) e vai para o registro. O disparo
    seguinte reprocessa, na ordem, o dia atrasado (valores reais e FA3, sem previsões retroativas) e o dia novo (com
    as previsões)."""
    from src.ml import consolidacao

    versao = vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    predicao(db_session, ESTAVEL, versao, D, 1, 10_000)
    queda = OperationalError("INSERT INTO predicao_diaria", {}, Exception("server closed the connection"))
    mocker.patch.object(consolidacao, "prever_dia", side_effect=queda)

    falha = consolidar(pg_engine, relogio)

    assert [(d.dia, d.status) for d in falha.dias] == [(D, "FALHA")] and "server closed" in falha.dias[0].erro
    db_session.expire_all()
    [predita] = db_session.query(PredicaoDiaria).all()
    assert (predita.preco_real, predita.consolidado_em) == (None, None)  # o preenchimento foi desfeito
    assert db_session.query(ConsolidacaoDiaria).one().status == "FALHA"

    mocker.stopall()
    relogio.avancar(days=1)
    importacao_de_hoje(db_session, relogio)
    reprocessado = consolidar(pg_engine, relogio)

    assert [(d.dia, d.status) for d in reprocessado.dias] == [(D, "SUCESSO"), (D + timedelta(days=1), "SUCESSO")]
    assert reprocessado.dias[0].predicoes_preenchidas == 1 and reprocessado.dias[0].previsoes_gravadas == 0
    assert reprocessado.dias[1].previsoes_gravadas > 0
    db_session.expire_all()
    assert {p.data_previsao for p in db_session.query(PredicaoDiaria) if p.data_previsao != D - timedelta(days=1)} == \
        {D + timedelta(days=1)}  # sem previsões retroativas para D
    assert [(c.dia, c.status) for c in db_session.query(ConsolidacaoDiaria).order_by(ConsolidacaoDiaria.dia)] == [
        (D, "SUCESSO"), (D + timedelta(days=1), "SUCESSO")]


def test_cu11_c3_disparo_perdido_roda_ao_iniciar(pg_engine, db_session, relogio, mocker, monkeypatch):
    """Passo 1: todo dia às 03:00 UTC. Dormindo no horário (três disparos perdidos), roda ao acordar uma vez só;
    desligado, o serviço confere ao iniciar e roda agora, uma vez."""
    import threading
    import time

    from apscheduler.schedulers.background import BackgroundScheduler

    from src import modelo_worker
    from src.models.modelo import ModeloPreditivo

    monkeypatch.delenv("MODELO_CONSOLIDACAO_CRON", raising=False)
    SessionLocal = sessionmaker(bind=pg_engine)
    execucoes: list[int] = []
    rodou = threading.Event()
    mocker.patch.object(modelo_worker, "consolidacao_perdida", return_value=False)
    agendador = BackgroundScheduler(timezone=timezone.utc)
    agendador.start(paused=True)
    try:
        assert modelo_worker.agendar_consolidacao(agendador, lambda: (execucoes.append(1), rodou.set()), SessionLocal,
                                                  CFG)
        agora = datetime.now(timezone.utc)
        assert agendador.get_job(modelo_worker.CONSOLIDACAO_JOB_ID).trigger.get_next_fire_time(
            None, datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)
        agendador.modify_job(modelo_worker.CONSOLIDACAO_JOB_ID, next_run_time=agora - timedelta(days=2, hours=12))
        agendador.resume()
        assert rodou.wait(timeout=5)
        time.sleep(0.5)
        assert execucoes == [1]
    finally:
        agendador.shutdown()

    mocker.stopall()
    db_session.add(ModeloPreditivo(
        regiao="US", treinado_em=DIA_DO_C1, data_inicio=date(2024, 1, 1), corte_validacao=date(2025, 12, 7),
        corte_teste=date(2026, 6, 26), data_fim=D, itens_elegiveis=1, itens_treino=1, itens_avaliados=1,
        amostras_treino=1, amostras_validacao=1, amostras_teste=1, epocas=1, melhor_epoca=1, segundos_por_epoca=1.0,
        duracao_segundos=1.0, caminho_artefatos="v1", assinatura_normalizacao="a", vigente=True))
    db_session.commit()
    ligou = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)  # desligado às 03:00 de 07/10
    assert modelo_worker.consolidacao_perdida(SessionLocal, CFG, ligou)
    agendador = MagicMock()
    mocker.patch.object(modelo_worker, "consolidacao_perdida", return_value=True)
    modelo_worker.agendar_consolidacao(agendador, lambda: None, SessionLocal, CFG)
    jobs = {c.kwargs["id"]: c for c in agendador.add_job.call_args_list}
    assert jobs[modelo_worker.CONSOLIDACAO_PERDIDA_JOB_ID].args[1] == "date"
    mocker.stopall()

    db_session.add(ConsolidacaoDiaria(regiao="US", dia=date(2026, 10, 6), status="SUCESSO",
                                      iniciado_em=ligou - timedelta(hours=5), concluido_em=ligou - timedelta(hours=5)))
    db_session.commit()  # a de 07/10 às 04:00 rodou depois do disparo das 03:00
    assert not modelo_worker.consolidacao_perdida(SessionLocal, CFG, ligou)


def test_cu11_c3_comando_consolidar(pg_engine, db_session, relogio, tmp_path, mocker, capsys):
    """`python -m src.modelo_worker --consolidar` roda a consolidação agora, como o agendador, e mostra o resumo."""
    from src import modelo_worker

    vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    mocker.patch.object(modelo_worker, "init_db", return_value=sessionmaker(bind=pg_engine))
    mocker.patch.object(modelo_worker, "Consolidacao",
                        lambda engine, cfg: Consolidacao(engine, CFG, TreinadorDePrevisao(), relogio))

    assert modelo_worker.main(["--consolidar"]) == 0

    saida = capsys.readouterr().out
    assert "Importação diária: CONCLUIDA" in saida and "status='SUCESSO'" in saida
    assert db_session.query(ConsolidacaoDiaria).one().status == "SUCESSO"
    assert db_session.query(PredicaoDiaria).count() > 0

    previsoes = db_session.query(PredicaoDiaria).count()
    assert modelo_worker.main(["--consolidar"]) == 0  # de novo no mesmo dia: nada a fazer, nada em dobro
    assert "Nenhum dia a consolidar" in capsys.readouterr().out
    assert (db_session.query(ConsolidacaoDiaria).count(), db_session.query(PredicaoDiaria).count()) == (1, previsoes)
