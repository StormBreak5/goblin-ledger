"""
CU09-C1 (ativação) – regras de agendamento da ingestão: funções puras, sem esperar o relógio, e o agendador do worker.
"""
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from apscheduler.schedulers.background import BackgroundScheduler

from src import worker
from src.services.agendamento import (
    ESPERA_MINIMA,
    INTERVALO_ENTRE_RECUPERACOES,
    MARGEM_DO_DISPARO,
    planejar,
    proximo_disparo,
)

AGORA = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
CHAVE = "auctions:us:3209"


def test_cu09_c1_ativacao_planeja_coleta_imediata_apos_uma_hora():
    for ultima in (None, AGORA - timedelta(minutes=60), AGORA - timedelta(hours=5)):
        plano = planejar(AGORA, AGORA - timedelta(hours=1), {CHAVE: ultima})

        assert plano.mercados_a_coletar == (CHAVE,), ultima
        assert plano.recuperar_com_backfill is False


def test_cu09_c1_ativacao_planeja_espera_ate_completar_60_minutos():
    ultima = AGORA - timedelta(minutes=20)

    plano = planejar(AGORA, ultima, {CHAVE: ultima})

    assert plano.mercados_a_coletar == ()  # C1-FA1: não coleta, reagenda
    assert proximo_disparo(AGORA, {CHAVE: ultima}) == ultima + timedelta(minutes=60) + MARGEM_DO_DISPARO

    quase_liberado = AGORA - timedelta(minutes=59, seconds=59)
    assert planejar(AGORA, quase_liberado, {CHAVE: quase_liberado}).mercados_a_coletar == ()  # falta 1 s: ainda não
    assert proximo_disparo(AGORA, {CHAVE: quase_liberado}) == AGORA + ESPERA_MINIMA  # e espera ao menos 1 minuto


def test_cu09_c1_ativacao_planeja_backfill_apos_48h():
    for horas, esperado in ((47, False), (48, False), (49, True), (500, True)):
        ultima_coleta = AGORA - timedelta(hours=horas)

        plano = planejar(AGORA, ultima_coleta, {CHAVE: ultima_coleta})

        assert plano.recuperar_com_backfill is esperado, horas
        assert plano.mercados_a_coletar == (CHAVE,)  # e o ciclo da Blizzard vem depois do backfill


def test_cu09_c1_ativacao_sem_nenhuma_coleta_recompoe_o_historico_uma_vez():
    plano = planejar(AGORA, None, {CHAVE: None})

    assert plano.recuperar_com_backfill is True and plano.mercados_a_coletar == (CHAVE,)


def test_cu09_c1_ativacao_nao_repete_a_recuperacao_em_menos_de_6_horas():
    ultima_coleta = AGORA - timedelta(days=5)  # a Blizzard ficou fora do ar por dias

    logo_depois = planejar(AGORA, ultima_coleta, {CHAVE: None}, ultimo_backfill_iniciado=AGORA - timedelta(hours=1))
    passado_o_intervalo = planejar(
        AGORA, ultima_coleta, {CHAVE: None}, ultimo_backfill_iniciado=AGORA - INTERVALO_ENTRE_RECUPERACOES
    )

    assert logo_depois.recuperar_com_backfill is False  # o backfill não roda a cada hora enquanto a API está fora
    assert passado_o_intervalo.recuperar_com_backfill is True


def test_cu09_c1_ativacao_proximo_disparo_espera_o_primeiro_endpoint_liberar():
    reino, commodities = "auctions:us:3209", "commodities:us"
    ultimas = {reino: AGORA - timedelta(minutes=10), commodities: AGORA - timedelta(minutes=40)}

    assert proximo_disparo(AGORA, ultimas) == AGORA + timedelta(minutes=20) + MARGEM_DO_DISPARO  # o de 40 min atrás
    # Sem nenhuma requisição registrada (ou já liberado), tenta de novo em 1 minuto, e não em laço apertado.
    assert proximo_disparo(AGORA, {reino: None}) == AGORA + ESPERA_MINIMA
    assert proximo_disparo(AGORA, {reino: AGORA - timedelta(hours=3)}) == AGORA + ESPERA_MINIMA


# ---------------------------------------------------------------- worker: o que é agendado

def _agendar_worker(mocker):
    agendador = MagicMock()
    mocker.patch.object(worker, "BackgroundScheduler", return_value=agendador)
    mocker.patch.object(worker, "init_db")
    mocker.patch.object(worker, "get_session", return_value=MagicMock())
    worker.start_scheduler()
    return {chamada.kwargs["id"]: chamada for chamada in agendador.add_job.call_args_list}


def test_cu09_c1_ativacao_nao_ha_mais_backfill_horario(mocker):
    jobs = _agendar_worker(mocker)

    assert set(jobs) == {"token_job", "sync_items_job", "ingestao_job", "vigia_ingestao_job"}
    assert "backfill_job" not in jobs
    assert worker.job_run_backfill not in [chamada.args[0] for chamada in jobs.values()]  # só a recuperação o chama


