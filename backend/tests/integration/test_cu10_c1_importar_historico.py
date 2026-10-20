"""
Plano de testes do CU10 – Cadastrar Dados Passados, Cenário 01 (importar histórico de preços), um teste por fluxo.
Rodam contra um PostgreSQL temporário; a Undermine Exchange é falsa (tests/helpers_historico.py).
"""
import logging
from datetime import timedelta

from helpers_auth import cabecalho, cadastrar_e_entrar
from helpers_historico import REGIAO, dias
from sqlalchemy.exc import OperationalError

from src.models.item import Item
from src.models.usuario import Usuario
from src.scraper import backfill
from src.scraper.models import ExecutionStatus, HistoricalItemPrice, ScraperExecutionLog

FE1 = "Não foi possível obter os dados da fonte informada. Tente novamente mais tarde"
FE2 = "Não foi possível concluir a importação no momento. Tente novamente mais tarde"
FE3 = "Não foi possível interpretar os dados da fonte. Verifique se houve alteração no formato"
FA1 = "Região ou item inválido. Verifique os dados informados"


def _token_de_admin(cliente, db_session) -> str:
    token = cadastrar_e_entrar(cliente)
    db_session.query(Usuario).update({"role": "admin"})  # o papel é lido a cada requisição
    db_session.commit()
    return token


def _importar(cliente, token, **corpo):
    """Passos 1 e 2: o pedido é validado e aceito; a importação (passos 3 a 10) roda em segundo plano."""
    return cliente.post("/api/admin/history-import", json={"regiao": "US", **corpo}, headers=cabecalho(token))


def _resumo(cliente, token, resposta) -> dict:
    """Passo 10: o resumo da importação, consultado pelo id devolvido no pedido."""
    assert resposta.status_code == 202, resposta.text
    consulta = cliente.get(f"/api/admin/history-import/{resposta.json()['id_execucao']}", headers=cabecalho(token))
    assert consulta.status_code == 200
    return consulta.json()


def _itens(add_item, ids):
    for item_id in ids:
        add_item(item_id, f"Item {item_id}")


def test_cu10_c1_fluxo_principal_importa_o_historico_pedido_pelo_admin(admin_client, db_session, add_item, fonte_falsa):
    _itens(add_item, (1001, 1002, 1003))
    fonte_falsa.com_dias(1001, dias(5))
    fonte_falsa.com_dias(1002, dias(5))
    fonte_falsa.com_dias(1003, dias(5))  # este item não será pedido
    token = _token_de_admin(admin_client, db_session)

    resposta = _importar(admin_client, token, itens=[1001, 1002])

    assert resposta.status_code == 202
    assert resposta.json()["status"] == "EM_ANDAMENTO"  # a resposta sai antes de a importação terminar
    resumo = _resumo(admin_client, token, resposta)
    assert resumo["status"] == "CONCLUIDA" and resumo["disparo"] == "ADMIN" and resumo["regiao"] == REGIAO
    # Passo 10: registros importados, descartados e duplicados.
    assert (resumo["registros_importados"], resumo["registros_descartados"], resumo["registros_duplicados"]) == (10, 0, 0)
    assert (resumo["itens_solicitados"], resumo["itens_processados"]) == (2, 2)
    assert {linha.item_id for linha in db_session.query(HistoricalItemPrice)} == {1001, 1002}

    # Repetir o pedido: tudo já existe para o mesmo item e a mesma data (passo 8), e o resumo conta os duplicados.
    repetido = _resumo(admin_client, token, _importar(admin_client, token, itens=[1001, 1002]))
    assert (repetido["registros_importados"], repetido["registros_duplicados"]) == (0, 10)
    assert db_session.query(HistoricalItemPrice).count() == 10


def test_cu10_c1_fluxo_principal_sem_itens_importa_todos_os_itens_ativos(admin_client, db_session, add_item, fonte_falsa):
    _itens(add_item, (2001, 2002, 122284))  # a Ficha do WoW tem coleta própria e fica de fora
    add_item(2003, "Item inativo")
    db_session.query(Item).filter(Item.external_item_id == "2003").update({"is_active": False})
    db_session.commit()
    for item_id in (2001, 2002, 2003, 122284):
        fonte_falsa.com_dias(item_id, dias(2))
    token = _token_de_admin(admin_client, db_session)

    resumo = _resumo(admin_client, token, _importar(admin_client, token))

    assert resumo["itens_solicitados"] == 2
    assert {chamado.item_id for chamado in fonte_falsa.chamadas} == {2001, 2002}


