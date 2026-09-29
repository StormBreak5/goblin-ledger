"""
Plano de testes do CU04 – Visualizar Histórico, um teste por fluxo do backend. Rodam contra um PostgreSQL temporário, com o
relógio falso (2026-09-28 12:00 UTC). Os fluxos de tela estão em frontend (`npm test`).
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.controllers import item_controller
from src.models.item_price import ItemPrice
from src.models.mercado import EstadoMercado, Leilao, Reino
from src.repositories.mercado_repository import MercadoRepository
from src.scraper.models import HistoricalItemPrice
from src.services.item_service import ItemService

FA1 = "Dados Desatualizados"
FA2 = "Ainda não há dados históricos coletados suficientes para este item"
FE1 = "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde"
UTC = timezone.utc


def _sem_fuso(momento: datetime) -> datetime:
    return momento.astimezone(UTC).replace(tzinfo=None)


def _ponto(item_id: int, momento: datetime, price: int = 12_490, quantity: int = 8, region: str = "3209",
           origem: str = "BLIZZARD", granularidade: str = "HORARIA") -> HistoricalItemPrice:
    return HistoricalItemPrice(
        item_id=item_id, region=region, timestamp=_sem_fuso(momento), price=price, quantity=quantity,
        origem=origem, granularidade=granularidade,
    )


def _mercado(db, id_reino: int, ultima_atualizacao: datetime, desatualizado: bool = False, regiao: str = "US") -> None:
    db.add(Reino(id_reino=id_reino, nome=f"reino {id_reino}", regiao=regiao))
    db.flush()
    db.add(EstadoMercado(
        mercado=f"mercado:{id_reino}", id_reino=id_reino, ultima_atualizacao_em=ultima_atualizacao, desatualizado=desatualizado,
    ))
    db.commit()


def _historico(cliente, item_id: int, janela: str = "14D") -> dict:
    resposta = cliente.get(f"/api/items/{item_id}/history?window={janela}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# ---------------------------------------------------------------------- C1: renderizar histórico de preços


def test_cu04_c1_fluxo_principal_devolve_a_serie_e_o_valor_de_mercado_rn06(historico_client, db_session, relogio):
    agora = relogio()
    _mercado(db_session, 3209, agora - timedelta(minutes=30))
    dia = (agora - timedelta(days=2)).replace(hour=0, minute=0, second=0)
    db_session.add_all([
        _ponto(1001, dia, 10_000, 5, origem="UNDERMINE", granularidade="DIARIA"),
        _ponto(1001, agora - timedelta(hours=3), 12_000, 7),
        _ponto(1001, agora - timedelta(hours=1), 12_490, 9),
    ])
    for id_leilao, unitario, quantidade in ((1, 100, 1), (2, 200, 2), (3, 300, 1), (4, 400, 6)):  # último ciclo do reino
        db_session.add(Leilao(
            id_leilao_origem=id_leilao, id_reino=3209, item_id=1001, preco_buyout=unitario * quantidade,
            preco_unitario=unitario, quantidade=quantidade, situacao="ATIVO", data_ingestao=agora - timedelta(minutes=30),
        ))
    db_session.commit()

    historico = _historico(historico_client, 1001)
    atual = historico_client.get("/api/items/1001/current-auctions").json()

    assert historico["janela"] == "14D"
    assert [ponto["price"] for ponto in historico["pontos"]] == [10_000, 12_000, 12_490]  # Cobre (RN01), do mais antigo
    assert [ponto["granularity"] for ponto in historico["pontos"]] == ["DIARIA", "HORARIA", "HORARIA"]
    assert historico["pontos"][2]["quantity"] == 9
    assert (historico["desatualizado"], historico["avisos"]) == (False, [])
    assert _instante(historico["ultima_atualizacao_em"]) == agora - timedelta(minutes=30)
    # Passo 3 / RN06: o valor de mercado é o 1º quartil ponderado (200), e o menor preço (100) segue disponível.
    assert (atual["market_value"], atual["min_price"], atual["total_quantity"]) == (200, 100, 10)


def test_cu04_c1_o_historico_devolve_o_instante_em_utc_com_o_fuso_explicito(historico_client, db_session, relogio):
    """Sem a marca de fuso o navegador leria o horário como local (3 h de erro em GMT-3)."""
    agora = relogio()
    db_session.add(_ponto(1002, agora - timedelta(hours=2, minutes=30)))
    db_session.commit()

    [ponto] = _historico(historico_client, 1002)["pontos"]

    assert ponto["timestamp"].endswith("Z")  # UTC explícito
    assert _instante(ponto["timestamp"]) == agora - timedelta(hours=2, minutes=30)
    assert _instante(ponto["timestamp"]).astimezone(timezone(timedelta(hours=-3))).hour == 6  # 09:30 UTC = 06:30 em GMT-3


@pytest.mark.parametrize("idade, desatualizado", [(timedelta(hours=23, minutes=59), False), (timedelta(hours=24, minutes=1), True)])
def test_cu04_c1_fa1_dados_desatualizados_pelo_limiar_de_24_horas(historico_client, db_session, relogio, idade, desatualizado):
    agora = relogio()
    _mercado(db_session, 3209, agora - idade)
    db_session.add(_ponto(1003, agora - idade))
    db_session.commit()

    historico = _historico(historico_client, 1003)

    assert historico["desatualizado"] is desatualizado
    assert len(historico["pontos"]) == 1  # 1.2: o gráfico é desenhado normalmente, com os últimos dados
    esperado = [{"codigo": "DADOS_DESATUALIZADOS", "texto": FA1}] if desatualizado else []
    assert historico["avisos"] == esperado


def test_cu04_c1_fa1_mercado_sinalizado_por_falha_rn14(historico_client, db_session, relogio):
    agora = relogio()
    _mercado(db_session, 3209, agora - timedelta(minutes=10), desatualizado=True)  # o último ciclo falhou (CU09-FE1)
    db_session.add(_ponto(1004, agora - timedelta(minutes=10)))
    db_session.commit()

    historico = _historico(historico_client, 1004)

    assert historico["desatualizado"] is True
    assert [aviso["codigo"] for aviso in historico["avisos"]] == ["DADOS_DESATUALIZADOS"]


def test_cu04_c1_fa1_o_frescor_segue_o_mercado_do_item(historico_client, db_session, relogio):
    """RN14: a falha de um mercado não marca os itens de outro. Commodities ficam no "reino" 32512."""
    agora = relogio()
    _mercado(db_session, 3209, agora - timedelta(minutes=20))
    _mercado(db_session, 32512, agora - timedelta(hours=30))
    db_session.add_all([
        _ponto(1005, agora - timedelta(hours=1), region="3209"),  # item do reino
        _ponto(1006, agora - timedelta(hours=1), region="32512"),  # commodity
    ])
    db_session.commit()

    assert _historico(historico_client, 1005)["desatualizado"] is False
    assert _historico(historico_client, 1006)["desatualizado"] is True


def test_cu04_c1_fa1_item_que_o_ciclo_nunca_coletou_usa_o_ciclo_mais_recente_de_qualquer_mercado(historico_client, db_session, relogio):
    agora = relogio()
    db_session.add(_ponto(1007, agora - timedelta(days=3), origem="UNDERMINE", granularidade="DIARIA", region="3209"))
    db_session.commit()

    sem_nenhum_ciclo = _historico(historico_client, 1007, "30D")
    _mercado(db_session, 3209, agora - timedelta(hours=1))
    com_ciclo_recente = _historico(historico_client, 1007, "30D")

    assert sem_nenhum_ciclo["desatualizado"] is True and sem_nenhum_ciclo["ultima_atualizacao_em"] is None
    assert com_ciclo_recente["desatualizado"] is False


@pytest.mark.parametrize("idade, desatualizado", [(timedelta(hours=1), False), (timedelta(hours=30), True)])
def test_cu04_c1_fa1_ficha_do_wow_usa_a_idade_do_ultimo_preco(historico_client, db_session, relogio, idade, desatualizado):
    agora = relogio()
    db_session.add(ItemPrice(item_id=122284, region="us", price_copper=2_868_980_000, created_at=agora - idade))
    db_session.commit()

    historico = _historico(historico_client, 122284)

    assert historico["desatualizado"] is desatualizado
    assert _instante(historico["ultima_atualizacao_em"]) == agora - idade


def test_cu04_c1_fa2_item_sem_historico_registrado(historico_client, db_session, relogio):
    _mercado(db_session, 3209, relogio() - timedelta(hours=40))  # mesmo com o mercado atrasado, o FA2 termina o fluxo

    historico = _historico(historico_client, 424242)

    assert historico["pontos"] == []
    assert historico["avisos"] == [{"codigo": "SEM_HISTORICO", "texto": FA2}]


def test_cu04_c1_fe1_falha_de_banco_ao_recuperar_o_historico(db_session, relogio, mocker):
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    servico = ItemService(db_session, relogio)
    mocker.patch.object(
        servico, "get_item_history", side_effect=OperationalError("SELECT ...", {}, Exception('connection to server at "db" failed'))
    )
    app.dependency_overrides[item_controller.get_servico_do_historico] = lambda: servico
    cliente = TestClient(app, raise_server_exceptions=False)

    resposta = cliente.get("/api/items/1001/history")

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1})
    assert "connection" not in resposta.text  # o detalhe técnico só vai para o log


def test_cu04_c1_fe1_banco_fora_do_ar_ja_na_abertura_da_sessao(mocker):
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")  # sem substituir a dependência: usa a sessão real
    mocker.patch.object(item_controller, "get_session", side_effect=OperationalError("connect", {}, Exception("refused")))
    cliente = TestClient(app, raise_server_exceptions=False)

    historico = cliente.get("/api/items/1001/history")
    atuais = cliente.get("/api/items/1001/current-auctions")

    assert (historico.status_code, historico.json()) == (503, {"detail": FE1})
    assert (atuais.status_code, atuais.json()) == (503, {"detail": FE1})


def test_cu04_c1_o_mercado_do_item_vem_do_ponto_mais_recente_da_blizzard(db_session, relogio):
    agora = relogio()
    db_session.add_all([
        _ponto(1008, agora - timedelta(days=5), region="3209", origem="UNDERMINE", granularidade="DIARIA"),
        _ponto(1008, agora - timedelta(hours=9), region="3209"),
        _ponto(1008, agora - timedelta(hours=1), region="32512"),  # o item passou a ser coletado como commodity
    ])
    db_session.commit()

    repositorio = MercadoRepository(db_session)

    assert repositorio.mercado_do_item(1008) == 32512
    assert repositorio.mercado_do_item(9999) is None


# ---------------------------------------------------------------------- Ficha do WoW (preço em item_prices)


def test_cu04_c1_historico_da_ficha_vem_de_item_prices_em_cobre_e_utc(historico_client, db_session, relogio):
    agora = relogio()
    db_session.add_all([
        ItemPrice(item_id=122284, region="us", price_copper=2_600_000_000, created_at=agora - timedelta(days=30)),  # fora da janela
        ItemPrice(item_id=122284, region="us", price_copper=2_850_000_000, created_at=agora - timedelta(hours=3)),
        ItemPrice(item_id=122284, region="us", price_copper=2_868_980_000, created_at=agora - timedelta(minutes=20)),
        ItemPrice(item_id=122284, region="eu", price_copper=2_900_000_000, created_at=agora),  # outra região: não entra
    ])
    db_session.commit()

    antigo, novo = _historico(historico_client, 122284)["pontos"]

    assert (antigo["price"], novo["price"]) == (2_850_000_000, 2_868_980_000)  # Cobre (RN01): a tela converte
    assert _instante(novo["timestamp"]) == agora - timedelta(minutes=20)
    assert (novo["quantity"], novo["granularity"]) == (None, "HORARIA")  # sem volume; é um instante
    assert len(_historico(historico_client, 122284, "ALL")["pontos"]) == 3


def test_cu04_c1_preco_atual_da_ficha_e_o_da_ultima_coleta_sem_contagem_de_leiloes(historico_client, db_session, relogio):
    agora = relogio()
    db_session.add_all([
        ItemPrice(item_id=122284, region="us", price_copper=2_800_000_000, created_at=agora - timedelta(hours=1)),
        ItemPrice(item_id=122284, region="us", price_copper=2_868_980_000, created_at=agora),
    ])
    db_session.commit()

    resposta = historico_client.get("/api/items/122284/current-auctions")

    assert resposta.json() == {"min_price": 2_868_980_000, "total_quantity": None, "market_value": 2_868_980_000}


def test_cu04_c1_ficha_sem_nenhuma_coleta_ainda(historico_client):
    assert _historico(historico_client, 122284)["pontos"] == []
    assert historico_client.get("/api/items/122284/current-auctions").json() == {
        "min_price": 0, "total_quantity": None, "market_value": None,
    }


def test_cu04_c1_os_demais_itens_continuam_lendo_o_historico_de_leiloes(historico_client, db_session, relogio):
    agora = relogio()
    db_session.add(_ponto(39354, agora, price=12_490, quantity=8))
    db_session.add(ItemPrice(item_id=39354, region="us", price_copper=2_868_980_000, created_at=agora))  # só vale para a Ficha
    db_session.commit()

    [ponto] = _historico(historico_client, 39354)["pontos"]
    atual = historico_client.get("/api/items/39354/current-auctions").json()

    assert (ponto["price"], ponto["quantity"]) == (12_490, 8)
    assert atual == {"min_price": 0, "total_quantity": 0, "market_value": None}  # sem leilões no último ciclo
