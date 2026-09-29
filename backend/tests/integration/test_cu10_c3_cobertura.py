"""
Plano de testes do CU10 – Cadastrar Dados Passados, Cenário 03 (validar cobertura histórica dos itens), um teste por
fluxo, mais as regras do cálculo do maior período contínuo. Rodam contra um PostgreSQL temporário.
"""
from datetime import date, datetime, timedelta

import pytest
from helpers_auth import cabecalho, cadastrar_e_entrar
from sqlalchemy import insert
from sqlalchemy.exc import OperationalError

from src.models.cobertura import AptidaoTreinamento
from src.models.item import Item
from src.models.usuario import Usuario
from src.repositories.cobertura_repository import CoberturaRepository
from src.scraper.models import HistoricalItemPrice
from src.services.cobertura_service import CoberturaService

FE1 = "Não foi possível concluir a validação no momento. Tente novamente mais tarde"
INICIO = date(2025, 1, 1)


def _token_de_admin(cliente, db_session) -> str:
    token = cadastrar_e_entrar(cliente)
    db_session.query(Usuario).update({"role": "admin"})  # o papel é lido a cada requisição
    db_session.commit()
    return token


def _historico(db_session, item_id: int, inicio: date, dias: int, regiao: str = "3209", origem: str = "UNDERMINE", por_dia: int = 1):
    """`dias` dias seguidos de registros do item, com `por_dia` pontos em cada um (os horários da Blizzard têm vários)."""
    linhas = []
    for deslocamento in range(dias):
        for hora in range(por_dia):
            linhas.append({
                "item_id": item_id, "region": regiao, "origem": origem, "price": 1000, "quantity": 5,
                "granularidade": "DIARIA" if por_dia == 1 else "HORARIA",
                "timestamp": datetime.combine(inicio + timedelta(days=deslocamento), datetime.min.time()) + timedelta(hours=hora),
            })
    db_session.execute(insert(HistoricalItemPrice), linhas)
    db_session.commit()


def _validar(cliente, token, **consulta):
    return cliente.post("/api/admin/history-coverage", params=consulta, headers=cabecalho(token))


def _por_item(resposta) -> dict:
    return {item["item_id"]: item for item in resposta.json()["itens"]}


# ---------------------------------------------------------------------- fluxo principal e FA1


def test_cu10_c3_fluxo_principal_classifica_o_item_como_apto_ao_treinamento(admin_client, db_session, add_item):
    add_item(1001, "Linen Cloth")
    _historico(db_session, 1001, INICIO, 200)
    token = _token_de_admin(admin_client, db_session)

    resposta = _validar(admin_client, token)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert (corpo["total"], corpo["aptos"], corpo["inaptos"]) == (1, 1, 0)
    [item] = corpo["itens"]
    assert item["nome"] == "Linen Cloth" and item["situacao"] == "Apto ao treinamento" and item["apto"] is True
    assert (item["periodo_continuo_dias"], item["dias_com_dados"]) == (200, 200)  # passo 6: o período contínuo de cada um
    assert (item["inicio_periodo"], item["fim_periodo"]) == ("2025-01-01", "2025-07-19")
    gravado = db_session.get(AptidaoTreinamento, 1001)  # o CU11 lê daqui para liberar a predição (RN15)
    assert gravado.apto is True and gravado.periodo_continuo_dias == 200 and gravado.validado_em is not None