def test_cu10_c1_fa1_regiao_ou_item_invalido(admin_client, db_session, fonte_falsa):
    token = _token_de_admin(admin_client, db_session)
    invalidos = [
        {"regiao": "CN"}, {"regiao": ""}, {"regiao": "EU"},  # EU não tem reino monitorado por padrão
        {"itens": ["abc"]}, {"itens": [0]}, {"itens": [-3]}, {"itens": [True]}, {"itens": [1.5]},
        {"itens": [2_147_483_648]}, {"itens": [122284]}, {"itens": [1001, None]},
        {"reino": "3209"}, {"reino": 0}, {"reino": True},
    ]

    for corpo in invalidos:
        resposta = admin_client.post(
            "/api/admin/history-import", json={"regiao": "US", **corpo}, headers=cabecalho(token)
        )
        assert resposta.status_code == 422, corpo
        assert resposta.json() == {"detail": FA1}, corpo  # o texto das Observações, e não o do Pydantic

    assert fonte_falsa.chamadas == []  # retorna ao passo 1: nada foi consultado nem registrado
    assert db_session.query(ScraperExecutionLog).count() == 0


def test_cu10_c1_fa2_item_nao_cadastrado_e_cadastrado_com_o_identificador(admin_client, db_session, add_item, fonte_falsa):
    fonte_falsa.com_dias(3001, dias(4))  # a fonte tem o item, mas ele não existe no banco
    fonte_falsa.com_dias(3002, dias(4))
    add_item(3002, "Item existente")
    token = _token_de_admin(admin_client, db_session)

    resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=[3001, 3002, 3003]))  # 3003: sem arquivo

    novo = db_session.query(Item).filter(Item.external_item_id == "3001").one()
    assert (novo.game, novo.name, novo.is_active) == ("wow", "Item 3001", True)  # o nome real vem depois
    assert novo.metadata_info["last_etag"]  # o item já nasce com o ETag do arquivo importado
    assert db_session.query(Item).filter(Item.external_item_id == "3003").count() == 0  # sem dados: não cria item
    assert (resumo["itens_cadastrados"], resumo["itens_sem_dados"], resumo["registros_importados"]) == (1, 1, 8)


def test_cu10_c1_fe1_fonte_indisponivel_mantem_o_que_ja_foi_gravado(admin_client, db_session, add_item, fonte_falsa, mocker, caplog):
    ids = list(range(4001, 4008))
    _itens(add_item, ids)
    for item_id in ids[:3]:
        fonte_falsa.com_dias(item_id, dias(3))
    for item_id in ids[3:]:
        fonte_falsa.comportamentos[item_id] = "rede"  # a fonte cai depois do primeiro lote
    mocker.patch.object(backfill, "CHUNK_SIZE", 3)
    mocker.patch.object(backfill, "LIMITE_DE_FALHAS_SEGUIDAS", 2)
    token = _token_de_admin(admin_client, db_session)

    with caplog.at_level(logging.ERROR, logger="src.services.importacao_historico"):
        resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=ids))

    assert resumo["status"] == "FALHA" and resumo["etapa_da_falha"] == "FONTE"
    assert resumo["mensagem"] == FE1
    assert "fonte fora do ar" in resumo["erro"]  # o detalhe técnico vai para o log e para o Admin
    assert "CU10-C1-FE1" in caplog.text
    assert db_session.query(HistoricalItemPrice).count() == 9  # o primeiro lote continua gravado
    assert resumo["registros_importados"] == 9
    assert len(fonte_falsa.chamadas) < len(ids)  # a importação parou: os itens seguintes nem foram consultados
    log = db_session.query(ScraperExecutionLog).one()
    assert log.status == ExecutionStatus.FAILED


def test_cu10_c1_fe1_falhas_isoladas_nao_interrompem_a_importacao(admin_client, db_session, add_item, fonte_falsa):
    ids = [4101, 4102, 4103]
    _itens(add_item, ids)
    fonte_falsa.com_dias(4101, dias(3))
    fonte_falsa.comportamentos[4102] = "5xx"  # falha só nesse item
    fonte_falsa.com_dias(4103, dias(3))
    token = _token_de_admin(admin_client, db_session)

    resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=ids))

    assert resumo["status"] == "CONCLUIDA"
    assert (resumo["itens_com_erro"], resumo["registros_importados"]) == (1, 6)


