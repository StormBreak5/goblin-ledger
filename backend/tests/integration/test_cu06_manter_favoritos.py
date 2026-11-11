"""
Plano de testes do CU06 – Manter Favoritos, um teste por fluxo do backend. Rodam contra um PostgreSQL temporário, com o
relógio falso (2026-09-28 12:00 UTC). Os fluxos de tela estão em frontend (`npm test`, arquivos `cu06-*`).
"""
from datetime import datetime, timedelta, timezone

from helpers_auth import EMAIL, SENHA, cabecalho, cadastrar_e_entrar, erro_de_banco, sem_detalhe_tecnico
from src.models.favorito import AlertaPreco, Favorito
from src.models.item import Item
from src.models.item_price import ItemPrice
from src.models.mercado import EstadoMercado, Leilao, Reino
from src.repositories.favorito_repository import FavoritoRepository
from src.scraper.models import HistoricalItemPrice

ADICIONADO = "Item adicionado aos favoritos"
REMOVIDO = "Item removido dos favoritos"
COM_ALERTAS = "Este item possui alertas de preço, que também serão excluídos. Deseja continuar?"
VAZIA = "Você ainda não tem itens favoritos. Use a busca para encontrar itens e favoritá-los"
FE1_ATUALIZAR = "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde"
FE1_LISTA = "Não foi possível carregar os seus favoritos no momento. Tente novamente mais tarde"
DESATUALIZADOS = "Dados Desatualizados"
FICHA = 122284
UTC = timezone.utc


def _item(db, item_id: int, nome: str) -> None:
    db.add(Item(game="wow", external_item_id=str(item_id), name=nome, icon_url=f"https://icones/{item_id}.jpg"))
    db.commit()


def _mercado(db, id_reino: int, ultima: datetime, desatualizado: bool = False) -> None:
    db.add(Reino(id_reino=id_reino, nome=f"reino {id_reino}", regiao="US"))
    db.flush()
    db.add(EstadoMercado(mercado=f"mercado:{id_reino}", id_reino=id_reino, ultima_atualizacao_em=ultima,
                         desatualizado=desatualizado))
    db.commit()


def _leilao(db, id_reino: int, item_id: int, unitario: int, quando: datetime, quantidade: int = 5) -> None:
    db.add(Leilao(id_leilao_origem=item_id * 10 + id_reino, id_reino=id_reino, item_id=item_id, preco_unitario=unitario,
                  preco_buyout=unitario * quantidade, quantidade=quantidade, situacao="ATIVO", data_ingestao=quando))
    db.commit()


def _ponto(db, item_id: int, id_reino: int, quando: datetime, preco: int) -> None:
    """O ponto horário do ciclo da Blizzard: o valor de mercado (RN06) do item naquele ciclo."""
    db.add(HistoricalItemPrice(item_id=item_id, region=str(id_reino), timestamp=quando.astimezone(UTC).replace(tzinfo=None),
                               price=preco, quantity=5, origem="BLIZZARD", granularidade="HORARIA"))
    db.commit()


def _alerta(db, id_usuario: int, item_id: int, situacao: str = "ATIVO") -> None:
    agora = datetime(2026, 9, 27, tzinfo=UTC)
    db.add(AlertaPreco(id_usuario=id_usuario, item_id=item_id, tipo="COMPRA", preco_alvo=10_000, canal="WEB",
                       situacao=situacao, criado_em=agora, atualizado_em=agora,
                       disparado_em=agora if situacao == "DISPARADO" else None))
    db.commit()


def _id_usuario(db, email: str = EMAIL) -> int:
    from src.models.usuario import Usuario
    return db.query(Usuario).filter(Usuario.email == email).one().id_usuario


def _favoritos(db) -> set[tuple[int, int]]:
    db.expire_all()
    return {(f.id_usuario, f.item_id) for f in db.query(Favorito).all()}


def _alertas(db) -> int:
    db.expire_all()
    return db.query(AlertaPreco).count()


# ---------------------------------------------------------------------- C1: adicionar item aos favoritos