def test_cu10_c3_fa1_historico_insuficiente_bloqueia_o_item_e_segue_para_os_demais(admin_client, db_session, add_item):
    for item_id, nome in ((2001, "Copper Ore"), (2002, "Tin Ore"), (2003, "Iron Ore")):
        add_item(item_id, nome)
    _historico(db_session, 2001, INICIO, 100)  # menos de 6 meses
    _historico(db_session, 2002, INICIO, 250)  # o item seguinte continua sendo avaliado
    token = _token_de_admin(admin_client, db_session)

    corpo = _validar(admin_client, token).json()

    itens = {item["item_id"]: item for item in corpo["itens"]}
    assert (itens[2001]["situacao"], itens[2001]["apto"]) == ("Inapto ao treinamento", False)
    assert itens[2001]["periodo_continuo_dias"] == 100  # mesmo inapto, mostra o período que o item tem
    assert itens[2002]["situacao"] == "Apto ao treinamento"
    assert (corpo["total"], corpo["aptos"], corpo["inaptos"]) == (3, 1, 2)
    assert db_session.get(AptidaoTreinamento, 2001).apto is False  # a predição segue bloqueada


def test_cu10_c3_fe1_falha_de_banco_ao_recuperar_os_registros_mantem_a_classificacao_anterior(admin_client, db_session, add_item, mocker):
    add_item(3001, "Silk Cloth")
    _historico(db_session, 3001, INICIO, 200)
    token = _token_de_admin(admin_client, db_session)
    assert _validar(admin_client, token).status_code == 200  # a classificação anterior: apto

    _historico(db_session, 3001, INICIO - timedelta(days=400), 1)  # o histórico mudou, mas a validação vai falhar
    mocker.patch.object(
        CoberturaRepository, "periodos_continuos",
        side_effect=OperationalError("SELECT ... FROM historical_item_prices", {}, Exception("connection lost")),
    )

    resposta = _validar(admin_client, token)

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FE1}
    assert "connection lost" not in resposta.text
    db_session.expire_all()
    assert db_session.get(AptidaoTreinamento, 3001).periodo_continuo_dias == 200  # nada foi alterado


def test_cu10_c3_fe1_falha_de_banco_ao_gravar_desfaz_a_validacao(admin_client, db_session, add_item, mocker):
    add_item(3101, "Mageroyal")
    _historico(db_session, 3101, INICIO, 200)
    token = _token_de_admin(admin_client, db_session)
    _validar(admin_client, token)
    _historico(db_session, 3101, INICIO + timedelta(days=200), 100)  # agora seriam 300 dias

    gravar = CoberturaRepository.substituir_resultado

    def grava_e_cai(self, aptidoes):
        gravar(self, aptidoes)  # apaga a classificação anterior e insere a nova...
        raise OperationalError("COMMIT", {}, Exception("connection lost"))  # ...e a conexão cai antes de confirmar

    mocker.patch.object(CoberturaRepository, "substituir_resultado", grava_e_cai)

    resposta = _validar(admin_client, token)

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1})
    db_session.expire_all()
    assert db_session.get(AptidaoTreinamento, 3101).periodo_continuo_dias == 200  # continua a classificação anterior
    assert db_session.query(AptidaoTreinamento).count() == 1


# ---------------------------------------------------------------------- regras do cálculo do período contínuo (passo 3)


@pytest.mark.parametrize("dias, apto", [(179, False), (180, True), (181, True)])
def test_cu10_c3_passo4_o_minimo_e_de_seis_meses_rn15(admin_client, db_session, add_item, dias, apto):
    add_item(4001, "Peacebloom")
    _historico(db_session, 4001, INICIO, dias)
    token = _token_de_admin(admin_client, db_session)

    assert _por_item(_validar(admin_client, token))[4001]["apto"] is apto


def test_cu10_c3_passo3_lacunas_pequenas_nao_interrompem_o_periodo(admin_client, db_session, add_item):
    add_item(5001, "Com lacuna de 3 dias")
    add_item(5002, "Com lacuna de 4 dias")
    _historico(db_session, 5001, INICIO, 100)
    _historico(db_session, 5001, INICIO + timedelta(days=103), 100)  # faltam 3 dias (101 a 103): continua o mesmo período
    _historico(db_session, 5002, INICIO, 100)
    _historico(db_session, 5002, INICIO + timedelta(days=104), 100)  # faltam 4 dias: são dois períodos
    token = _token_de_admin(admin_client, db_session)

    itens = _por_item(_validar(admin_client, token))

    assert (itens[5001]["periodo_continuo_dias"], itens[5001]["dias_com_dados"], itens[5001]["apto"]) == (203, 200, True)
    assert (itens[5002]["periodo_continuo_dias"], itens[5002]["dias_com_dados"], itens[5002]["apto"]) == (100, 100, False)