def test_cu10_c1_fe2_falha_de_banco_desfaz_a_importacao(admin_client, db_session, add_item, fonte_falsa, mocker):
    ids = [5001, 5002, 5003, 5004]
    _itens(add_item, ids)
    for item_id in ids:
        fonte_falsa.com_dias(item_id, dias(4))
    mocker.patch.object(backfill, "CHUNK_SIZE", 2)
    gravar = backfill._insert_rows
    chamadas = {"total": 0}

    def cai_no_segundo_lote(session, rows):
        chamadas["total"] += 1
        if chamadas["total"] == 2:
            raise OperationalError("INSERT INTO historical_item_prices", {}, Exception("connection lost"))
        return gravar(session, rows)

    mocker.patch.object(backfill, "_insert_rows", cai_no_segundo_lote)
    token = _token_de_admin(admin_client, db_session)

    resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=ids))

    assert resumo["status"] == "FALHA" and resumo["etapa_da_falha"] == "BANCO"
    assert resumo["mensagem"] == FE2
    assert db_session.query(HistoricalItemPrice).count() == 0  # sem registros parciais: o primeiro lote também foi desfeito
    assert (resumo["registros_importados"], resumo["itens_cadastrados"]) == (0, 0)


def test_cu10_c1_fe3_formato_alterado_interrompe_e_mantem_o_que_ja_foi_gravado(admin_client, db_session, add_item, fonte_falsa, mocker, caplog):
    ids = list(range(6001, 6008))
    _itens(add_item, ids)
    for item_id in ids[:3]:
        fonte_falsa.com_dias(item_id, dias(3))
    for item_id in ids[3:]:
        fonte_falsa.comportamentos[item_id] = "formato"  # a fonte muda o formato depois do primeiro lote
    mocker.patch.object(backfill, "CHUNK_SIZE", 3)
    mocker.patch.object(backfill, "LIMITE_DE_ARQUIVOS_ILEGIVEIS", 2)
    token = _token_de_admin(admin_client, db_session)

    with caplog.at_level(logging.ERROR, logger="src.services.importacao_historico"):
        resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=ids))

    assert resumo["status"] == "FALHA" and resumo["etapa_da_falha"] == "FORMATO"
    assert resumo["mensagem"] == FE3
    assert "CU10-C1-FE3" in caplog.text
    assert db_session.query(HistoricalItemPrice).count() == 9  # mantém os registros já persistidos
    assert len(fonte_falsa.chamadas) < len(ids)


def test_cu10_c1_um_arquivo_ilegivel_isolado_nao_e_formato_alterado(admin_client, db_session, add_item, fonte_falsa):
    ids = [6101, 6102, 6103]
    _itens(add_item, ids)
    fonte_falsa.com_dias(6101, dias(2))
    fonte_falsa.comportamentos[6102] = "formato"
    fonte_falsa.com_dias(6103, dias(2))
    token = _token_de_admin(admin_client, db_session)

    resumo = _resumo(admin_client, token, _importar(admin_client, token, itens=ids))

    assert resumo["status"] == "CONCLUIDA" and resumo["itens_com_erro"] == 1


def test_cu10_c1_so_uma_importacao_roda_por_vez(admin_client, db_session, add_item, fonte_falsa, relogio):
    _itens(add_item, (7001,))
    fonte_falsa.com_dias(7001, dias(2))
    token = _token_de_admin(admin_client, db_session)
    db_session.add(
        ScraperExecutionLog(execution_start=relogio().replace(tzinfo=None), status=ExecutionStatus.RUNNING, triggered_by="ADMIN")
    )
    db_session.commit()

    resposta = _importar(admin_client, token, itens=[7001])

    assert resposta.status_code == 409
    assert resposta.json() == {"detail": "Já existe uma importação em andamento"}
    assert fonte_falsa.chamadas == []

    # Uma execução "em andamento" que ficou para trás (o processo caiu) deixa de bloquear depois de 12 h.
    relogio.avancar(hours=13)
    liberada = _importar(admin_client, token, itens=[7001])
    assert liberada.status_code == 202
    assert _resumo(admin_client, token, liberada)["status"] == "CONCLUIDA"
    assert db_session.query(ScraperExecutionLog).filter(ScraperExecutionLog.failure_stage == "INTERNA").count() == 1


