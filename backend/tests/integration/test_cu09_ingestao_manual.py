"""
Plano de testes do CU09 – Cenário 04 (executar ingestão manual pelo Admin) e o estado de frescor dos mercados
(RN09 / RN14). Rodam contra um PostgreSQL temporário; a API da Blizzard e o relógio são falsos.
"""
from datetime import datetime, timedelta

from helpers_auth import cabecalho, cadastrar_e_entrar
from helpers_ingestao import leilao_de_commodity, leilao_de_reino
from src.models.mercado import CicloIngestao, Leilao
from src.models.usuario import Usuario
from src.services.api_client import ApiIndisponivelError


def _token_de_admin(cliente, db_session) -> str:
    token = cadastrar_e_entrar(cliente)
    db_session.query(Usuario).update({"role": "admin"})  # o papel é lido a cada requisição
    db_session.commit()
    return token


def _ingerir(cliente, token, **corpo):
    return cliente.post("/api/admin/ingestion", json={"regiao": "US", **corpo}, headers=cabecalho(token))


def test_cu09_c4_fluxo_principal_ingestao_manual_do_admin(admin_client, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100), leilao_de_reino(2, 1002, 300)]}
    cliente_blizzard.payload_das_commodities = {"auctions": [leilao_de_commodity(9, 2001, 50, 20), {"id": 10}]}
    token = _token_de_admin(admin_client, db_session)

    resposta = _ingerir(admin_client, token)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [(m["mercado"], m["status"]) for m in corpo["mercados"]] == [
        ("auctions:us:3209", "SUCESSO"), ("commodities:us", "SUCESSO"),
    ]
    # Passo 4: o resumo traz os registros coletados, descartados e os itens atualizados.
    assert (corpo["leiloes_coletados"], corpo["leiloes_descartados"], corpo["itens_atualizados"]) == (3, 1, 3)
    assert {ciclo.origem for ciclo in db_session.query(CicloIngestao)} == {"MANUAL"}
    assert db_session.query(Leilao).count() == 3


def test_cu09_c4_ingestao_de_um_reino_informado_nao_coleta_as_commodities(admin_client, cliente_blizzard, db_session):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    token = _token_de_admin(admin_client, db_session)

    resposta = _ingerir(admin_client, token, reino=3209)

    assert [m["mercado"] for m in resposta.json()["mercados"]] == ["auctions:us:3209"]
    assert cliente_blizzard.chamadas == ["auctions:us:3209"]


def test_cu09_c4_fa1_intervalo_minimo_informa_horario(admin_client, cliente_blizzard, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    primeira = relogio()
    assert _ingerir(admin_client, token).status_code == 200
    relogio.avancar(minutes=15)

    resposta = _ingerir(admin_client, token)

    assert resposta.status_code == 200
    for mercado in resposta.json()["mercados"]:
        assert mercado["status"] == "CANCELADO"
        assert datetime.fromisoformat(mercado["proxima_permitida"]) == primeira + timedelta(minutes=60)  # horário liberado
    assert len(cliente_blizzard.chamadas) == 2  # só as duas chamadas do primeiro pedido: a API não foi consultada


def test_cu09_c4_fe1_falha_informa_etapa_e_erro(admin_client, cliente_blizzard, db_session):
    token = _token_de_admin(admin_client, db_session)
    cliente_blizzard.erro = ApiIndisponivelError("A API não respondeu após 4 tentativas: HTTP 503")

    resposta = _ingerir(admin_client, token)

    assert resposta.status_code == 200
    for mercado in resposta.json()["mercados"]:
        assert mercado["status"] == "FALHA" and mercado["etapa_da_falha"] == "COLETA"
        assert "HTTP 503" in mercado["erro"]  # o erro registrado em log


def test_cu09_c4_so_o_admin_executa_a_ingestao(admin_client, cliente_blizzard, db_session):
    token_comum = cadastrar_e_entrar(admin_client)  # papel "usuario"

    sem_sessao = admin_client.post("/api/admin/ingestion", json={"regiao": "US"})
    usuario_comum = _ingerir(admin_client, token_comum)

    assert sem_sessao.status_code == 401
    assert usuario_comum.status_code == 403
    assert usuario_comum.json() == {"detail": "Acesso restrito ao administrador"}
    assert cliente_blizzard.chamadas == []


def test_cu09_c4_regiao_fora_de_us_eu_e_recusada_rn11(admin_client, cliente_blizzard, db_session):
    token = _token_de_admin(admin_client, db_session)

    for corpo in ({"regiao": "CN"}, {"regiao": ""}, {"regiao": "EU"}):  # EU não tem mercado monitorado por padrão
        resposta = admin_client.post("/api/admin/ingestion", json=corpo, headers=cabecalho(token))
        assert resposta.status_code == 422, corpo
        assert resposta.json() == {"detail": "Informe uma região válida (US ou EU) com mercados monitorados"}

    assert cliente_blizzard.chamadas == []


def test_cu09_estado_do_mercado_expoe_o_frescor_rn09_e_a_sinalizacao_rn14(admin_client, cliente_blizzard, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    momento = relogio()
    _ingerir(admin_client, token, reino=3209)
    relogio.avancar(minutes=61)
    cliente_blizzard.erro = ApiIndisponivelError("HTTP 503")
    _ingerir(admin_client, token, reino=3209)

    resposta = admin_client.get("/api/market/status")  # público: o dashboard precisa dele

    assert resposta.status_code == 200
    [estado] = resposta.json()
    assert estado["mercado"] == "auctions:us:3209" and estado["desatualizado"] is True
    assert datetime.fromisoformat(estado["ultima_atualizacao_em"]) == momento  # dado do último ciclo bem-sucedido
    assert datetime.fromisoformat(estado["ultima_falha_em"]) == relogio()