def test_cu10_c3_passo3_vale_o_maior_periodo_e_no_empate_o_mais_recente(admin_client, db_session, add_item):
    add_item(6001, "Maior periodo no fim")
    add_item(6002, "Empate")
    _historico(db_session, 6001, INICIO, 120)
    _historico(db_session, 6001, INICIO + timedelta(days=130), 200)  # 10 dias de lacuna separam os dois períodos
    _historico(db_session, 6002, INICIO, 90)
    _historico(db_session, 6002, INICIO + timedelta(days=200), 90)
    token = _token_de_admin(admin_client, db_session)

    itens = _por_item(_validar(admin_client, token))

    assert (itens[6001]["inicio_periodo"], itens[6001]["periodo_continuo_dias"], itens[6001]["apto"]) == ("2025-05-11", 200, True)
    assert itens[6002]["inicio_periodo"] == "2025-07-20"  # empate: o mais recente


def test_cu10_c3_passo2_os_registros_de_todas_as_regioes_e_origens_contam_uma_vez_por_dia(admin_client, db_session, add_item):
    add_item(7001, "Item com duas origens")
    _historico(db_session, 7001, INICIO, 100, regiao="3209", origem="UNDERMINE")  # o histórico diário da Undermine
    _historico(db_session, 7001, INICIO + timedelta(days=100), 100, regiao="32512", origem="BLIZZARD", por_dia=24)  # horários
    _historico(db_session, 7001, INICIO + timedelta(days=50), 100, regiao="3210", origem="UNDERMINE")  # e dias repetidos em outra região
    token = _token_de_admin(admin_client, db_session)

    item = _por_item(_validar(admin_client, token))[7001]

    assert (item["periodo_continuo_dias"], item["dias_com_dados"], item["apto"]) == (200, 200, True)  # cada dia conta uma vez


def test_cu10_c3_item_sem_nenhum_registro_e_inapto_com_periodo_zero(admin_client, db_session, add_item):
    add_item(8001, "Sem historico")
    token = _token_de_admin(admin_client, db_session)

    item = _por_item(_validar(admin_client, token))[8001]

    assert (item["apto"], item["periodo_continuo_dias"], item["dias_com_dados"]) == (False, 0, 0)
    assert (item["inicio_periodo"], item["fim_periodo"]) == (None, None)


def test_cu10_c3_so_os_itens_ativos_do_wow_sao_avaliados_e_a_ficha_fica_de_fora(admin_client, db_session, add_item):
    add_item(9001, "Ativo")
    add_item(9002, "Inativo")
    add_item(122284, "WoW Token")
    add_item(9003, "Nao numerico")
    db_session.query(Item).filter(Item.external_item_id == "9002").update({"is_active": False})
    db_session.query(Item).filter(Item.external_item_id == "9003").update({"external_item_id": "abc"})
    db_session.commit()
    for item_id in (9001, 9002, 122284):
        _historico(db_session, item_id, INICIO, 200)
    token = _token_de_admin(admin_client, db_session)

    itens = _por_item(_validar(admin_client, token))

    assert set(itens) == {9001}


