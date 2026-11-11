"""
Plano de testes do CU07 – Manter Alerta, um teste por fluxo do backend. Rodam contra um PostgreSQL temporário, com o
relógio falso (2026-09-28 12:00 UTC). Os fluxos de tela estão em frontend (`npm test`, arquivos `cu07-*`); o C3-FA1
(exclusão cancelada) é só de tela.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from helpers_auth import EMAIL, cabecalho, cadastrar_e_entrar, erro_de_banco, sem_detalhe_tecnico
from src.models.api_models import AlertaRequest
from src.models.favorito import AlertaPreco
from src.models.mercado import EstadoMercado, Leilao, Reino
from src.models.usuario import Usuario
from src.repositories.alerta_repository import AlertaRepository
from src.services.alerta_service import AlertaService
from src.services.erros import LimiteDeAlertasError

CRIADO = "Alerta criado com sucesso"
ATUALIZADO = "Alerta atualizado com sucesso"
EXCLUIDO = "Alerta excluído com sucesso"
FORA_DOS_FAVORITOS = "Para criar um alerta, adicione o item aos favoritos"
LIMITE_C1 = "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para criar outro"
LIMITE_C2 = "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para reativar este"
INVALIDOS = "Informe o tipo de gatilho, um preço-alvo maior que zero e o canal de notificação"
FE1_SALVAR = "Não foi possível salvar o alerta no momento. Tente novamente mais tarde"
FE1_EXCLUIR = "Não foi possível excluir o alerta no momento. Tente novamente mais tarde"
ITEM = 1001
UTC = timezone.utc


def _alerta(**campos) -> dict:
    return {"tipo": "COMPRA", "ouro": 17, "prata": 50, "cobre": 0, "canal": "AMBOS", **campos}


def _usuario(db, email: str = EMAIL) -> int:
    return db.query(Usuario).filter(Usuario.email == email).one().id_usuario


def _favoritar(cliente, token: str, item_id: int = ITEM) -> None:
    assert cliente.post(f"/api/favorites/{item_id}", headers=cabecalho(token)).status_code == 200


def _inserir(db, id_usuario: int, quantos: int, situacao: str = "ATIVO", item_id: int = ITEM) -> list[int]:
    """Alertas gravados direto (o disparo é do CU08)."""
    agora = datetime(2026, 9, 27, 12, tzinfo=UTC)
    alertas = [AlertaPreco(id_usuario=id_usuario, item_id=item_id, tipo="VENDA", preco_alvo=210_000, canal="WEB",
                           situacao=situacao, criado_em=agora, atualizado_em=agora,
                           disparado_em=agora if situacao == "DISPARADO" else None) for _ in range(quantos)]
    db.add_all(alertas)
    db.commit()
    return [a.id_alerta for a in alertas]


def _valor_de_mercado(db, relogio, item_id: int = ITEM, unitario: int = 179_500) -> None:
    ciclo = relogio() - timedelta(minutes=30)
    db.add(Reino(id_reino=3209, nome="reino 3209", regiao="US"))
    db.flush()
    db.add(EstadoMercado(mercado="mercado:3209", id_reino=3209, ultima_atualizacao_em=ciclo))
    db.add(Leilao(id_leilao_origem=1, id_reino=3209, item_id=item_id, preco_unitario=unitario, preco_buyout=unitario,
                  quantidade=1, situacao="ATIVO", data_ingestao=ciclo))
    db.commit()


def _do_banco(db, id_alerta: int) -> AlertaPreco:
    db.expire_all()
    return db.get(AlertaPreco, id_alerta)


# ---------------------------------------------------------------------- C1: criar alerta de preço


def test_cu07_c1_fluxo_principal_cria_alerta(favoritos_client, db_session, relogio):
    """Passos 2 a 4: o formulário com o valor de mercado atual (RN06); 6 e 7: o preço-alvo convertido para Cobre (RN01) e
    o alerta "Ativo"; 8: a mensagem e o alerta na seção."""
    _valor_de_mercado(db_session, relogio)
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)

    formulario = favoritos_client.get(f"/api/items/{ITEM}/alerts/new", headers=cabecalho(token))
    criado = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=_alerta())
    venda = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token),
                                  json=_alerta(tipo="VENDA", ouro=21, prata=0, cobre=5, canal="WEB"))
    secao = favoritos_client.get(f"/api/items/{ITEM}/alerts", headers=cabecalho(token)).json()

    assert (formulario.status_code, formulario.json()["market_value"]) == (200, 179_500)
    assert criado.status_code == 201 and criado.json()["message"] == CRIADO
    assert {k: criado.json()["alerta"][k] for k in ("tipo", "preco_alvo", "canal", "situacao")} == {
        "tipo": "COMPRA", "preco_alvo": 175_000, "canal": "AMBOS", "situacao": "ATIVO"}  # 17g 50s = 175.000 Cobre
    assert venda.json()["alerta"]["preco_alvo"] == 210_005
    assert [(a["tipo"], a["preco_alvo"]) for a in secao["alertas"]] == [("COMPRA", 175_000), ("VENDA", 210_005)]
    assert (secao["ativos_do_usuario"], secao["limite"]) == (2, 20)


def test_cu07_c1_fa1_item_fora_dos_favoritos(favoritos_client, db_session):
    """1.1 e 1.2: sem o item nos favoritos, a mensagem do cenário, antes do formulário e na gravação; 1.3 e 1.4:
    favoritado (CU06-C1), o fluxo segue para a cota e o formulário."""
    token = cadastrar_e_entrar(favoritos_client)

    antes = favoritos_client.get(f"/api/items/{ITEM}/alerts/new", headers=cabecalho(token))
    gravacao = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=_alerta())
    _favoritar(favoritos_client, token)
    depois = favoritos_client.get(f"/api/items/{ITEM}/alerts/new", headers=cabecalho(token))

    assert (antes.status_code, antes.json()) == (409, {"detail": FORA_DOS_FAVORITOS})
    assert (gravacao.status_code, gravacao.json()) == (409, {"detail": FORA_DOS_FAVORITOS})
    assert depois.status_code == 200
    assert db_session.query(AlertaPreco).count() == 0


def test_cu07_c1_fa2_limite_de_alertas_rn08(favoritos_client, db_session):
    """2.1 e 2.2 (RN08): com 20 alertas ativos em todos os itens, a mensagem do cenário, antes do formulário e na
    gravação. Os disparados não contam."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    _favoritar(favoritos_client, token, 1002)
    usuario = _usuario(db_session)
    _inserir(db_session, usuario, 15)
    _inserir(db_session, usuario, 4, item_id=1002)
    _inserir(db_session, usuario, 3, "DISPARADO")

    com_19 = favoritos_client.get(f"/api/items/{ITEM}/alerts/new", headers=cabecalho(token))
    o_20 = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=_alerta())
    antes = favoritos_client.get(f"/api/items/{ITEM}/alerts/new", headers=cabecalho(token))
    gravacao = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=_alerta())

    assert (com_19.status_code, o_20.status_code) == (200, 201)
    assert (antes.status_code, antes.json()) == (409, {"detail": LIMITE_C1})
    assert (gravacao.status_code, gravacao.json()) == (409, {"detail": LIMITE_C1})
    assert db_session.query(AlertaPreco).filter(AlertaPreco.situacao == "ATIVO").count() == 20