def test_cu10_c1_so_o_admin_importa_e_consulta(admin_client, db_session, fonte_falsa):
    token_comum = cadastrar_e_entrar(admin_client)  # papel "usuario"

    sem_sessao = admin_client.post("/api/admin/history-import", json={"regiao": "US"})
    usuario_comum = _importar(admin_client, token_comum)
    consulta = admin_client.get("/api/admin/history-import/1", headers=cabecalho(token_comum))
    lista = admin_client.get("/api/admin/history-import", headers=cabecalho(token_comum))

    assert sem_sessao.status_code == 401
    assert (usuario_comum.status_code, consulta.status_code, lista.status_code) == (403, 403, 403)
    assert usuario_comum.json() == {"detail": "Acesso restrito ao administrador"}
    assert fonte_falsa.chamadas == []


def test_cu10_c1_lista_as_importacoes_mais_recentes_e_recusa_id_desconhecido(admin_client, db_session, add_item, fonte_falsa):
    _itens(add_item, (8001,))
    fonte_falsa.com_dias(8001, dias(2))
    token = _token_de_admin(admin_client, db_session)
    primeira = _importar(admin_client, token, itens=[8001]).json()["id_execucao"]
    segunda = _importar(admin_client, token, itens=[8001]).json()["id_execucao"]

    lista = admin_client.get("/api/admin/history-import", headers=cabecalho(token))
    desconhecida = admin_client.get("/api/admin/history-import/999999", headers=cabecalho(token))

    assert [execucao["id_execucao"] for execucao in lista.json()] == [segunda, primeira]
    assert desconhecida.status_code == 404
    assert desconhecida.json() == {"detail": "Importação não encontrada"}


def test_cu10_c1_o_ritmo_entre_requisicoes_e_configuravel_rn23(monkeypatch):
    from src.services.limitador import INTERVALO_MINIMO_PADRAO, intervalo_minimo_configurado

    monkeypatch.delenv("UNDERMINE_INTERVALO_MINIMO_SEGUNDOS", raising=False)
    assert intervalo_minimo_configurado() == INTERVALO_MINIMO_PADRAO  # o ritmo que a importação já tinha (~125/s)
    monkeypatch.setenv("UNDERMINE_INTERVALO_MINIMO_SEGUNDOS", "0.25")
    assert intervalo_minimo_configurado() == 0.25
    for invalido in ("rapido", "-1"):
        monkeypatch.setenv("UNDERMINE_INTERVALO_MINIMO_SEGUNDOS", invalido)
        assert intervalo_minimo_configurado() == INTERVALO_MINIMO_PADRAO


def test_cu10_c1_a_recuperacao_do_worker_importa_incrementalmente_os_itens_ativos(db_session, add_item, fonte_falsa):
    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9901, "Item A")
    fonte_falsa.com_dias(9901, dias(3))

    ImportacaoHistoricoService(db_session).recuperar()

    assert db_session.query(HistoricalItemPrice).count() == 3
    log = db_session.query(ScraperExecutionLog).one()
    assert (log.triggered_by, log.status, log.region) == ("RECUPERACAO", ExecutionStatus.SUCCESS, REGIAO)
    assert log.execution_end - log.execution_start < timedelta(minutes=1)


def test_cu10_c1_a_importacao_do_admin_nao_conta_como_recuperacao_do_historico(db_session, add_item, fonte_falsa, relogio):
    """A regra de 48 h do CU09 olha só a recuperação automática: a importação do Admin pode cobrir poucos itens."""
    from src.repositories.mercado_repository import MercadoRepository
    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9911, "Item A")
    fonte_falsa.com_dias(9911, dias(3))
    servico = ImportacaoHistoricoService(db_session, relogio)
    pedido = servico.validar("US", 3209, [9911])
    servico.executar(servico.registrar_inicio(pedido, "ADMIN"), pedido)
    repositorio = MercadoRepository(db_session)

    assert repositorio.ultima_coleta() is None and repositorio.ultimo_backfill_iniciado() is None

    servico.recuperar()

    assert repositorio.ultima_coleta() is not None and repositorio.ultimo_backfill_iniciado() is not None


# ---------------------------------------------------------------- importação diária (série diária para o CU11)

