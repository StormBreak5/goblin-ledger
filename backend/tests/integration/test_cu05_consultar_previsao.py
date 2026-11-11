"""
Plano de testes do CU05 – Consultar Previsão Preditiva, Cenário 01 (Exibir projeção de preços), um teste por fluxo do
backend. Rodam contra um PostgreSQL temporário, com o relógio falso (2026-09-28 12:00 UTC): hoje é 28/09 e o último dia
encerrado é 27/09. Os fluxos de tela (C1 a C3) estão em frontend (`npm test`). A comparação do critério de elegibilidade
com o do CU11 e o caminho treino → consolidação → projeção rodam no serviço `modelo` (tests/modelo).
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.controllers import item_controller
from src.models.mercado import Reino
from src.models.modelo import ModeloPreditivo, PredicaoDiaria, ProjecaoItem
from src.scraper.models import HistoricalItemPrice
from src.services.projecao_service import ProjecaoService

FA1 = "A projeção de preços ainda não está disponível"
FA2_RN02 = "Projeção indisponível: este item tem pouca quantidade ofertada para uma previsão confiável"
FA2_RN27 = "Projeção indisponível: este item ainda não tem histórico suficiente para a previsão"
FA3 = "Projeção indisponível: as previsões deste item não atingiram a precisão mínima exigida"
FA4 = "A projeção deste item está em avaliação e será exibida quando houver dados suficientes para medir a sua precisão"
FA5 = ("A projeção deste item está suspensa porque as previsões recentes ficaram abaixo da precisão mínima. Ela será "
       "reavaliada na próxima atualização do modelo")
FA6 = "A projeção deste item não está disponível no momento"
FA7 = "Projeção desatualizada"
FE1 = "Não foi possível carregar a projeção no momento. Tente novamente mais tarde"
ESTIMATIVA = "A projeção é uma estimativa estatística e não garante o preço futuro"

ONTEM = date(2026, 9, 27)  # o último dia encerrado no relógio falso
REINO, COMMODITIES = "3209", "32512"


@pytest.fixture
def projecao_client(db_session, relogio):
    """TestClient das rotas do item (CU05) sobre o PostgreSQL de teste, com o relógio falso."""
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    app.dependency_overrides[item_controller.get_servico_da_projecao] = lambda: ProjecaoService(db_session, relogio)
    return TestClient(app, raise_server_exceptions=False)


def _projecao(cliente, item_id: int) -> dict:
    resposta = cliente.get(f"/api/items/{item_id}/projection")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _modelo(db, versao: int = 1, vigente: bool = True, descartado: bool = False) -> int:
    db.add(ModeloPreditivo(
        versao=versao, regiao="US", treinado_em=datetime(2026, 9, 20, tzinfo=timezone.utc), data_inicio=date(2024, 1, 1),
        corte_validacao=date(2025, 7, 1), corte_teste=date(2026, 5, 1), data_fim=date(2026, 9, 19), itens_elegiveis=10,
        itens_treino=9, itens_avaliados=10, amostras_treino=1, amostras_validacao=1, amostras_teste=1, epocas=1,
        melhor_epoca=1, segundos_por_epoca=1.0, duracao_segundos=1.0, caminho_artefatos=f"/tmp/v{versao}",
        assinatura_normalizacao="x", vigente=vigente, descartado=descartado,
    ))
    db.commit()
    return versao


def _situacao(db, item_id: int, situacao: str, motivo: str | None = None, serie: str = REINO, versao: int = 1,
              mdape: float | None = 0.0849) -> None:
    db.add(ProjecaoItem(serie=serie, item_id=item_id, regiao="US", versao=versao, integra_treino=True, mdape=mdape,
                        situacao=situacao, motivo=motivo))
    db.commit()


def _predicoes(db, item_id: int, dia_de_referencia: date, precos: list[int], serie: str = REINO, versao: int = 1) -> None:
    gerada = datetime.combine(dia_de_referencia + timedelta(days=1), datetime.min.time(), timezone.utc) + timedelta(hours=3)
    for h, preco in enumerate(precos, start=1):
        db.add(PredicaoDiaria(data_previsao=dia_de_referencia, serie=serie, item_id=item_id, versao=versao, h=h,
                              data_prevista=dia_de_referencia + timedelta(days=h), preco_previsto=preco, criado_em=gerada))
    db.commit()


def _diaria(db, item_id: int, inicio: date, fim: date, preco: int = 10_000, quantidade: int = 100,
            serie: str = REINO) -> None:
    """Série diária da Undermine (RN16), um registro por dia às 00:00 UTC."""
    dia = inicio
    while dia <= fim:
        db.add(HistoricalItemPrice(item_id=item_id, region=serie, timestamp=datetime.combine(dia, datetime.min.time()),
                                   price=preco, quantity=quantidade, origem="UNDERMINE", granularidade="DIARIA"))
        dia += timedelta(days=1)
    db.commit()


def _regiao_us(db) -> None:
    db.add(Reino(id_reino=int(REINO), nome="reino 3209", regiao="US"))
    db.commit()


# ---------------------------------------------------------------------- C1: exibir projeção de preços


def test_cu05_c1_fluxo_principal_exibe_a_projecao_dos_proximos_7_dias(projecao_client, db_session):
    """Passos 2 a 7: a série liberada, as 7 predições da versão vigente a partir de hoje, o preço de partida de D, a
    variação, o erro típico e os textos. A série de reino bloqueada e a versão descartada não entram."""
    _modelo(db_session, 1)
    _modelo(db_session, 2, vigente=False, descartado=True)
    _situacao(db_session, 1001, "BLOQUEADA", "acima do limiar", serie=REINO)
    _situacao(db_session, 1001, "LIBERADA", serie=COMMODITIES, mdape=0.0849)
    _diaria(db_session, 1001, ONTEM - timedelta(days=5), ONTEM, preco=172_000, serie=COMMODITIES)
    _predicoes(db_session, 1001, ONTEM, [173_500, 175_500, 177_000, 178_500, 178_000, 179_500, 181_000], serie=COMMODITIES)
    _predicoes(db_session, 1001, ONTEM, [999_999] * 7, serie=COMMODITIES, versao=2)  # a versão descartada (RN26)
    _predicoes(db_session, 1001, ONTEM - timedelta(days=1), [1] * 7, serie=COMMODITIES)  # uma projeção mais antiga

    projecao = _projecao(projecao_client, 1001)

    assert (projecao["situacao"], projecao["mensagem"], projecao["desatualizada"]) == ("DISPONIVEL", None, False)
    assert (projecao["data_referencia"], projecao["preco_referencia"]) == ("2026-09-27", 172_000)  # passo 5: a partida
    assert [p["data_prevista"] for p in projecao["predicoes"]] == [f"2026-{d}" for d in (
        "09-28", "09-29", "09-30", "10-01", "10-02", "10-03", "10-04")]  # passo 3: os 7 dias, em ordem
    assert [p["preco_previsto"] for p in projecao["predicoes"]][:2] == [173_500, 175_500]  # em Cobre (RN01)
    assert [p["variacao_pct"] for p in projecao["predicoes"]][:3] == [0.9, 2.0, 2.9]  # passo 6: sobre o preço de D
    assert projecao["erro_tipico_pct"] == 8
    assert projecao["avisos"] == [  # passo 7
        {"codigo": "ORIGEM", "texto": "Projeção gerada em 28/09/2026, a partir do menor preço diário de 27/09/2026"},
        {"codigo": "ERRO_TIPICO", "texto": "Erro mediano de 8% nas previsões deste item"},
        {"codigo": "ESTIMATIVA", "texto": ESTIMATIVA},
    ]


def test_cu05_c1_fa1_modelo_nao_treinado(projecao_client, db_session):
    """1.1: não há versão vigente na região (só uma descartada); 1.2: a mensagem do cenário."""
    _modelo(db_session, 1, vigente=False, descartado=True)
    _situacao(db_session, 1002, "LIBERADA")
    _predicoes(db_session, 1002, ONTEM, [10_000] * 7)

    projecao = _projecao(projecao_client, 1002)

    assert (projecao["situacao"], projecao["mensagem"], projecao["predicoes"]) == ("MODELO_NAO_TREINADO", FA1, [])


def test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27(projecao_client, db_session):
    """2.1: o critério é recalculado na hora (RN02: quantidade média dos últimos 7 dias da base acima de 50; RN27: ao
    menos 60 dias de histórico diário até o último dia da base). 2.2: a mensagem do critério não atendido; os dois
    falhando, vale a da RN02. "Deixou de ser elegível" também é recalculado, e a série "Ignorada" é a RN27."""
    _modelo(db_session, 1)
    _regiao_us(db_session)
    _diaria(db_session, 1, ONTEM - timedelta(days=200), ONTEM)  # o último dia da base da região é 27/09
    _diaria(db_session, 2001, ONTEM - timedelta(days=100), ONTEM, quantidade=10)  # ilíquido
    _diaria(db_session, 2002, ONTEM - timedelta(days=30), ONTEM, quantidade=500)  # histórico curto
    _diaria(db_session, 2003, ONTEM - timedelta(days=20), ONTEM, quantidade=5)  # os dois
    _diaria(db_session, 2004, ONTEM - timedelta(days=100), ONTEM, quantidade=20)
    _situacao(db_session, 2004, "BLOQUEADA", "deixou de ser elegível")
    _situacao(db_session, 2005, "IGNORADA", "série insuficiente", mdape=None)
    db_session.add(HistoricalItemPrice(item_id=2006, region=REINO, timestamp=datetime(2026, 9, 27, 9), price=1, quantity=999,
                                       origem="BLIZZARD", granularidade="HORARIA"))  # só a coleta horária: sem série diária
    db_session.commit()

    esperado = {2001: FA2_RN02, 2002: FA2_RN27, 2003: FA2_RN02, 2004: FA2_RN02, 2005: FA2_RN27, 2006: FA2_RN02}
    obtido = {item: _projecao(projecao_client, item) for item in esperado}

    assert {item: p["mensagem"] for item, p in obtido.items()} == esperado
    assert {p["situacao"] for p in obtido.values()} == {"NAO_ELEGIVEL"}


def test_cu05_c1_fa3_projecao_reprovada_rn10(projecao_client, db_session):
    """3.1: a projeção está bloqueada pela RN10 (MdAPE acima de 15% ou não supera o ingênuo); 3.2: a mensagem."""
    _modelo(db_session, 1)
    _situacao(db_session, 3001, "BLOQUEADA", "acima do limiar")
    _situacao(db_session, 3002, "BLOQUEADA", "não supera o ingênuo")

    for item in (3001, 3002):
        projecao = _projecao(projecao_client, item)
        assert (projecao["situacao"], projecao["mensagem"]) == ("REPROVADA", FA3)


def test_cu05_c1_fa4_projecao_em_avaliacao(projecao_client, db_session):
    """4.1: o item ainda não tem os 30 dias de previsões avaliadas (RN10); 4.2: a mensagem. Decisão do autor (11/11/2026):
    o item que ficou elegível depois do último treino e ainda não foi avaliado também está "em avaliação"."""
    _modelo(db_session, 1)
    _regiao_us(db_session)
    _situacao(db_session, 4001, "BLOQUEADA", "avaliação insuficiente")
    _diaria(db_session, 4002, ONTEM - timedelta(days=100), ONTEM, quantidade=500)  # fora de projecao_item, mas elegível

    for item in (4001, 4002):
        projecao = _projecao(projecao_client, item)
        assert (projecao["situacao"], projecao["mensagem"]) == ("EM_AVALIACAO", FA4)


def test_cu05_c1_fa5_projecao_suspensa_rn13(projecao_client, db_session):
    """5.1: a projeção foi bloqueada pela degradação das previsões recentes (RN13, CU11-C3); 5.2: a mensagem."""
    _modelo(db_session, 1)
    _situacao(db_session, 5001, "BLOQUEADA", "degradação")
    _predicoes(db_session, 5001, ONTEM, [10_000] * 7)  # as predições antigas não aparecem

    projecao = _projecao(projecao_client, 5001)

    assert (projecao["situacao"], projecao["mensagem"], projecao["predicoes"]) == ("SUSPENSA", FA5, [])


def test_cu05_c1_fa6_projecao_nao_disponivel(projecao_client, db_session):
    """6.1: liberada, mas sem predição da versão vigente com dia previsto a partir de hoje (logo após a liberação, ou a
    predição não pôde ser gerada nas últimas consolidações); 6.2: a mensagem."""
    _modelo(db_session, 1)
    _situacao(db_session, 6001, "LIBERADA")  # nenhuma predição ainda
    _situacao(db_session, 6002, "LIBERADA")
    _diaria(db_session, 6002, date(2026, 9, 15), date(2026, 9, 20))
    _predicoes(db_session, 6002, date(2026, 9, 20), [10_000] * 7)  # previu de 21 a 27/09: tudo antes de hoje

    for item in (6001, 6002):
        projecao = _projecao(projecao_client, item)
        assert (projecao["situacao"], projecao["mensagem"], projecao["predicoes"]) == ("NAO_DISPONIVEL", FA6, [])


def test_cu05_c1_fa7_projecao_desatualizada(projecao_client, db_session):
    """7.1: o dia de referência (23/09) ficou mais de 2 dias atrás do último dia encerrado (27/09); 7.2: só os dias a
    partir de hoje, a partir do preço diário do dia de referência, com o alerta "Projeção desatualizada"."""
    _modelo(db_session, 1)
    _situacao(db_session, 7001, "LIBERADA")
    _diaria(db_session, 7001, date(2026, 9, 20), date(2026, 9, 23), preco=20_000)
    _predicoes(db_session, 7001, date(2026, 9, 23), [20_100, 20_200, 20_300, 20_400, 20_500, 20_600, 20_700])

    projecao = _projecao(projecao_client, 7001)

    assert (projecao["situacao"], projecao["desatualizada"]) == ("DISPONIVEL", True)
    assert (projecao["data_referencia"], projecao["preco_referencia"]) == ("2026-09-23", 20_000)
    assert [p["data_prevista"] for p in projecao["predicoes"]] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert [p["variacao_pct"] for p in projecao["predicoes"]] == [2.5, 3.0, 3.5]
    assert {"codigo": "DESATUALIZADA", "texto": FA7} in projecao["avisos"]

    # Com 2 dias de atraso (D = 25/09), ainda não está desatualizada.
    _situacao(db_session, 7002, "LIBERADA")
    _diaria(db_session, 7002, date(2026, 9, 25), date(2026, 9, 25))
    _predicoes(db_session, 7002, date(2026, 9, 25), [10_000] * 7)
    assert _projecao(projecao_client, 7002)["desatualizada"] is False


def test_cu05_c1_fe1_falha_no_banco(db_session, relogio, mocker):
    """1.1: falha de I/O ao recuperar a situação ou as predições; 1.2: 503 com a mensagem do cenário (o histórico, de
    outra rota, continua). O detalhe técnico só vai para o log. Também com o banco fora do ar já na abertura da sessão."""
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    servico = ProjecaoService(db_session, relogio)
    mocker.patch.object(servico.repositorio, "vigente",
                        side_effect=OperationalError("SELECT ...", {}, Exception('connection to server at "db" failed')))
    app.dependency_overrides[item_controller.get_servico_da_projecao] = lambda: servico
    resposta = TestClient(app, raise_server_exceptions=False).get("/api/items/1001/projection")

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1})
    assert "connection" not in resposta.text

    sem_banco = FastAPI()
    sem_banco.include_router(item_controller.router, prefix="/api")  # sem substituir a dependência: usa a sessão real
    mocker.patch.object(item_controller, "get_session", side_effect=OperationalError("connect", {}, Exception("refused")))
    resposta = TestClient(sem_banco, raise_server_exceptions=False).get("/api/items/1001/projection")

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1})