@pytest.mark.parametrize("dados", [
    _alerta(tipo=None), _alerta(canal=None), _alerta(tipo="TALVEZ"), _alerta(canal="SMS"),
    _alerta(ouro=0, prata=0, cobre=0), _alerta(ouro=None, prata=None, cobre=None), _alerta(ouro=-1),
    _alerta(prata=100), _alerta(cobre=150), _alerta(ouro="dez"), _alerta(ouro=1.5),
], ids=["sem-tipo", "sem-canal", "tipo-desconhecido", "canal-desconhecido", "zero", "vazio", "negativo",
        "prata-acima-de-99", "cobre-acima-de-99", "texto", "fracao"])
def test_cu07_c1_fa3_dados_invalidos(favoritos_client, db_session, dados):
    """3.1 e 3.2: a mensagem do cenário (e não o erro padrão de validação), e nada é gravado."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)

    resposta = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=dados)

    assert (resposta.status_code, resposta.json()) == (422, {"detail": INVALIDOS})
    assert db_session.query(AlertaPreco).count() == 0


def test_cu07_c1_fe1_falha_no_banco(favoritos_client, db_session, mocker):
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    mocker.patch.object(AlertaRepository, "incluir", side_effect=erro_de_banco())

    resposta = favoritos_client.post(f"/api/items/{ITEM}/alerts", headers=cabecalho(token), json=_alerta())

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_SALVAR})
    assert sem_detalhe_tecnico(resposta)
    assert db_session.query(AlertaPreco).count() == 0


# ---------------------------------------------------------------------- C2: alterar ou reativar alerta de preço


def test_cu07_c2_fluxo_principal_altera_alerta(favoritos_client, db_session, relogio):
    """Passo 2: os dados atuais e o valor de mercado atual; 4 e 5: os dados novos, "Ativo"; 6: a mensagem."""
    _valor_de_mercado(db_session, relogio)
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1)

    formulario = favoritos_client.get(f"/api/alerts/{id_alerta}/edit", headers=cabecalho(token)).json()
    resposta = favoritos_client.put(f"/api/alerts/{id_alerta}", headers=cabecalho(token),
                                    json=_alerta(tipo="COMPRA", ouro=16, prata=0, cobre=0, canal="EMAIL"))

    assert formulario["market_value"] == 179_500
    assert {k: formulario["alerta"][k] for k in ("tipo", "preco_alvo", "canal")} == {"tipo": "VENDA", "preco_alvo": 210_000,
                                                                                    "canal": "WEB"}
    assert (resposta.status_code, resposta.json()["message"]) == (200, ATUALIZADO)
    alerta = _do_banco(db_session, id_alerta)
    assert (alerta.tipo, alerta.preco_alvo, alerta.canal, alerta.situacao) == ("COMPRA", 160_000, "EMAIL", "ATIVO")
    assert alerta.atualizado_em == relogio()


def test_cu07_c2_fa1_reativa_alerta_disparado(favoritos_client, db_session):
    """1.1 a 1.3: o alerta disparado (CU08) abre para edição se o usuário estiver abaixo da cota; salvo, volta a "Ativo",
    sem a data do disparo."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1, "DISPARADO")

    formulario = favoritos_client.get(f"/api/alerts/{id_alerta}/edit", headers=cabecalho(token))
    resposta = favoritos_client.put(f"/api/alerts/{id_alerta}", headers=cabecalho(token), json=_alerta())

    assert formulario.status_code == 200 and formulario.json()["alerta"]["situacao"] == "DISPARADO"
    assert resposta.status_code == 200 and resposta.json()["alerta"]["situacao"] == "ATIVO"
    alerta = _do_banco(db_session, id_alerta)
    assert (alerta.situacao, alerta.disparado_em) == ("ATIVO", None)