def test_cu06_c1_fluxo_principal_adiciona_favorito(favoritos_client, db_session):
    _item(db_session, 1001, "Mycobloom")
    token = cadastrar_e_entrar(favoritos_client)

    antes = favoritos_client.get("/api/items/1001", headers=cabecalho(token)).json()
    resposta = favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))  # passo 1

    assert antes["favorito"] is False
    assert resposta.status_code == 200
    assert resposta.json() == {"item_id": 1001, "favorito": True, "message": ADICIONADO}  # passo 5
    assert _favoritos(db_session) == {(_id_usuario(db_session), 1001)}  # passo 4
    assert favoritos_client.get("/api/items/1001", headers=cabecalho(token)).json()["favorito"] is True  # "Favoritado"


def test_cu06_c1_fa1_usuario_nao_autenticado(favoritos_client, db_session):
    """1.1: sem sessão válida, nada é gravado (a tela leva ao login com a mensagem do cenário). O item continua público."""
    _item(db_session, 1001, "Mycobloom")

    sem_token = favoritos_client.post("/api/favorites/1001")
    token_invalido = favoritos_client.post("/api/favorites/1001", headers=cabecalho("adulterado"))

    assert (sem_token.status_code, token_invalido.status_code) == (401, 401)
    assert _favoritos(db_session) == set()
    publico = favoritos_client.get("/api/items/1001")
    assert publico.status_code == 200 and "favorito" not in publico.json()  # a rota pública não muda (CU03-C3)
    assert "favorito" not in favoritos_client.get("/api/items/1001", headers=cabecalho("adulterado")).json()


def test_cu06_c1_fa2_item_ja_favoritado(favoritos_client, db_session):
    """2.1 e 2.2: o registro existente é mantido, e o controle fica "Favoritado", sem nova mensagem."""
    _item(db_session, 1001, "Mycobloom")
    token = cadastrar_e_entrar(favoritos_client)
    favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))
    incluido_em = db_session.query(Favorito).one().data_inclusao

    resposta = favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))

    assert resposta.json() == {"item_id": 1001, "favorito": True, "message": None}
    assert db_session.query(Favorito).count() == 1
    db_session.expire_all()
    assert db_session.query(Favorito).one().data_inclusao == incluido_em


def test_cu06_c1_fe1_falha_no_banco(favoritos_client, db_session, mocker):
    """1.1 e 1.2: a gravação falha; 503 com a mensagem do cenário, sem o detalhe técnico, e nada é gravado."""
    _item(db_session, 1001, "Mycobloom")
    token = cadastrar_e_entrar(favoritos_client)
    mocker.patch.object(FavoritoRepository, "incluir", side_effect=erro_de_banco())

    resposta = favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_ATUALIZAR})
    assert sem_detalhe_tecnico(resposta)
    assert _favoritos(db_session) == set()


# ---------------------------------------------------------------------- C2: remover item dos favoritos


def test_cu06_c2_fluxo_principal_remove_favorito(favoritos_client, db_session):
    _item(db_session, 1001, "Mycobloom")
    token = cadastrar_e_entrar(favoritos_client)
    favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))

    resposta = favoritos_client.delete("/api/favorites/1001", headers=cabecalho(token))  # sem alertas: não pede confirmação

    assert (resposta.status_code, resposta.json()) == (200, {"item_id": 1001, "favorito": False, "message": REMOVIDO})
    assert _favoritos(db_session) == set()
    assert favoritos_client.get("/api/items/1001", headers=cabecalho(token)).json()["favorito"] is False  # "Favoritar"


def test_cu06_c2_fa1_remove_os_alertas_do_item(favoritos_client, db_session):
    """1.1 e 1.2: com alertas, o aviso do cenário (409) e nada é removido; 1.3 a 1.5: confirmada, saem os alertas do item
    e o favorito. Os alertas e o favorito de outro item ficam."""
    token = cadastrar_e_entrar(favoritos_client)
    usuario = _id_usuario(db_session)
    for item_id in (1001, 1002):
        favoritos_client.post(f"/api/favorites/{item_id}", headers=cabecalho(token))
    _alerta(db_session, usuario, 1001)
    _alerta(db_session, usuario, 1001, "DISPARADO")
    _alerta(db_session, usuario, 1002)

    aviso = favoritos_client.delete("/api/favorites/1001", headers=cabecalho(token))
    confirmada = favoritos_client.delete("/api/favorites/1001?confirmar=true", headers=cabecalho(token))

    assert (aviso.status_code, aviso.json()) == (409, {"detail": COM_ALERTAS})
    assert (confirmada.status_code, confirmada.json()["message"]) == (200, REMOVIDO)
    assert _favoritos(db_session) == {(usuario, 1002)}
    assert {(a.item_id, a.situacao) for a in db_session.query(AlertaPreco)} == {(1002, "ATIVO")}


