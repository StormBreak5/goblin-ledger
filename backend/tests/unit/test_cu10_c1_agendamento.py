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