def test_cu07_c2_fa2_limite_na_reativacao_rn08(favoritos_client, db_session):
    """2.1 e 2.2 (RN08): com 20 ativos, o disparado não abre para reativar, nem é reativado na gravação. Um alerta já
    ativo continua editável (não muda a contagem)."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    usuario = _usuario(db_session)
    ativos = _inserir(db_session, usuario, 20)
    [disparado] = _inserir(db_session, usuario, 1, "DISPARADO")

    formulario = favoritos_client.get(f"/api/alerts/{disparado}/edit", headers=cabecalho(token))
    gravacao = favoritos_client.put(f"/api/alerts/{disparado}", headers=cabecalho(token), json=_alerta())
    ativo = favoritos_client.put(f"/api/alerts/{ativos[0]}", headers=cabecalho(token), json=_alerta())

    assert (formulario.status_code, formulario.json()) == (409, {"detail": LIMITE_C2})
    assert (gravacao.status_code, gravacao.json()) == (409, {"detail": LIMITE_C2})
    assert _do_banco(db_session, disparado).situacao == "DISPARADO"
    assert ativo.status_code == 200


def test_cu07_c2_fa3_dados_invalidos(favoritos_client, db_session):
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1)

    resposta = favoritos_client.put(f"/api/alerts/{id_alerta}", headers=cabecalho(token),
                                    json=_alerta(ouro=0, prata=0, cobre=0))

    assert (resposta.status_code, resposta.json()) == (422, {"detail": INVALIDOS})
    assert _do_banco(db_session, id_alerta).preco_alvo == 210_000


def test_cu07_c2_fe1_falha_mantem_dados(favoritos_client, db_session, mocker):
    """1.1 e 1.2: a gravação falha depois de os campos terem sido trocados: tudo é desfeito, e o alerta mantém os dados
    anteriores (inclusive o disparo)."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1, "DISPARADO")
    original = AlertaRepository.atualizar

    def atualizar_e_falhar(repositorio, alerta, campos):
        original(repositorio, alerta, campos)
        raise erro_de_banco()

    mocker.patch.object(AlertaRepository, "atualizar", atualizar_e_falhar)
    resposta = favoritos_client.put(f"/api/alerts/{id_alerta}", headers=cabecalho(token), json=_alerta(canal="EMAIL"))

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_SALVAR})
    alerta = _do_banco(db_session, id_alerta)
    assert (alerta.tipo, alerta.preco_alvo, alerta.canal, alerta.situacao) == ("VENDA", 210_000, "WEB", "DISPARADO")