def test_cu09_c1_ativacao_so_a_ficha_do_wow_roda_a_cada_15_minutos(mocker):
    jobs = _agendar_worker(mocker)

    a_cada_15 = [
        chave for chave, chamada in jobs.items()
        if chamada.args[1] == "interval" and chamada.kwargs.get("minutes") == 15
    ]
    assert a_cada_15 == ["token_job"]
    assert jobs["token_job"].args[0] is worker.job_fetch_wow_token_price
    # A ingestão dos leilões não é um job periódico: roda na hora ao iniciar e reagenda a si mesma após 60 minutos.
    assert jobs["ingestao_job"].args[1] == "date"
    assert jobs["ingestao_job"].kwargs["misfire_grace_time"] is None  # e nunca é descartada por atraso
    assert jobs["vigia_ingestao_job"].kwargs["minutes"] == 5  # e o vigia confere a cadeia a cada 5 minutos


def test_cu09_c1_ativacao_a_ingestao_reagenda_a_si_mesma(mocker):
    agendador = MagicMock()
    mocker.patch.object(worker, "scheduler", agendador)
    quando = AGORA + timedelta(minutes=60)

    worker.agendar_ingestao(quando)

    argumentos = agendador.add_job.call_args
    assert argumentos.args[:2] == (worker.job_ingestao_de_mercado, "date")
    assert argumentos.kwargs["run_date"] == quando and argumentos.kwargs["replace_existing"] is True


# ---------------------------------------------------------------- worker: a cadeia de rodadas não pode se perder

def test_cu09_c1_ativacao_rodada_atrasada_por_dias_roda_ao_acordar(mocker):
    """O PC ficou suspenso por 2,5 dias: a rodada horária atrasada roda assim que o worker acorda, não é descartada."""
    executou = threading.Event()
    mocker.patch.object(worker, "job_ingestao_de_mercado", executou.set)
    agendador = BackgroundScheduler(timezone=timezone.utc)
    mocker.patch.object(worker, "scheduler", agendador)
    agendador.start()
    try:
        worker.agendar_ingestao(datetime.now(timezone.utc) - timedelta(days=2, hours=12))

        assert executou.wait(timeout=5)
    finally:
        agendador.shutdown()


def test_cu09_c1_ativacao_a_proxima_rodada_e_agendada_mesmo_quando_a_rodada_falha(mocker):
    mocker.patch.object(worker, "_rodada_de_ingestao", side_effect=RuntimeError("banco fora do ar"))
    agendar = mocker.patch.object(worker, "agendar_ingestao")

    worker.job_ingestao_de_mercado()

    agendar.assert_called_once_with(None)  # sem horário calculado: tenta de novo em 1 hora
    assert not worker._rodada_em_andamento.locked()


def test_cu09_c1_ativacao_a_proxima_rodada_vem_do_horario_calculado_pela_rodada(mocker):
    proximo = AGORA + timedelta(minutes=37)
    mocker.patch.object(worker, "_rodada_de_ingestao", return_value=proximo)
    agendar = mocker.patch.object(worker, "agendar_ingestao")

    worker.job_ingestao_de_mercado()

    agendar.assert_called_once_with(proximo)


def test_cu09_c1_ativacao_nao_roda_duas_rodadas_ao_mesmo_tempo(mocker):
    rodada = mocker.patch.object(worker, "_rodada_de_ingestao")
    agendar = mocker.patch.object(worker, "agendar_ingestao")
    worker._rodada_em_andamento.acquire()
    try:
        worker.job_ingestao_de_mercado()
    finally:
        worker._rodada_em_andamento.release()

    rodada.assert_not_called()
    agendar.assert_not_called()


def test_cu09_c1_ativacao_vigia_retoma_a_ingestao_que_se_perdeu(mocker):
    agendador = MagicMock()
    agendador.get_job.return_value = None  # a cadeia se perdeu: não há rodada agendada
    mocker.patch.object(worker, "scheduler", agendador)

    worker.job_vigiar_ingestao()

    agendador.get_job.assert_called_once_with("ingestao_job")
    argumentos = agendador.add_job.call_args
    assert argumentos.args[:2] == (worker.job_ingestao_de_mercado, "date")
    assert argumentos.kwargs["id"] == "ingestao_job"
    assert abs(argumentos.kwargs["run_date"] - datetime.now(timezone.utc)) < timedelta(seconds=5)  # na hora
    assert argumentos.kwargs["misfire_grace_time"] is None


def test_cu09_c1_ativacao_vigia_nao_mexe_na_ingestao_ja_agendada(mocker):
    agendador = MagicMock()
    agendador.get_job.return_value = MagicMock()  # há uma próxima rodada
    mocker.patch.object(worker, "scheduler", agendador)

    worker.job_vigiar_ingestao()

    agendador.add_job.assert_not_called()


def test_cu09_c1_ativacao_vigia_nao_agenda_enquanto_a_rodada_esta_em_andamento(mocker):
    agendador = MagicMock()
    agendador.get_job.return_value = None  # um job `date` sai do agendador ao começar a rodar
    mocker.patch.object(worker, "scheduler", agendador)
    worker._rodada_em_andamento.acquire()
    try:
        worker.job_vigiar_ingestao()
    finally:
        worker._rodada_em_andamento.release()

    agendador.add_job.assert_not_called()  # a própria rodada agenda a seguinte ao terminar