def test_cu10_c3_validar_de_novo_substitui_o_resultado_anterior(admin_client, db_session, add_item, relogio):
    add_item(10001, "Cresceu")
    add_item(10002, "Saiu")
    _historico(db_session, 10001, INICIO, 100)
    _historico(db_session, 10002, INICIO, 200)
    token = _token_de_admin(admin_client, db_session)
    primeira = _validar(admin_client, token).json()
    assert (primeira["aptos"], primeira["inaptos"]) == (1, 1)

    _historico(db_session, 10001, INICIO + timedelta(days=100), 100)  # 200 dias seguidos agora
    db_session.query(Item).filter(Item.external_item_id == "10002").update({"is_active": False})
    db_session.commit()
    relogio.avancar(hours=1)
    segunda = _validar(admin_client, token).json()

    assert (segunda["total"], segunda["aptos"], segunda["inaptos"]) == (1, 1, 0)
    assert [item["item_id"] for item in segunda["itens"]] == [10001]
    assert db_session.query(AptidaoTreinamento).count() == 1  # o item que saiu não deixa classificação para trás
    assert segunda["validado_em"] > primeira["validado_em"]


def test_cu10_c3_os_limites_sao_configuraveis_rn15(db_session, add_item):
    add_item(11001, "Item")
    _historico(db_session, 11001, INICIO, 40)
    _historico(db_session, 11001, INICIO + timedelta(days=42), 40)  # falta 1 dia

    padrao = CoberturaService(db_session).validar().itens[0]
    sem_tolerancia = CoberturaService(db_session, lacuna_maxima_dias=0, minimo_de_dias=40).validar().itens[0]
    exigente = CoberturaService(db_session, minimo_de_dias=90).validar().itens[0]

    assert (padrao.periodo_continuo_dias, padrao.apto) == (82, False)  # a lacuna de 1 dia não interrompe; 82 < 180
    assert (sem_tolerancia.periodo_continuo_dias, sem_tolerancia.apto) == (40, True)  # sem tolerância, o período é de 40 dias
    assert (exigente.periodo_continuo_dias, exigente.apto) == (82, False)


# ---------------------------------------------------------------------- consulta e acesso


def test_cu10_c3_consulta_a_ultima_validacao_com_filtro_e_paginacao(admin_client, db_session, add_item):
    for item_id in range(12001, 12006):
        add_item(item_id, f"Item {item_id}")
        _historico(db_session, item_id, INICIO, 100 + (item_id - 12001) * 50)  # 100, 150, 200, 250, 300 dias
    token = _token_de_admin(admin_client, db_session)

    vazio = admin_client.get("/api/admin/history-coverage", headers=cabecalho(token)).json()
    assert (vazio["total"], vazio["itens"], vazio["validado_em"]) == (0, [], None)  # antes de qualquer validação

    _validar(admin_client, token)
    aptos = admin_client.get("/api/admin/history-coverage?situacao=apto", headers=cabecalho(token)).json()
    inaptos = admin_client.get("/api/admin/history-coverage?situacao=INAPTO", headers=cabecalho(token)).json()
    pagina_2 = admin_client.get("/api/admin/history-coverage?tamanho=2&pagina=2", headers=cabecalho(token)).json()

    assert [i["item_id"] for i in aptos["itens"]] == [12005, 12004, 12003]  # do maior período para o menor
    assert [i["item_id"] for i in inaptos["itens"]] == [12002, 12001]
    assert (aptos["total"], aptos["aptos"], aptos["inaptos"]) == (5, 3, 2)  # os totais valem para a validação inteira
    assert [i["item_id"] for i in pagina_2["itens"]] == [12003, 12002] and pagina_2["pagina"] == 2


def test_cu10_c3_so_o_admin_valida_e_consulta(admin_client, db_session, add_item):
    token_comum = cadastrar_e_entrar(admin_client)  # papel "usuario"

    sem_sessao = admin_client.post("/api/admin/history-coverage")
    validar = _validar(admin_client, token_comum)
    consultar = admin_client.get("/api/admin/history-coverage", headers=cabecalho(token_comum))

    assert sem_sessao.status_code == 401
    assert (validar.status_code, consultar.status_code) == (403, 403)
    assert validar.json() == {"detail": "Acesso restrito ao administrador"}
    assert db_session.query(AptidaoTreinamento).count() == 0