# ---------------------------------------------------------------------- C3: excluir alerta de preço


def test_cu07_c3_fluxo_principal_exclui_alerta(favoritos_client, db_session):
    """Passos 4 e 5 (a confirmação do passo 2 é da tela): o alerta sai, e a seção é atualizada."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    primeiro, segundo = _inserir(db_session, _usuario(db_session), 2)

    resposta = favoritos_client.delete(f"/api/alerts/{primeiro}", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (200, {"message": EXCLUIDO})
    secao = favoritos_client.get(f"/api/items/{ITEM}/alerts", headers=cabecalho(token)).json()
    assert [a["id_alerta"] for a in secao["alertas"]] == [segundo]


def test_cu07_c3_fe1_falha_mantem_alerta(favoritos_client, db_session, mocker):
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1)
    mocker.patch.object(AlertaRepository, "remover", side_effect=erro_de_banco())

    resposta = favoritos_client.delete(f"/api/alerts/{id_alerta}", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_EXCLUIR})
    assert _do_banco(db_session, id_alerta) is not None  # 1.2: o alerta é mantido


# ---------------------------------------------------------------------- regras gerais


def test_cu07_so_o_dono_altera_e_exclui_o_alerta(favoritos_client, db_session):
    """Os alertas de outro usuário não aparecem nem podem ser abertos, alterados ou excluídos (404)."""
    dono = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, dono)
    [id_alerta] = _inserir(db_session, _usuario(db_session), 1)
    intruso = cadastrar_e_entrar(favoritos_client, email="intruso@exemplo.com")
    _favoritar(favoritos_client, intruso)

    respostas = [
        favoritos_client.get(f"/api/alerts/{id_alerta}/edit", headers=cabecalho(intruso)),
        favoritos_client.put(f"/api/alerts/{id_alerta}", headers=cabecalho(intruso), json=_alerta()),
        favoritos_client.delete(f"/api/alerts/{id_alerta}", headers=cabecalho(intruso)),
    ]

    assert [r.status_code for r in respostas] == [404, 404, 404]
    assert favoritos_client.get(f"/api/items/{ITEM}/alerts", headers=cabecalho(intruso)).json()["alertas"] == []
    alerta = _do_banco(db_session, id_alerta)
    assert (alerta.preco_alvo, alerta.canal) == (210_000, "WEB")
    assert favoritos_client.get(f"/api/items/{ITEM}/alerts").status_code == 401  # e tudo exige a sessão


def test_cu07_rn08_pedidos_simultaneos_nao_passam_do_limite(favoritos_client, db_session, pg_engine, relogio):
    """RN08: a contagem e a gravação ficam na mesma transação, com a linha do usuário travada. A sessão A trava o usuário
    e grava o 20º alerta; o pedido B, ao mesmo tempo, espera a trava e, depois do commit da A, recebe o FA2."""
    token = cadastrar_e_entrar(favoritos_client)
    _favoritar(favoritos_client, token)
    usuario = _usuario(db_session)
    _inserir(db_session, usuario, 19)
    nova_sessao = sessionmaker(bind=pg_engine)
    sessao_a, sessao_b = nova_sessao(), nova_sessao()
    resultado: dict[str, object] = {}

    def pedido_b() -> None:
        try:
            AlertaService(sessao_b, relogio).criar(usuario, ITEM, AlertaRequest(**_alerta()))
            resultado["b"] = "criado"
        except LimiteDeAlertasError as erro:
            resultado["b"] = erro.mensagem

    try:
        repositorio_a = AlertaRepository(sessao_a)
        repositorio_a.travar_usuario(usuario)
        assert repositorio_a.ativos(usuario) == 19
        agora = relogio()
        repositorio_a.incluir(AlertaPreco(id_usuario=usuario, item_id=ITEM, tipo="COMPRA", preco_alvo=1, canal="WEB",
                                          situacao="ATIVO", criado_em=agora, atualizado_em=agora))
        b = threading.Thread(target=pedido_b)
        b.start()
        time.sleep(0.5)
        assert b.is_alive()  # B espera a trava da linha do usuário
        sessao_a.commit()
        b.join(timeout=10)
    finally:
        sessao_a.close()
        sessao_b.close()

    assert resultado["b"] == LIMITE_C1
    db_session.expire_all()
    assert db_session.query(AlertaPreco).filter(AlertaPreco.situacao == "ATIVO").count() == 20
