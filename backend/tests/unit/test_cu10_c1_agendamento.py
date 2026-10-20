"""
CU10-C1, importação diária: o worker agenda a importação incremental do histórico da Undermine pelo cron do ambiente,
em UTC (a série diária precisa crescer com o worker no ar; o CU11-C2 e o C3 dependem dela).
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src import worker

AGORA = datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc)


def _agendar_worker(mocker):
    agendador = MagicMock()
    mocker.patch.object(worker, "BackgroundScheduler", return_value=agendador)
    mocker.patch.object(worker, "init_db")
    mocker.patch.object(worker, "get_session", return_value=MagicMock())
    worker.start_scheduler()
    return {chamada.kwargs["id"]: chamada for chamada in agendador.add_job.call_args_list}


def test_cu10_c1_worker_agenda_a_importacao_diaria(mocker, monkeypatch):
    monkeypatch.delenv("HISTORICO_IMPORTACAO_DIARIA_CRON", raising=False)
    chamada = _agendar_worker(mocker)["importacao_diaria_job"]

    assert chamada.args[0] is worker.job_importacao_diaria
    assert chamada.args[1].get_next_fire_time(None, AGORA) == datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc)
    assert chamada.kwargs["misfire_grace_time"] is None and chamada.kwargs["coalesce"]  # roda ao acordar, uma vez

    monkeypatch.setenv("HISTORICO_IMPORTACAO_DIARIA_CRON", "30 3 * * *")
    gatilho = _agendar_worker(mocker)["importacao_diaria_job"].args[1]
    assert gatilho.get_next_fire_time(None, AGORA) == datetime(2026, 10, 20, 3, 30, tzinfo=timezone.utc)

    monkeypatch.setenv("HISTORICO_IMPORTACAO_DIARIA_CRON", "off")
    assert "importacao_diaria_job" not in _agendar_worker(mocker)


def test_cu10_c1_importacao_diaria_dormindo_roda_ao_acordar_uma_vez(mocker):
    """Computador suspenso por 2,5 dias (três disparos das 02:00 perdidos): ao acordar, a importação diária roda uma vez
    só (coalesce, sem limite de atraso), e o próximo disparo volta ao horário."""
    import threading
    import time
    from datetime import timedelta

    from apscheduler.schedulers.background import BackgroundScheduler

    execucoes: list[int] = []
    rodou = threading.Event()
    mocker.patch.object(worker, "job_importacao_diaria", lambda: (execucoes.append(1), rodou.set()))
    mocker.patch.object(worker, "importacao_diaria_perdida", return_value=False)
    agendador = BackgroundScheduler(timezone=timezone.utc)
    agendador.start(paused=True)
    try:
        worker.agendar_importacao_diaria(agendador)
        agora = datetime.now(timezone.utc)
        agendador.modify_job(worker.IMPORTACAO_DIARIA_JOB_ID, next_run_time=agora - timedelta(days=2, hours=12))
        agendador.resume()

        assert rodou.wait(timeout=5)
        time.sleep(0.5)
        assert execucoes == [1]
        assert agendador.get_job(worker.IMPORTACAO_DIARIA_JOB_ID).next_run_time > agora
    finally:
        agendador.shutdown()


def test_cu10_c1_importacao_diaria_perdida_com_o_computador_desligado_roda_ao_iniciar(mocker):
    """Desligado no horário, o APScheduler não guarda o disparo: ao iniciar, o worker agenda a importação para agora,
    uma vez, se o último disparo do cron não tem importação concluída depois dele (a regra está no teste de integração
    test_cu10_c1_importacao_diaria_perdida_e_reconhecida_pelo_ultimo_disparo)."""
    agendador = MagicMock()
    mocker.patch.object(worker, "importacao_diaria_perdida", return_value=True)
    worker.agendar_importacao_diaria(agendador)
    jobs = {chamada.kwargs["id"]: chamada for chamada in agendador.add_job.call_args_list}

    perdida = jobs["importacao_diaria_perdida_job"]
    assert perdida.args[:2] == (worker.job_importacao_diaria, "date")
    assert perdida.kwargs["misfire_grace_time"] is None
    assert set(jobs) == {"importacao_diaria_job", "importacao_diaria_perdida_job"}

    agendador = MagicMock()
    mocker.patch.object(worker, "importacao_diaria_perdida", return_value=False)
    worker.agendar_importacao_diaria(agendador)
    assert [c.kwargs["id"] for c in agendador.add_job.call_args_list] == ["importacao_diaria_job"]


def test_cu10_c1_importacao_diaria_agendada_nao_grava_junto_com_o_ciclo_da_blizzard(mocker):
    """A importação diária agendada espera a rodada de ingestão (CU09) em andamento terminar, como a recuperação de 48 h:
    as duas gravam em historical_item_prices e, juntas, podem entrar em deadlock."""
    import threading

    from src.services.importacao_historico import ImportacaoHistoricoService

    importou = threading.Event()
    mocker.patch.object(worker, "get_session", return_value=MagicMock())
    mocker.patch.object(ImportacaoHistoricoService, "importar_diariamente", lambda self: importou.set() or [])

    worker._rodada_em_andamento.acquire()  # um ciclo da Blizzard em andamento
    try:
        importacao = threading.Thread(target=worker.job_importacao_diaria)
        importacao.start()
        assert not importou.wait(timeout=0.5)  # esperando o ciclo
    finally:
        worker._rodada_em_andamento.release()
    importacao.join(timeout=5)
    assert importou.is_set() and not worker._rodada_em_andamento.locked()