def test_cu06_c2_fa2_remocao_cancelada(favoritos_client, db_session):
    """2.1 e 2.2: o usuário não confirma (a tela não reenvia com `confirmar`): o item e os alertas ficam."""
    token = cadastrar_e_entrar(favoritos_client)
    favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))
    _alerta(db_session, _id_usuario(db_session), 1001)

    resposta = favoritos_client.delete("/api/favorites/1001", headers=cabecalho(token))

    assert resposta.status_code == 409
    assert len(_favoritos(db_session)) == 1 and _alertas(db_session) == 1


def test_cu06_c2_fe1_falha_desfaz_remocoes(favoritos_client, db_session, mocker):
    """1.1 e 1.2: os alertas já tinham sido excluídos (passo 1.4) quando a remoção do favorito falhou: tudo é desfeito, e a
    resposta é a mensagem do cenário."""
    token = cadastrar_e_entrar(favoritos_client)
    favoritos_client.post("/api/favorites/1001", headers=cabecalho(token))
    _alerta(db_session, _id_usuario(db_session), 1001)

    def excluir_os_alertas_e_falhar(repositorio, id_usuario, item_id):
        repositorio.session.query(AlertaPreco).filter(AlertaPreco.item_id == item_id).delete()
        repositorio.session.flush()
        raise erro_de_banco()

    mocker.patch.object(FavoritoRepository, "remover", excluir_os_alertas_e_falhar)
    resposta = favoritos_client.delete("/api/favorites/1001?confirmar=true", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_ATUALIZAR})
    assert len(_favoritos(db_session)) == 1 and _alertas(db_session) == 1  # 1.2: as remoções foram desfeitas


# ---------------------------------------------------------------------- C3: visualizar lista de favoritos


def test_cu06_c3_fluxo_principal_lista_favoritos(favoritos_client, db_session, relogio):
    """Passos 2 a 4: em ordem alfabética, com o valor de mercado atual (RN06, o primeiro quartil do último ciclo), a variação
    em relação ao ponto do ciclo de 24 h antes (na tolerância de 2 h) e os alertas ativos. A Ficha do WoW usa a última
    coleta. Sem o ponto do dia anterior, a variação fica nula ("—")."""
    agora = relogio()
    ciclo = agora - timedelta(minutes=30)
    _mercado(db_session, 3209, ciclo)
    for item_id, nome in ((1001, "Mycobloom"), (1002, "algari Healing Potion"), (1003, "Bismuth"), (FICHA, "WoW Token")):
        _item(db_session, item_id, nome)
    for item_id, atual in ((1001, 17_950), (1002, 1_245_000), (1003, 13_200)):
        _leilao(db_session, 3209, item_id, atual, ciclo)
        _ponto(db_session, item_id, 3209, ciclo, atual)  # o ponto do ciclo atual: o item é deste mercado
    _ponto(db_session, 1001, 3209, ciclo - timedelta(hours=24) + timedelta(minutes=10), 17_400)  # +3,16%
    _ponto(db_session, 1003, 3209, ciclo - timedelta(hours=24), 13_524)  # −2,40%
    _ponto(db_session, 1002, 3209, ciclo - timedelta(hours=27), 1_000_000)  # 3 h fora: sem dia anterior
    db_session.add_all([ItemPrice(item_id=FICHA, price_copper=3_000_000_000, region="us", created_at=agora - timedelta(minutes=10)),
                        ItemPrice(item_id=FICHA, price_copper=2_900_000_000, region="us",
                                  created_at=agora - timedelta(hours=24, minutes=10))])
    db_session.commit()
    token = cadastrar_e_entrar(favoritos_client)
    for item_id in (1001, 1002, 1003, FICHA):
        favoritos_client.post(f"/api/favorites/{item_id}", headers=cabecalho(token))
    _alerta(db_session, _id_usuario(db_session), 1001)
    _alerta(db_session, _id_usuario(db_session), 1001, "DISPARADO")  # não conta como ativo
    outro = cadastrar_e_entrar(favoritos_client, email="outro@exemplo.com")
    favoritos_client.post("/api/favorites/1001", headers=cabecalho(outro))

    resposta = favoritos_client.get("/api/favorites", headers=cabecalho(token))

    assert resposta.status_code == 200
    lista = resposta.json()
    assert lista["mensagem"] is None
    assert [(i["name"], i["market_value"], i["variacao_pct"], i["alertas_ativos"]) for i in lista["itens"]] == [
        ("algari Healing Potion", 1_245_000, None, 0),
        ("Bismuth", 13_200, -2.4, 0),
        ("Mycobloom", 17_950, 3.2, 1),
        ("WoW Token", 3_000_000_000, 3.4, 0),
    ]
    assert lista["itens"][2]["icon_url"] == "https://icones/1001.jpg" and lista["itens"][2]["item_id"] == 1001
    assert {i["desatualizado"] for i in lista["itens"]} == {False}
    assert len(favoritos_client.get("/api/favorites", headers=cabecalho(outro)).json()["itens"]) == 1  # só os do usuário