def _pontos(db_session) -> dict:
    return {(p.timestamp, p.granularidade): (p.price, p.quantity) for p in db_session.query(HistoricalItemPrice)}


def test_cu10_c1_importacao_diaria_grava_so_dias_encerrados(db_session, add_item, fonte_falsa, relogio):
    """Importação diária do worker: incremental, para os reinos monitorados, gravando só os dias encerrados. O agregado
    diário da data UTC corrente (28/09 no relógio falso) ainda está em formação e fica para o dia seguinte; os registros
    horários do dia entram."""
    from datetime import datetime

    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9921, "Item A")
    fonte_falsa.com_dias(9921, [datetime(2026, 9, 26), datetime(2026, 9, 27), datetime(2026, 9, 28)],
                         horarios=[datetime(2026, 9, 28, 5), datetime(2026, 9, 28, 6)])

    resumos = ImportacaoHistoricoService(db_session, relogio).importar_diariamente()

    assert set(_pontos(db_session)) == {
        (datetime(2026, 9, 26), "DIARIA"), (datetime(2026, 9, 27), "DIARIA"),
        (datetime(2026, 9, 28, 5), "HORARIA"), (datetime(2026, 9, 28, 6), "HORARIA"),
    }
    log = db_session.query(ScraperExecutionLog).one()
    assert (log.triggered_by, log.status, log.region) == ("DIARIA", ExecutionStatus.SUCCESS, REGIAO)
    assert [(r.registros_importados, r.registros_descartados) for r in resumos] == [(4, 0)]

    relogio.avancar(days=1)  # no dia seguinte o 28/09 está encerrado
    ImportacaoHistoricoService(db_session, relogio).importar_diariamente()
    assert (datetime(2026, 9, 28), "DIARIA") in _pontos(db_session)


def test_cu10_c1_importacao_incremental_regrava_o_dia_gravado_antes_de_terminar(db_session, add_item, fonte_falsa,
                                                                                 relogio):
    """Um agregado diário gravado antes de o dia terminar (o menor preço só cobria as primeiras horas, como o 19/10/2026
    da recuperação das 02:11 UTC) é regravado com o valor do dia completo na importação incremental seguinte. Nada mais
    muda: nem o registro horário do mesmo dia nem o diário fora da janela incremental. A importação do Admin não
    sobrescreve o que já existe."""
    from datetime import datetime

    from helpers_historico import dados_decodificados

    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9931, "Item A")
    db_session.add_all([
        HistoricalItemPrice(item_id=9931, region=REGIAO, timestamp=datetime(2026, 9, 27), price=150000, quantity=2,
                            origem="UNDERMINE", granularidade="DIARIA"),  # dia parcial
        HistoricalItemPrice(item_id=9931, region=REGIAO, timestamp=datetime(2026, 9, 20), price=777, quantity=1,
                            origem="UNDERMINE", granularidade="DIARIA"),  # fora da janela de 2 dias
        HistoricalItemPrice(item_id=9931, region=REGIAO, timestamp=datetime(2026, 9, 27, 1), price=555, quantity=9,
                            origem="UNDERMINE", granularidade="HORARIA"),
    ])
    db_session.commit()
    diarios = [datetime(2026, 9, 20), datetime(2026, 9, 26), datetime(2026, 9, 27)]
    fonte_falsa.com_dias(9931, diarios, horarios=[datetime(2026, 9, 27, 1)])  # dia completo: 100000 Cobre

    resumo = ImportacaoHistoricoService(db_session, relogio).importar_diariamente()[0]

    db_session.expire_all()
    pontos = _pontos(db_session)
    assert pontos[(datetime(2026, 9, 27), "DIARIA")] == (100000, 5)  # corrigido
    assert pontos[(datetime(2026, 9, 26), "DIARIA")] == (100000, 5)  # novo
    assert pontos[(datetime(2026, 9, 20), "DIARIA")] == (777, 1)
    assert pontos[(datetime(2026, 9, 27, 1), "HORARIA")] == (555, 9)
    assert (resumo.registros_importados, resumo.registros_duplicados) == (1, 2)

    fonte_falsa.series[9931] = (dados_decodificados(diarios, preco=200000), REGIAO)
    servico = ImportacaoHistoricoService(db_session, relogio)
    pedido = servico.validar("US", 3209, [9931])
    servico.executar(servico.registrar_inicio(pedido, "ADMIN"), pedido)
    db_session.expire_all()
    assert _pontos(db_session)[(datetime(2026, 9, 26), "DIARIA")] == (100000, 5)


