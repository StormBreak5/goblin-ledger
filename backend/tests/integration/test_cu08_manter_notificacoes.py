"""
Plano de testes do CU08 – Manter Notificações, um teste por fluxo do backend. Rodam contra um PostgreSQL temporário, com o
relógio falso (2026-09-28 12:00 UTC) e o envio de e-mail substituído (`EmailFalso`). O C1 roda dentro de um ciclo real do
CU09 (API da Blizzard falsa); o C3 também tem os testes de tela no frontend (`npm test`, arquivos `cu08-*`).
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from helpers_auth import EMAIL, SENHA, cabecalho, cadastrar_e_entrar, erro_de_banco, sem_detalhe_tecnico
from helpers_ingestao import MERCADO_REINO, leilao_de_reino
from src.models.favorito import AlertaPreco, Favorito
from src.models.mercado import CicloIngestao
from src.models.notificacao import Notificacao
from src.models.usuario import Usuario
from src.repositories.notificacao_repository import NotificacaoRepository
from src.scraper.models import HistoricalItemPrice
from src.services.ingestao_service import IngestaoService
from src.services.notificacao_service import NotificacaoService, ValorDoCiclo

UTC = timezone.utc
VAZIO = "Você não tem notificações"
FE1 = "Não foi possível carregar as notificações no momento. Tente novamente mais tarde"
MYCOBLOOM, BISMUTH, ORE = 1001, 1002, 1003
FICHA = 122284


@pytest.fixture
def ingestao_com_email(db_session, cliente_blizzard, relogio, email_falso):
    """IngestaoService (CU09) com a API da Blizzard, o relógio e o e-mail falsos: o ciclo aciona o CU08-C1 e o C2."""
    return IngestaoService(db_session, cliente_blizzard, relogio, email_falso)


@pytest.fixture(autouse=True)
def frontend(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://goblin.test")


def _usuario(db, email: str = EMAIL) -> int:
    usuario = Usuario(email=email, senha_hash="x", regiao="US")
    db.add(usuario)
    db.commit()
    return usuario.id_usuario


def _id_usuario(db, email: str = EMAIL) -> int:
    return db.query(Usuario).filter(Usuario.email == email).one().id_usuario


def _alerta(db, id_usuario: int, item_id: int, tipo: str, preco_alvo: int, canal: str = "AMBOS") -> int:
    """Um alerta ativo de um item favorito (o favorito é criado se ainda não existir)."""
    if db.get(Favorito, (id_usuario, item_id)) is None:
        db.add(Favorito(id_usuario=id_usuario, item_id=item_id, data_inclusao=datetime(2026, 9, 20, tzinfo=UTC)))
        db.flush()
    criado = datetime(2026, 9, 27, 12, tzinfo=UTC)
    alerta = AlertaPreco(id_usuario=id_usuario, item_id=item_id, tipo=tipo, preco_alvo=preco_alvo, canal=canal,
                         situacao="ATIVO", criado_em=criado, atualizado_em=criado)
    db.add(alerta)
    db.commit()
    return alerta.id_alerta


def _notificacao(db, id_usuario: int, item_id: int = MYCOBLOOM, canal: str = "AMBOS", disparada_em=None, lida=False,
                 tipo: str = "COMPRA", preco_alvo: int = 175_000, valor: int = 174_200) -> int:
    """Uma notificação gravada direto (como o C1 a deixa)."""
    quando = disparada_em or datetime(2026, 9, 28, 12, tzinfo=UTC)
    notificacao = Notificacao(id_usuario=id_usuario, item_id=item_id, tipo=tipo, preco_alvo=preco_alvo,
                              valor_mercado=valor, canal=canal, disparada_em=quando,
                              lida_em=quando if lida else None,
                              envio_email=None if canal == "WEB" else "PENDENTE", tentativas_email=0)
    db.add(notificacao)
    db.commit()
    return notificacao.id_notificacao


def _ciclo(cliente_blizzard, valores: dict[int, int], quantidades: dict[int, int] | None = None) -> None:
    """Um leilão por item, com o preço unitário de compra imediata (o valor de mercado do ciclo, RN06)."""
    quantidades = quantidades or {}
    cliente_blizzard.payload_do_reino = {"auctions": [
        leilao_de_reino(indice, item_id, valor * quantidades.get(item_id, 1), quantidade=quantidades.get(item_id, 1))
        for indice, (item_id, valor) in enumerate(valores.items(), start=1)
    ]}


def _do_banco(db, modelo, chave):
    db.expire_all()
    return db.get(modelo, chave)


def _notificacoes(db) -> list[Notificacao]:
    db.expire_all()
    return db.query(Notificacao).order_by(Notificacao.id_notificacao).all()


# ---------------------------------------------------------------------- C1: verificar alertas e disparar notificações


def test_cu08_c1_fluxo_principal_dispara_alerta_de_compra_e_de_venda_rn07(
    ingestao_com_email, cliente_blizzard, db_session, relogio, email_falso, add_item, caplog
):
    """Ativação e passo 1: o ciclo do CU09 concluído. Passos 2 a 4 (RN07): compra atingida com o valor abaixo do alvo,
    venda atingida com o valor igual ao alvo, um alerta não atingido continua ativo. Passos 5 e 6: a notificação com os
    dados do disparo e o alerta "Disparado". Passo 7: as de e-mail encaminhadas ao C2 (enviadas em seguida). Passo 8: log."""
    add_item(MYCOBLOOM, "Mycobloom")
    usuario = _usuario(db_session)
    compra = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000, "AMBOS")
    venda = _alerta(db_session, usuario, BISMUTH, "VENDA", 132_000, "WEB")
    venda_email = _alerta(db_session, usuario, MYCOBLOOM, "VENDA", 100_000, "EMAIL")
    nao_atingido = _alerta(db_session, usuario, ORE, "COMPRA", 50_000, "AMBOS")
    _ciclo(cliente_blizzard, {MYCOBLOOM: 174_200, BISMUTH: 132_000, ORE: 60_000})

    with caplog.at_level(logging.INFO):
        resultado = ingestao_com_email.executar(MERCADO_REINO)

    agora = relogio()
    assert resultado.status == "SUCESSO"
    for id_alerta in (compra, venda, venda_email):
        alerta = _do_banco(db_session, AlertaPreco, id_alerta)
        assert (alerta.situacao, alerta.disparado_em) == ("DISPARADO", agora)
    assert _do_banco(db_session, AlertaPreco, nao_atingido).situacao == "ATIVO"
    por_alerta = {n.id_alerta: n for n in _notificacoes(db_session)}
    assert set(por_alerta) == {compra, venda, venda_email}
    n = por_alerta[compra]
    assert (n.id_usuario, n.item_id, n.tipo, n.preco_alvo, n.valor_mercado, n.canal, n.disparada_em, n.lida_em) == (
        usuario, MYCOBLOOM, "COMPRA", 175_000, 174_200, "AMBOS", agora, None)
    assert (por_alerta[venda].tipo, por_alerta[venda].valor_mercado, por_alerta[venda].envio_email) == ("VENDA", 132_000, None)
    # Passo 7: as de e-mail foram encaminhadas ao C2, que rodou logo depois, na mesma rotina.
    assert {por_alerta[compra].envio_email, por_alerta[venda_email].envio_email} == {"ENVIADO"}
    assert [e["para"] for e in email_falso.alertas] == [EMAIL, EMAIL]
    assert ("CU08-C1: verificação de auctions:us:3209 concluída: 3 itens verificados, 0 ignorados por anomalia de volume "
            "(RN12), 3 alertas atingidos, 2 notificações encaminhadas para e-mail.") in caplog.text


def test_cu08_c1_fa1_nenhum_alerta_atingido(db_session, relogio, email_falso, caplog):
    """FA1: nenhum alerta atingido; nada é registrado e o log da conclusão (passo 8) é gravado."""
    usuario = _usuario(db_session)
    compra = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000)
    venda = _alerta(db_session, usuario, MYCOBLOOM, "VENDA", 250_000)

    with caplog.at_level(logging.INFO):
        resultado = NotificacaoService(db_session, relogio, email_falso).verificar_alertas(
            [ValorDoCiclo(MYCOBLOOM, 200_000)], "auctions:us:3209")

    assert (resultado.alertas_atingidos, resultado.falhou) == (0, False)
    assert {_do_banco(db_session, AlertaPreco, a).situacao for a in (compra, venda)} == {"ATIVO"}
    assert _notificacoes(db_session) == []
    assert "CU08-C1-FA1: verificação de auctions:us:3209 concluída: 1 itens verificados" in caplog.text


def test_cu08_c1_fa2_item_com_volume_anomalo_rn12(ingestao_com_email, cliente_blizzard, db_session, relogio):
    """FA2 (RN12): o ponto do item no ciclo foi marcado como anomalia de volume; os alertas dele não são verificados nesse
    ciclo (continuam ativos mesmo com o preço além do alvo), e os dos demais itens são."""
    sem_fuso = relogio().replace(tzinfo=None)
    for horas in range(1, 31):  # 30 pontos de 10 unidades: base suficiente (mínimo de 24) para julgar o volume
        db_session.add(HistoricalItemPrice(item_id=MYCOBLOOM, region="3209", timestamp=sem_fuso - timedelta(hours=horas),
                                           price=180_000, quantity=10, origem="BLIZZARD"))
    db_session.commit()
    usuario = _usuario(db_session)
    anomalo = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000)
    normal = _alerta(db_session, usuario, ORE, "COMPRA", 50_000, "WEB")
    _ciclo(cliente_blizzard, {MYCOBLOOM: 100_000, ORE: 40_000}, quantidades={MYCOBLOOM: 5000})  # 500x a mediana

    resultado = ingestao_com_email.executar(MERCADO_REINO)

    assert resultado.itens_anomalos == 1
    assert _do_banco(db_session, AlertaPreco, anomalo).situacao == "ATIVO"
    assert _do_banco(db_session, AlertaPreco, normal).situacao == "DISPARADO"
    assert [n.id_alerta for n in _notificacoes(db_session)] == [normal]


def test_cu08_c1_fe1_falha_desfaz_a_verificacao(ingestao_com_email, cliente_blizzard, db_session, relogio, mocker, caplog):
    """FE1: o banco cai no passo 5, depois de o primeiro alerta já ter passado a "Disparado" na transação: a verificação
    inteira é desfeita e vai para o log; o ciclo do CU09 continua concluído; no próximo ciclo, o alerta dispara."""
    usuario = _usuario(db_session)
    compra = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000)
    venda = _alerta(db_session, usuario, BISMUTH, "VENDA", 130_000)
    _ciclo(cliente_blizzard, {MYCOBLOOM: 174_200, BISMUTH: 132_000})
    mocker.patch.object(NotificacaoRepository, "registrar", side_effect=erro_de_banco())

    resultado = ingestao_com_email.executar(MERCADO_REINO)

    mocker.stopall()
    assert resultado.status == "SUCESSO"  # a falha do CU08 não muda o resultado do ciclo
    assert db_session.query(CicloIngestao).filter(CicloIngestao.status == "SUCESSO").count() == 1
    assert {_do_banco(db_session, AlertaPreco, a).situacao for a in (compra, venda)} == {"ATIVO"}
    assert _notificacoes(db_session) == []
    assert "CU08-C1-FE1" in caplog.text

    relogio.avancar(minutes=61)  # FE1 passo 1.3: repete no próximo ciclo (RN05: 60 min depois)
    assert ingestao_com_email.executar(MERCADO_REINO).status == "SUCESSO"

    assert {n.id_alerta for n in _notificacoes(db_session)} == {compra, venda}


def test_cu08_c1_ficha_do_wow_dispara_alerta_sem_rn12(db_session, relogio, email_falso):
    """Decisão da Ficha do WoW: a cotação vem da coleta de 15 minutos do worker, fora do ciclo do CU09; a cada preço novo,
    a mesma verificação (RN07) e o mesmo envio, sem a RN12 (a Ficha não tem volume)."""
    usuario = _usuario(db_session)
    compra = _alerta(db_session, usuario, FICHA, "COMPRA", 2_600_000, "WEB")
    venda = _alerta(db_session, usuario, FICHA, "VENDA", 3_000_000, "WEB")

    NotificacaoService(db_session, relogio, email_falso).processar_coleta_da_ficha(2_500_000)

    assert _do_banco(db_session, AlertaPreco, compra).situacao == "DISPARADO"
    assert _do_banco(db_session, AlertaPreco, venda).situacao == "ATIVO"
    [notificacao] = _notificacoes(db_session)
    assert (notificacao.id_alerta, notificacao.item_id, notificacao.valor_mercado) == (compra, FICHA, 2_500_000)


# ---------------------------------------------------------------------- C2: enviar notificação por e-mail


def test_cu08_c2_fluxo_principal_envia_email_rn18(db_session, relogio, email_falso, add_item):
    """Passo 1: as notificações de e-mail ainda não enviadas, inclusive a de um ciclo anterior. Passo 2: a mensagem com o
    item, o tipo, o preço-alvo e o valor de mercado em Ouro, Prata e Cobre (RN01), a data e a hora (Brasília) e o link.
    Passo 3: ao e-mail cadastrado (RN18). Passo 4: a data e a hora do envio. A de canal só tela não é enviada."""
    add_item(MYCOBLOOM, "Mycobloom")
    usuario = _usuario(db_session)
    anterior = _notificacao(db_session, usuario, BISMUTH, "EMAIL", datetime(2026, 9, 28, 9, tzinfo=UTC), tipo="VENDA",
                            preco_alvo=130_000, valor=132_000)
    atual = _notificacao(db_session, usuario, MYCOBLOOM, "AMBOS")
    so_tela = _notificacao(db_session, usuario, MYCOBLOOM, "WEB")

    resultado = NotificacaoService(db_session, relogio, email_falso).enviar_pendentes()

    assert (resultado.enviados, resultado.falhou) == (2, False)
    assert [e["para"] for e in email_falso.alertas] == [EMAIL, EMAIL]
    email = email_falso.alertas[1]
    assert email["assunto"] == "Alerta de preço atingido – Mycobloom"
    for trecho in ("Seu alerta de preço foi atingido",
                   "O valor de mercado do item Mycobloom atingiu o preço do seu alerta de compra.",
                   "Tipo do alerta: Compra (preço cair até o alvo)", "Preço-alvo: 17g 50s", "Valor de mercado: 17g 42s",
                   "Data e hora: 28/09/2026 às 09:00",  # 12:00 UTC no horário de Brasília
                   "Ver o item no Goblin Ledger: http://goblin.test/item/1001",
                   'reative-o na seção "Alertas de preço" da tela do item.',
                   "Você recebeu este e-mail porque configurou um alerta de preço no Goblin Ledger com notificação por e-mail."):
        assert trecho in email["texto"]
    assert 'href="http://goblin.test/item/1001"' in email["html"] and "17g 42s" in email["html"]
    assert "Item 1002" in email_falso.alertas[0]["assunto"]  # item sem cadastro: o nome provisório
    for id_notificacao in (anterior, atual):
        n = _do_banco(db_session, Notificacao, id_notificacao)
        assert (n.envio_email, n.enviada_em, n.tentativas_email) == ("ENVIADO", relogio(), 1)
    assert _do_banco(db_session, Notificacao, so_tela).envio_email is None


def test_cu08_c2_fa1_falha_no_envio_tenta_ate_3_vezes(db_session, relogio, email_falso, caplog):
    """FA1: o servidor não aceita a mensagem; a notificação continua pendente e é tentada de novo no próximo ciclo. Na
    terceira falha, o envio é marcado como "Falhou" e vai para o log; não há quarta tentativa. A falha de um e-mail não
    impede os outros."""
    falha = _notificacao(db_session, _usuario(db_session, "falha@exemplo.com"))
    outro = _notificacao(db_session, _usuario(db_session))
    email_falso.falhar_para = {"falha@exemplo.com"}
    servico = NotificacaoService(db_session, relogio, email_falso)

    servico.enviar_pendentes()
    assert _do_banco(db_session, Notificacao, outro).envio_email == "ENVIADO"  # o outro não foi impedido
    n = _do_banco(db_session, Notificacao, falha)
    assert (n.envio_email, n.tentativas_email, n.enviada_em) == ("PENDENTE", 1, None)

    servico.enviar_pendentes()
    assert (_do_banco(db_session, Notificacao, falha).envio_email,
            _do_banco(db_session, Notificacao, falha).tentativas_email) == ("PENDENTE", 2)

    servico.enviar_pendentes()
    n = _do_banco(db_session, Notificacao, falha)
    assert (n.envio_email, n.tentativas_email) == ("FALHOU", 3)
    assert 'CU08-C2-FA1: o e-mail da notificação' in caplog.text and 'marcado como "Falhou"' in caplog.text

    email_falso.falhar_para = set()
    servico.enviar_pendentes()  # não é tentada de novo
    assert (_do_banco(db_session, Notificacao, falha).envio_email,
            _do_banco(db_session, Notificacao, falha).tentativas_email) == ("FALHOU", 3)
    assert [e["para"] for e in email_falso.alertas] == [EMAIL]


def test_cu08_c2_fe1_falha_no_banco(db_session, relogio, email_falso, mocker, caplog):
    """FE1: a falha de banco no passo 1 ou no passo 4 vai para o log, sem interromper quem chamou; a notificação continua
    pendente e é processada na próxima execução."""
    id_notificacao = _notificacao(db_session, _usuario(db_session))
    servico = NotificacaoService(db_session, relogio, email_falso)

    # Passo 1: não consegue recuperar as pendentes.
    mocker.patch.object(NotificacaoRepository, "pendentes_de_envio", side_effect=erro_de_banco())
    assert servico.enviar_pendentes().falhou is True
    mocker.stopall()
    assert email_falso.alertas == []
    assert _do_banco(db_session, Notificacao, id_notificacao).envio_email == "PENDENTE"

    # Passo 4: o e-mail sai, mas a gravação do envio falha (o primeiro commit encerra a leitura do passo 1).
    commit_original = db_session.commit
    commits: list[int] = []

    def commit_que_falha_no_passo_4() -> None:
        commits.append(1)
        if len(commits) == 2:
            raise erro_de_banco()
        commit_original()

    mocker.patch.object(db_session, "commit", side_effect=commit_que_falha_no_passo_4)
    assert servico.enviar_pendentes().falhou is True
    mocker.stopall()
    n = _do_banco(db_session, Notificacao, id_notificacao)
    assert (n.envio_email, n.tentativas_email, n.enviada_em) == ("PENDENTE", 0, None)
    assert caplog.text.count("CU08-C2-FE1") == 2

    assert servico.enviar_pendentes().enviados == 1  # a próxima execução processa a pendente
    assert _do_banco(db_session, Notificacao, id_notificacao).envio_email == "ENVIADO"


# ---------------------------------------------------------------------- C3: consultar notificações


def test_cu08_c3_fluxo_principal_lista_e_marca_como_lidas(notificacoes_client, db_session, relogio, add_item):
    """Passo 1: o contador de não lidas (só as do canal tela). Passos 3 e 4: as notificações do canal tela, da mais
    recente para a mais antiga, com o item, o tipo, o preço-alvo, o valor de mercado, a data e a hora e as não lidas.
    Passo 5: as exibidas ficam lidas e o contador zera. A consulta da lista não marca nada por conta própria."""
    add_item(MYCOBLOOM, "Mycobloom", "https://icone.exemplo/mycobloom.jpg")
    add_item(BISMUTH, "Bismuth")
    token = cadastrar_e_entrar(notificacoes_client)
    usuario = _id_usuario(db_session)
    antiga = _notificacao(db_session, usuario, BISMUTH, "WEB", datetime(2026, 9, 26, 10, tzinfo=UTC), lida=True,
                          tipo="VENDA", preco_alvo=130_000, valor=132_000)
    recente = _notificacao(db_session, usuario, MYCOBLOOM, "AMBOS", datetime(2026, 9, 28, 11, tzinfo=UTC))
    meio = _notificacao(db_session, usuario, BISMUTH, "WEB", datetime(2026, 9, 27, 18, tzinfo=UTC))
    _notificacao(db_session, usuario, MYCOBLOOM, "EMAIL", datetime(2026, 9, 28, 11, 30, tzinfo=UTC))  # só e-mail
    autenticado = cabecalho(token)

    assert notificacoes_client.get("/api/notifications/unread-count", headers=autenticado).json() == {"nao_lidas": 2}
    resposta = notificacoes_client.get("/api/notifications", headers=autenticado)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [n["id_notificacao"] for n in corpo["notificacoes"]] == [recente, meio, antiga]
    assert (corpo["nao_lidas"], corpo["mensagem"]) == (2, None)
    assert corpo["notificacoes"][0] == {
        "id_notificacao": recente, "item_id": MYCOBLOOM, "name": "Mycobloom",
        "icon_url": "https://icone.exemplo/mycobloom.jpg", "tipo": "COMPRA", "preco_alvo": 175_000,
        "valor_mercado": 174_200, "disparada_em": "2026-09-28T11:00:00Z", "lida": False,
    }
    assert [n["lida"] for n in corpo["notificacoes"]] == [False, False, True]
    assert notificacoes_client.get("/api/notifications/unread-count", headers=autenticado).json() == {"nao_lidas": 2}

    marcadas = notificacoes_client.post("/api/notifications/read", headers=autenticado,
                                        json={"ids": [n["id_notificacao"] for n in corpo["notificacoes"]]})

    assert (marcadas.status_code, marcadas.json()) == (200, {"nao_lidas": 0})
    assert _do_banco(db_session, Notificacao, recente).lida_em == relogio()
    assert _do_banco(db_session, Notificacao, antiga).lida_em == datetime(2026, 9, 26, 10, tzinfo=UTC)  # já estava lida
    assert notificacoes_client.get("/api/notifications/unread-count", headers=autenticado).json() == {"nao_lidas": 0}


def test_cu08_c3_fa1_nenhuma_notificacao(notificacoes_client, db_session):
    """FA1: o usuário não tem notificações (as só de e-mail não aparecem no sino): a mensagem do cenário."""
    token = cadastrar_e_entrar(notificacoes_client)
    _notificacao(db_session, _id_usuario(db_session), canal="EMAIL")

    resposta = notificacoes_client.get("/api/notifications", headers=cabecalho(token))

    assert resposta.status_code == 200
    assert resposta.json() == {"notificacoes": [], "nao_lidas": 0, "mensagem": VAZIO}


def test_cu08_c3_fe1_falha_no_banco(notificacoes_client, db_session, mocker):
    """FE1: a falha de banco no passo 3 (consultar) ou no passo 5 (marcar como lidas) devolve a mensagem do cenário, sem
    detalhe técnico, e nada é marcado."""
    token = cadastrar_e_entrar(notificacoes_client)
    id_notificacao = _notificacao(db_session, _id_usuario(db_session), canal="WEB")

    mocker.patch.object(NotificacaoRepository, "da_tela", side_effect=erro_de_banco())
    lista = notificacoes_client.get("/api/notifications", headers=cabecalho(token))
    mocker.patch.object(NotificacaoRepository, "marcar_lidas", side_effect=erro_de_banco())
    marcacao = notificacoes_client.post("/api/notifications/read", headers=cabecalho(token), json={"ids": [id_notificacao]})

    for resposta in (lista, marcacao):
        assert (resposta.status_code, resposta.json()["detail"]) == (503, FE1)
        assert sem_detalhe_tecnico(resposta)
    mocker.stopall()
    assert _do_banco(db_session, Notificacao, id_notificacao).lida_em is None


# ---------------------------------------------------------------------- regras gerais


def test_rn07_alerta_dispara_uma_unica_vez(ingestao_com_email, cliente_blizzard, db_session, pg_engine, relogio,
                                           email_falso):
    """RN07: depois de disparado, o alerta fica "Disparado" e não gera outra notificação no ciclo seguinte, com o preço
    ainda além do alvo. Dois ciclos simultâneos também não: a troca de "Ativo" para "Disparado" é condicional; a sessão B
    fica bloqueada na linha do alerta até o commit da A e, depois, não o altera."""
    usuario = _usuario(db_session)
    compra = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000, "WEB")
    _ciclo(cliente_blizzard, {MYCOBLOOM: 174_200})
    ingestao_com_email.executar(MERCADO_REINO)
    relogio.avancar(minutes=61)
    _ciclo(cliente_blizzard, {MYCOBLOOM: 170_000})
    ingestao_com_email.executar(MERCADO_REINO)
    assert [n.id_alerta for n in _notificacoes(db_session)] == [compra]

    # Ciclos simultâneos: um alerta novo, verificado ao mesmo tempo por duas sessões.
    venda = _alerta(db_session, usuario, BISMUTH, "VENDA", 130_000, "WEB")
    nova_sessao = sessionmaker(bind=pg_engine)
    sessao_a, sessao_b = nova_sessao(), nova_sessao()
    resultado: dict[str, int] = {}

    def ciclo_b() -> None:
        resultado["b"] = NotificacaoService(sessao_b, relogio, email_falso).verificar_alertas(
            [ValorDoCiclo(BISMUTH, 132_000)], "commodities:us").alertas_atingidos

    try:
        repositorio_a = NotificacaoRepository(sessao_a)
        alerta_a = sessao_a.get(AlertaPreco, venda)
        assert repositorio_a.disparar(alerta_a, relogio()) == "WEB"
        b = threading.Thread(target=ciclo_b)
        b.start()
        time.sleep(0.5)
        assert b.is_alive()  # B espera a linha do alerta, travada pela A
        repositorio_a.registrar(Notificacao(id_alerta=venda, id_usuario=usuario, item_id=BISMUTH, tipo="VENDA",
                                            preco_alvo=130_000, valor_mercado=132_000, canal="WEB",
                                            disparada_em=relogio(), tentativas_email=0))
        sessao_a.commit()
        b.join(timeout=10)
    finally:
        sessao_a.close()
        sessao_b.close()

    assert resultado["b"] == 0
    assert [n.id_alerta for n in _notificacoes(db_session)] == [compra, venda]


def test_cu08_exclusao_da_conta_remove_notificacoes_rn20(notificacoes_client, db_session):
    """RN20: a exclusão da conta (CU01-C3, sem mudança) remove as notificações do usuário, pela cascata da chave; as de
    outro usuário ficam."""
    token = cadastrar_e_entrar(notificacoes_client)
    cadastrar_e_entrar(notificacoes_client, email="outro@exemplo.com")
    _notificacao(db_session, _id_usuario(db_session))
    _notificacao(db_session, _id_usuario(db_session), canal="WEB")
    outro = _notificacao(db_session, _id_usuario(db_session, "outro@exemplo.com"))

    resposta = notificacoes_client.request("DELETE", "/api/users/me", headers=cabecalho(token), json={"senha": SENHA})

    assert resposta.status_code == 204
    assert [n.id_notificacao for n in _notificacoes(db_session)] == [outro]


def test_cu08_notificacao_permanece_quando_o_alerta_e_excluido(notificacoes_client, db_session, relogio, email_falso):
    """A notificação guarda os dados do disparo e continua no histórico quando o alerta é excluído (CU07-C3) ou o favorito
    é removido com os alertas (CU06-C2-FA1): o vínculo com o alerta fica nulo."""
    token = cadastrar_e_entrar(notificacoes_client)
    usuario = _id_usuario(db_session)
    compra = _alerta(db_session, usuario, MYCOBLOOM, "COMPRA", 175_000, "WEB")
    venda = _alerta(db_session, usuario, BISMUTH, "VENDA", 130_000, "WEB")
    NotificacaoService(db_session, relogio, email_falso).verificar_alertas(
        [ValorDoCiclo(MYCOBLOOM, 174_200), ValorDoCiclo(BISMUTH, 132_000)], "auctions:us:3209")

    assert notificacoes_client.delete(f"/api/alerts/{compra}", headers=cabecalho(token)).status_code == 200
    removido = notificacoes_client.delete(f"/api/favorites/{BISMUTH}?confirmar=true", headers=cabecalho(token))
    assert removido.status_code == 200

    restantes = _notificacoes(db_session)
    assert [(n.id_alerta, n.item_id, n.valor_mercado) for n in restantes] == [(None, MYCOBLOOM, 174_200),
                                                                              (None, BISMUTH, 132_000)]
    lista = notificacoes_client.get("/api/notifications", headers=cabecalho(token)).json()
    assert len(lista["notificacoes"]) == 2


def test_cu08_c3_so_as_notificacoes_do_proprio_usuario(notificacoes_client, db_session):
    """Pré-condição do C3: usuário autenticado (sem sessão, 401). Cada usuário vê e marca só as próprias notificações."""
    token = cadastrar_e_entrar(notificacoes_client)
    outro_token = cadastrar_e_entrar(notificacoes_client, email="outro@exemplo.com")
    minha = _notificacao(db_session, _id_usuario(db_session), canal="WEB")

    for metodo, caminho in (("GET", "/api/notifications/unread-count"), ("GET", "/api/notifications"),
                            ("POST", "/api/notifications/read")):
        assert notificacoes_client.request(metodo, caminho, json={"ids": [minha]}).status_code == 401

    do_outro = notificacoes_client.get("/api/notifications", headers=cabecalho(outro_token)).json()
    marcadas = notificacoes_client.post("/api/notifications/read", headers=cabecalho(outro_token), json={"ids": [minha]})

    assert do_outro["notificacoes"] == [] and marcadas.json() == {"nao_lidas": 0}
    assert _do_banco(db_session, Notificacao, minha).lida_em is None
    assert notificacoes_client.get("/api/notifications/unread-count", headers=cabecalho(token)).json() == {"nao_lidas": 1}