def test_cu06_c3_fa1_lista_vazia(favoritos_client):
    token = cadastrar_e_entrar(favoritos_client)

    resposta = favoritos_client.get("/api/favorites", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (200, {"itens": [], "mensagem": VAZIA})


def test_cu06_c3_fa2_dados_desatualizados_rn09(favoritos_client, db_session, relogio):
    """2.1 e 2.2: o mercado do item falhou na última coleta (RN14) ou a coleta tem mais de 24 h (RN09): o item aparece
    normalmente, com o selo do cenário. A regra é a mesma do CU04 (frescor_do_item)."""
    agora = relogio()
    _mercado(db_session, 3209, agora - timedelta(minutes=30))
    _mercado(db_session, 32512, agora - timedelta(minutes=30), desatualizado=True)
    _mercado(db_session, 4444, agora - timedelta(hours=25))
    for item_id, reino in ((1001, 3209), (1002, 32512), (1003, 4444)):
        _item(db_session, item_id, f"Item {item_id}")
        _leilao(db_session, reino, item_id, 10_000, agora - timedelta(minutes=30) if reino != 4444 else agora - timedelta(hours=25))
        _ponto(db_session, item_id, reino, agora - timedelta(hours=1), 10_000)
    token = cadastrar_e_entrar(favoritos_client)
    for item_id in (1001, 1002, 1003):
        favoritos_client.post(f"/api/favorites/{item_id}", headers=cabecalho(token))

    itens = favoritos_client.get("/api/favorites", headers=cabecalho(token)).json()["itens"]

    assert [(i["item_id"], i["desatualizado"], i["aviso"]) for i in itens] == [
        (1001, False, None), (1002, True, DESATUALIZADOS), (1003, True, DESATUALIZADOS)]
    assert itens[1]["market_value"] == 10_000  # 2.2: o item é exibido normalmente


def test_cu06_c3_fe1_falha_no_banco(favoritos_client, mocker):
    token = cadastrar_e_entrar(favoritos_client)
    mocker.patch.object(FavoritoRepository, "do_usuario", side_effect=erro_de_banco())

    resposta = favoritos_client.get("/api/favorites", headers=cabecalho(token))

    assert (resposta.status_code, resposta.json()) == (503, {"detail": FE1_LISTA})
    assert sem_detalhe_tecnico(resposta)


# ---------------------------------------------------------------------- exclusão da conta (CU01-C3, RN20)


def test_cu06_exclusao_da_conta_remove_favoritos_e_alertas_rn20(favoritos_client, db_session):
    """RN20: a exclusão da conta (CU01-C3, sem mudança) remove os favoritos e os alertas do usuário, pela cascata das
    chaves; os de outro usuário ficam."""
    token = cadastrar_e_entrar(favoritos_client)
    outro = cadastrar_e_entrar(favoritos_client, email="outro@exemplo.com")
    for cliente_token in (token, outro):
        favoritos_client.post("/api/favorites/1001", headers=cabecalho(cliente_token))
    _alerta(db_session, _id_usuario(db_session), 1001)
    _alerta(db_session, _id_usuario(db_session, "outro@exemplo.com"), 1001)

    resposta = favoritos_client.request("DELETE", "/api/users/me", headers=cabecalho(token), json={"senha": SENHA})

    assert resposta.status_code == 204
    restantes = _favoritos(db_session)
    assert restantes == {(_id_usuario(db_session, "outro@exemplo.com"), 1001)}
    assert _alertas(db_session) == 1