def test_cu10_c1_importacao_diaria_nao_roda_com_outra_importacao_em_andamento(db_session, add_item, fonte_falsa,
                                                                              relogio):
    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9941, "Item A")
    fonte_falsa.com_dias(9941, dias(3))
    db_session.add(ScraperExecutionLog(execution_start=relogio().replace(tzinfo=None), status=ExecutionStatus.RUNNING,
                                       triggered_by="ADMIN", region=REGIAO))
    db_session.commit()

    assert ImportacaoHistoricoService(db_session, relogio).importar_diariamente() == []

    assert db_session.query(HistoricalItemPrice).count() == 0 and fonte_falsa.chamadas == []
    assert db_session.query(ScraperExecutionLog).count() == 1


def test_cu10_c1_importacao_diaria_perdida_e_reconhecida_pelo_ultimo_disparo(db_session):
    """Ligado às 08:00 de 20/10: o disparo das 02:00 foi perdido se nenhuma importação incremental (diária ou
    recuperação) concluiu depois dele. A importação do Admin, que pode cobrir poucos itens, não conta."""
    from datetime import datetime, timezone

    from apscheduler.triggers.cron import CronTrigger

    from src import worker

    gatilho = CronTrigger.from_crontab("0 2 * * *", timezone=timezone.utc)
    agora = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)

    def log(inicio: datetime, disparo: str, status=ExecutionStatus.SUCCESS) -> None:
        db_session.add(ScraperExecutionLog(execution_start=inicio, execution_end=inicio, status=status,
                                           triggered_by=disparo, region=REGIAO))
        db_session.commit()

    assert worker.importacao_diaria_perdida(gatilho, agora, db_session)  # nenhuma importação
    log(datetime(2026, 10, 19, 2, 0, 5), "DIARIA")  # a de ontem
    log(datetime(2026, 10, 20, 3, 0), "ADMIN")
    log(datetime(2026, 10, 20, 2, 0, 5), "DIARIA", ExecutionStatus.FAILED)
    assert worker.importacao_diaria_perdida(gatilho, agora, db_session)

    log(datetime(2026, 10, 20, 2, 0, 5), "DIARIA")
    assert not worker.importacao_diaria_perdida(gatilho, agora, db_session)
    assert not worker.importacao_diaria_perdida(gatilho, datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc), db_session)


def test_cu10_c1_importacao_diaria_tenta_de_novo_depois_de_um_deadlock(db_session, add_item, fonte_falsa, relogio,
                                                                       mocker):
    """A importação grava numa só transação e o ciclo da Blizzard (CU09) grava no mesmo índice: o PostgreSQL pode
    desfazê-la por deadlock (20/10/2026). É uma falha transitória: ela é tentada de novo uma vez."""
    import psycopg2.errors

    from src.services.importacao_historico import ImportacaoHistoricoService

    add_item(9951, "Item A")
    fonte_falsa.com_dias(9951, dias(3))
    gravar = backfill._insert_rows
    chamadas = {"total": 0}

    def deadlock_na_primeira(session, rows):
        chamadas["total"] += 1
        if chamadas["total"] == 1:
            raise psycopg2.errors.DeadlockDetected("deadlock detected")
        return gravar(session, rows)

    mocker.patch.object(backfill, "_insert_rows", deadlock_na_primeira)

    [resumo] = ImportacaoHistoricoService(db_session, relogio).importar_diariamente()

    assert (resumo.status, resumo.registros_importados) == ("CONCLUIDA", 3)
    logs = db_session.query(ScraperExecutionLog).order_by(ScraperExecutionLog.id).all()
    assert [(log.status, log.failure_stage) for log in logs] == [(ExecutionStatus.FAILED, "BANCO"),
                                                                 (ExecutionStatus.SUCCESS, None)]

    chamadas["total"] = 0  # outra falha de banco não é transitória: não há nova tentativa
    mocker.patch.object(backfill, "_insert_rows", side_effect=OperationalError("INSERT", {}, Exception("disk full")))
    db_session.query(HistoricalItemPrice).delete()
    db_session.commit()
    [falha] = ImportacaoHistoricoService(db_session, relogio).importar_diariamente()
    assert falha.status == "FALHA" and db_session.query(ScraperExecutionLog).count() == 3
