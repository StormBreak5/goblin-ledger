"""
Plano de testes do CU10 – Cadastrar Dados Passados, Cenário 02 (registrar eventos de atualização do jogo), um teste
por fluxo, mais uma prova por fonte de eventos. Rodam contra um PostgreSQL temporário; as páginas de referência (trechos
reais da Wikipedia e da Warcraft Wiki) e a API da Blizzard são falsas: nenhum teste acessa a internet.
"""
from datetime import date

import pytest
from helpers_auth import cabecalho, cadastrar_e_entrar
from helpers_eventos import URL_EXPANSOES, URL_FERIADOS, URL_PATCHES, fixture
from sqlalchemy.exc import OperationalError

from src.models.evento import EventoJogo, ExtracaoEvento
from src.models.usuario import Usuario
from src.services.api_client import ApiIndisponivelError
from src.services.eventos.base import FonteDeEventosIndisponivelError

FE1 = "Não foi possível extrair os eventos da página informada. Verifique a fonte ou cadastre o evento manualmente"
FA2_INVALIDO = "Verifique os campos destacados"

PAGINA_SEM_A_TABELA = "<html><body><div class='novo-layout'><p>Patch 12.0.0 lançado em 20/01/2026</p></div></body></html>"


def _token_de_admin(cliente, db_session) -> str:
    token = cadastrar_e_entrar(cliente)
    db_session.query(Usuario).update({"role": "admin"})  # o papel é lido a cada requisição
    db_session.commit()
    return token


def _extrair(cliente, token, fonte, **corpo):
    return cliente.post("/api/admin/events/extract", json={"fonte": fonte, **corpo}, headers=cabecalho(token))


def _cadastrar(cliente, token, **corpo):
    dados = {"nome": "Patch 11.1.0", "versao": "11.1.0", "tipo": "PATCH", "data_inicio": "25/02/2025", **corpo}
    return cliente.post("/api/admin/events", json=dados, headers=cabecalho(token))


def _do_banco(db_session, **filtro) -> list[EventoJogo]:
    return db_session.query(EventoJogo).filter_by(**filtro).order_by(EventoJogo.data_inicio, EventoJogo.nome).all()


# ---------------------------------------------------------------------- fluxo principal, uma fonte por teste


def test_cu10_c2_fluxo_principal_extrai_e_registra_patches(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "PATCHES")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert (corpo["eventos_encontrados"], corpo["eventos_registrados"], corpo["eventos_ignorados"]) == (8, 8, 0)
    # Passo 6: a relação de eventos registrados, com a data no formato padrão DD/MM/AAAA (passo 3).
    por_versao = {evento["versao"]: evento for evento in corpo["eventos"]}
    assert por_versao["12.1.0"]["nome"] == "Patch 12.1.0" and por_versao["12.1.0"]["data_inicio"] == "11/08/2026"
    assert por_versao["12.0.0"]["nome"] == "Patch 12.0.0 (pre-patch)"  # o pré-patch é reconhecido pela descrição
    assert por_versao["1.12.1"]["data_inicio"] == "26/09/2006"
    # Passo 5: registrados como patch, com a origem e a página de onde vieram.
    gravado = _do_banco(db_session, tipo="PATCH")
    assert len(gravado) == 8 and {e.origem for e in gravado} == {"WARCRAFT_WIKI"} and {e.regiao for e in gravado} == {"GLOBAL"}
    assert {e.fonte for e in gravado} == {URL_PATCHES}
    assert isinstance(gravado[0].data_inicio, date) and gravado[0].data_inicio == date(2006, 9, 26)  # gravada como data
    assert paginas.chamadas == [URL_PATCHES]  # uma requisição à wiki
    log = db_session.query(ExtracaoEvento).one()
    assert (log.fonte, log.status, log.eventos_registrados) == ("PATCHES", "SUCESSO", 8)


def test_cu10_c2_fluxo_principal_extrai_as_expansoes_da_wikipedia(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    corpo = _extrair(admin_client, token, "EXPANSOES").json()

    expansoes = {(evento["nome"], evento["regiao"]): evento["data_inicio"] for evento in corpo["eventos"]}
    assert len(expansoes) == 13  # as 11 expansões e o lançamento do jogo original nas Américas e na Europa
    assert expansoes[("Battle for Azeroth", "GLOBAL")] == "13/08/2018"  # a Wikipedia, e não a memória de quem programou
    assert expansoes[("Midnight", "GLOBAL")] == "02/03/2026"
    assert expansoes[("The Burning Crusade", "GLOBAL")] == "16/01/2007"
    assert expansoes[("World of Warcraft", "US")] == "23/11/2004"
    assert expansoes[("World of Warcraft", "EU")] == "11/02/2005"
    assert {e.tipo for e in _do_banco(db_session)} == {"EXPANSAO"}
    assert {e.origem for e in _do_banco(db_session)} == {"WIKIPEDIA"}


def test_cu10_c2_fluxo_principal_extrai_as_temporadas_da_api_da_blizzard(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    corpo = _extrair(admin_client, token, "TEMPORADAS").json()

    assert paginas.chamadas == []  # a fonte é a API oficial, e não uma página
    nomes = {evento["nome"]: evento for evento in corpo["eventos"]}
    assert len(nomes) == 7  # a temporada de PvP que a API recusou (403) fica de fora
    assert nomes["Mythic+ Dungeons (Midnight Season 1)"]["data_inicio"] == "17/03/2026"
    assert nomes["Mythic+ Dungeons (Midnight Season 1)"]["data_fim"] == "11/08/2026"  # a API traz o fim das encerradas
    assert nomes["Mythic+ Dungeons (Midnight Season 2)"]["data_inicio"] == "11/08/2026"
    assert nomes["Mythic+ Dungeons (Midnight Season 2)"]["data_fim"] is None  # a temporada em curso não tem fim
    assert nomes["Mythic+ Season 1"]["data_inicio"] == "29/08/2018"  # as antigas não têm nome na API
    assert nomes["PvP Season 40"]["data_inicio"] == "12/08/2025" and nomes["PvP Season 40"]["data_fim"] == "20/01/2026"
    assert nomes["Player vs. Player (Midnight Season 2)"]["data_inicio"] == "18/08/2026"
    assert {e.tipo for e in _do_banco(db_session)} == {"TEMPORADA"}
    assert {e.origem for e in _do_banco(db_session)} == {"API_BLIZZARD"}


def test_cu10_c2_fluxo_principal_extrai_os_eventos_sazonais(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "SAZONAIS")

    assert resposta.status_code == 200
    eventos = {(e.nome, e.data_inicio): e for e in _do_banco(db_session)}
    inverno = eventos[("Feast of Winter Veil", date(2022, 12, 15))]
    assert inverno.data_fim == date(2023, 1, 2)  # o período atravessa a virada do ano
    assert eventos[("Pirates' Day", date(2024, 9, 19))].data_fim is None  # um dia só
    assert eventos[("Peon Day", date(2024, 9, 30))].regiao == "EU"  # a página diz "observed only in Europe"
    assert ("Love is in the Air", date(2027, 2, 7)) in eventos  # de 2022 até o ano que vem (a data do relógio é 2026)
    assert ("Love is in the Air", date(2028, 2, 7)) not in eventos
    # Lunar Festival e Noblegarden "variam": a página não tem datas, então vêm por regra e são marcados como aproximados.
    assert eventos[("Noblegarden (aproximado)", date(2024, 3, 31))].data_fim == date(2024, 4, 7)  # domingo de Páscoa
    assert eventos[("Lunar Festival (aproximado)", date(2024, 2, 10))].origem == "REGRA"
    assert {e.tipo for e in eventos.values()} == {"EVENTO_SAZONAL"}


def test_cu10_c2_fluxo_principal_gera_os_eventos_recorrentes_por_regra(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "RECORRENTES")

    assert resposta.status_code == 200 and paginas.chamadas == []  # regras de calendário: nenhuma página é lida
    reinicios_us = _do_banco(db_session, nome="Weekly reset", regiao="US")
    reinicios_eu = _do_banco(db_session, nome="Weekly reset", regiao="EU")
    assert {e.data_inicio.weekday() for e in reinicios_us} == {1}  # toda terça-feira (7:00 PDT, informado pelo autor)
    assert {e.data_inicio.weekday() for e in reinicios_eu} == {2}  # a Europa é a sugestão: quarta-feira
    assert reinicios_us[0].data_inicio == date(2022, 1, 4) and reinicios_us[-1].data_inicio == date(2027, 12, 28)
    assert len(reinicios_us) == 313  # uma linha por semana, de 2022 até o ano que vem
    feira = {e.data_inicio: e for e in _do_banco(db_session, nome="Darkmoon Faire")}
    assert feira[date(2024, 9, 1)].data_fim == date(2024, 9, 7)  # o mês começou no domingo: abre nesse mesmo dia
    assert feira[date(2026, 10, 4)].data_fim == date(2026, 10, 10)  # o primeiro domingo, e dura uma semana
    assert len(feira) == 72
    posto = {e.data_inicio: e for e in _do_banco(db_session, nome="Trading Post monthly rotation")}
    assert posto[date(2024, 2, 1)].data_fim == date(2024, 2, 29)  # o estoque gira no dia 1º e vale o mês
    assert {e.tipo for e in _do_banco(db_session)} == {"RECORRENTE"}


def test_cu10_c2_o_reinicio_semanal_da_europa_pode_ser_desligado(admin_client, paginas, db_session, monkeypatch):
    monkeypatch.setenv("EVENTOS_REINICIO_SEMANAL_EU", "off")
    token = _token_de_admin(admin_client, db_session)

    _extrair(admin_client, token, "RECORRENTES")

    assert _do_banco(db_session, nome="Weekly reset", regiao="EU") == []
    assert len(_do_banco(db_session, nome="Weekly reset", regiao="US")) == 313


# ---------------------------------------------------------------------- FA1: evento já registrado


def test_cu10_c2_fa1_evento_ja_registrado_e_ignorado_e_os_demais_seguem(admin_client, paginas, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    completa = paginas.paginas[URL_PATCHES]
    paginas.paginas[URL_PATCHES] = completa.split("<h2>Vanilla</h2>")[0] + "</body></html>"  # só a tabela do Midnight
    primeira = _extrair(admin_client, token, "PATCHES").json()
    assert (primeira["eventos_registrados"], primeira["eventos_ignorados"]) == (5, 0)

    paginas.paginas[URL_PATCHES] = completa  # a página ganhou as tabelas antigas
    relogio.avancar(minutes=11)
    segunda = _extrair(admin_client, token, "PATCHES").json()

    assert (segunda["eventos_encontrados"], segunda["eventos_registrados"], segunda["eventos_ignorados"]) == (8, 3, 5)
    assert sorted(e["versao"] for e in segunda["eventos"]) == ["1.12.1", "1.12.2", "1.12.3"]  # só os novos
    assert len(_do_banco(db_session, tipo="PATCH")) == 8  # nada foi duplicado

    relogio.avancar(minutes=11)
    repetida = _extrair(admin_client, token, "PATCHES").json()
    assert (repetida["eventos_registrados"], repetida["eventos_ignorados"]) == (0, 8)
    assert repetida["eventos"] == []


def test_cu10_c2_fa1_repetir_a_extracao_nao_duplica_os_eventos_gerados_por_regra(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)
    assert _extrair(admin_client, token, "RECORRENTES").json()["eventos_registrados"] > 0

    outra_vez = _extrair(admin_client, token, "RECORRENTES").json()  # regras não têm página: sem intervalo mínimo

    assert (outra_vez["eventos_registrados"], outra_vez["eventos_ignorados"]) == (0, outra_vez["eventos_encontrados"])


# ---------------------------------------------------------------------- FA2: cadastro manual


def test_cu10_c2_fa2_cadastro_manual_do_evento(admin_client, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _cadastrar(admin_client, token, nome="  Patch 11.1.0 ", data_fim="04/03/2025", regiao="us")

    assert resposta.status_code == 200
    [evento] = resposta.json()["eventos"]
    assert (evento["nome"], evento["versao"], evento["tipo"], evento["regiao"]) == ("Patch 11.1.0", "11.1.0", "PATCH", "US")
    assert (evento["data_inicio"], evento["data_fim"], evento["origem"]) == ("25/02/2025", "04/03/2025", "MANUAL")
    [gravado] = _do_banco(db_session)
    assert gravado.data_inicio == date(2025, 2, 25) and gravado.data_fim == date(2025, 3, 4)

    repetido = _cadastrar(admin_client, token, nome="Patch 11.1.0", regiao="US").json()  # o passo 4 vale também aqui
    assert (repetido["eventos_registrados"], repetido["eventos_ignorados"]) == (0, 1)
    assert len(_do_banco(db_session)) == 1


@pytest.mark.parametrize(
    "corpo, campos",
    [
        ({"data_inicio": "31/02/2026"}, ["data_inicio"]),  # a data não existe
        ({"data_inicio": "2026-01-01"}, ["data_inicio"]),  # não é DD/MM/AAAA
        ({"data_inicio": ""}, ["data_inicio"]),
        ({"data_inicio": "01/01/1999"}, ["data_inicio"]),  # antes do lançamento do jogo
        ({"nome": "   "}, ["nome"]),
        ({"nome": "x" * 151}, ["nome"]),
        ({"versao": "1" * 21}, ["versao"]),
        ({"tipo": "FESTA"}, ["tipo"]),
        ({"tipo": ""}, ["tipo"]),
        ({"regiao": "CN"}, ["regiao"]),
        ({"data_fim": "01/01/2025"}, ["data_fim"]),  # termina antes de começar
        ({"data_fim": "amanhã"}, ["data_fim"]),
        ({"nome": "", "tipo": "X", "data_inicio": "99/99/9999"}, ["nome", "tipo", "data_inicio"]),
    ],
)
def test_cu10_c2_fa2_dados_invalidos_no_cadastro_manual(admin_client, db_session, corpo, campos):
    token = _token_de_admin(admin_client, db_session)

    resposta = _cadastrar(admin_client, token, **corpo)

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": {"message": FA2_INVALIDO, "fields": campos}}
    assert _do_banco(db_session) == []


# ---------------------------------------------------------------------- FE1: estrutura da página alterada


@pytest.mark.parametrize("fonte, url", [("EXPANSOES", URL_EXPANSOES), ("PATCHES", URL_PATCHES), ("SAZONAIS", URL_FERIADOS)])
def test_cu10_c2_fe1_estrutura_da_pagina_alterada_nao_registra_eventos(admin_client, paginas, db_session, fonte, url, caplog):
    paginas.paginas[url] = PAGINA_SEM_A_TABELA  # o layout mudou: as tabelas conhecidas não existem mais
    token = _token_de_admin(admin_client, db_session)

    with caplog.at_level("ERROR", logger="src.services.evento_service"):
        resposta = _extrair(admin_client, token, fonte)

    assert resposta.status_code == 502
    assert resposta.json() == {"detail": FE1}
    assert _do_banco(db_session) == []  # não registra eventos
    log = db_session.query(ExtracaoEvento).one()  # e grava a falha em log
    assert (log.fonte, log.status, log.eventos_registrados) == (fonte, "FALHA", 0) and log.erro
    assert "CU10-C2-FE1" in caplog.text


def test_cu10_c2_fe1_a_fonte_fora_do_ar_tem_o_mesmo_tratamento(admin_client, paginas, db_session):
    paginas.erro = FonteDeEventosIndisponivelError("ConnectTimeout: tempo limite esgotado")
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "PATCHES")

    assert (resposta.status_code, resposta.json()) == (502, {"detail": FE1})
    assert "ConnectTimeout" in db_session.query(ExtracaoEvento).one().erro


def test_cu10_c2_fe1_uma_pagina_que_o_provider_nao_reconhece_nem_e_consultada(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    for url in (
        "https://www.wowhead.com/events",  # o Wowhead carrega os eventos por JavaScript
        "http://localhost:8025/",  # nada de consultar a rede interna
        "https://en.wikipedia.org.exemplo.com/wiki/World_of_Warcraft",
        "ftp://en.wikipedia.org/wiki/World_of_Warcraft",
        "isto-nao-e-um-endereco",
    ):
        resposta = _extrair(admin_client, token, "EXPANSOES", url=url)
        assert (resposta.status_code, resposta.json()) == (502, {"detail": FE1}), url

    assert paginas.chamadas == []
    assert _do_banco(db_session) == []


def test_cu10_c2_o_endereco_informado_e_lido_quando_e_da_fonte(admin_client, paginas, db_session):
    outra = "https://en.wikipedia.org/wiki/World_of_Warcraft?action=raw"
    paginas.paginas[outra] = paginas.paginas[URL_EXPANSOES]
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "EXPANSOES", url=outra)

    assert resposta.status_code == 200 and paginas.chamadas == [outra]


def test_cu10_c2_fe1_api_da_blizzard_fora_do_ar(admin_client, cliente_blizzard, db_session):
    cliente_blizzard.erro = ApiIndisponivelError("A API não respondeu após 4 tentativas: HTTP 503")
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "TEMPORADAS")

    assert (resposta.status_code, resposta.json()) == (502, {"detail": FE1})
    assert _do_banco(db_session) == []


def test_cu10_c2_fe1_resposta_da_api_com_outro_formato(admin_client, cliente_blizzard, db_session):
    cliente_blizzard.respostas_json = {"/data/wow/mythic-keystone/season/index": {"temporadas": []}}
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "TEMPORADAS")

    assert (resposta.status_code, resposta.json()) == (502, {"detail": FE1})


# ---------------------------------------------------------------------- demais regras


def test_cu10_c2_a_mesma_pagina_nao_e_lida_de_novo_em_menos_de_10_minutos(admin_client, paginas, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    assert _extrair(admin_client, token, "EXPANSOES").status_code == 200

    relogio.avancar(minutes=9)
    cedo = _extrair(admin_client, token, "EXPANSOES")
    outra_pagina = _extrair(admin_client, token, "PATCHES")  # outra fonte não é afetada
    relogio.avancar(minutes=2)
    depois = _extrair(admin_client, token, "EXPANSOES")

    assert cedo.status_code == 429
    assert cedo.json() == {"detail": "Esta fonte foi lida há pouco. Aguarde alguns minutos antes de extrair novamente"}
    assert outra_pagina.status_code == 200 and depois.status_code == 200
    assert paginas.chamadas == [URL_EXPANSOES, URL_PATCHES, URL_EXPANSOES]  # a leitura recusada não chegou à página


def test_cu10_c2_falha_de_banco_desfaz_o_registro(admin_client, paginas, db_session, mocker):
    from src.repositories.evento_repository import EventoRepository

    mocker.patch.object(EventoRepository, "registrar", side_effect=OperationalError("INSERT INTO evento_jogo", {}, Exception("connection lost")))
    token = _token_de_admin(admin_client, db_session)

    resposta = _extrair(admin_client, token, "PATCHES")

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "Não foi possível registrar os eventos no momento. Tente novamente mais tarde"}
    assert _do_banco(db_session) == []


def test_cu10_c2_fonte_desconhecida_e_recusada(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)

    for fonte in ("", "WOWHEAD", "todas"):
        resposta = _extrair(admin_client, token, fonte)
        assert (resposta.status_code, resposta.json()) == (422, {"detail": "Informe uma fonte de eventos válida"}), fonte

    assert paginas.chamadas == []


def test_cu10_c2_so_o_admin_extrai_cadastra_e_lista_eventos(admin_client, paginas, db_session):
    token_comum = cadastrar_e_entrar(admin_client)  # papel "usuario"

    sem_sessao = admin_client.post("/api/admin/events/extract", json={"fonte": "PATCHES"})
    extrair = _extrair(admin_client, token_comum, "PATCHES")
    cadastrar = _cadastrar(admin_client, token_comum)
    listar = admin_client.get("/api/admin/events", headers=cabecalho(token_comum))

    assert sem_sessao.status_code == 401
    assert (extrair.status_code, cadastrar.status_code, listar.status_code) == (403, 403, 403)
    assert extrair.json() == {"detail": "Acesso restrito ao administrador"}
    assert paginas.chamadas == [] and _do_banco(db_session) == []


def test_cu10_c2_lista_os_eventos_registrados_do_mais_recente_ao_mais_antigo(admin_client, paginas, db_session):
    token = _token_de_admin(admin_client, db_session)
    _extrair(admin_client, token, "PATCHES")
    _cadastrar(admin_client, token, nome="Feira especial", tipo="OUTRO", data_inicio="01/01/2027", versao=None)

    tudo = admin_client.get("/api/admin/events", headers=cabecalho(token)).json()
    patches = admin_client.get("/api/admin/events?tipo=patch&limite=2&deslocamento=1", headers=cabecalho(token)).json()
    europa = admin_client.get("/api/admin/events?regiao=EU", headers=cabecalho(token)).json()

    assert tudo["total"] == 9 and tudo["eventos"][0]["nome"] == "Feira especial"  # o mais recente primeiro
    assert [e["versao"] for e in patches["eventos"]] == ["12.0.7", "12.0.5"] and patches["total"] == 8
    assert europa == {"total": 0, "eventos": []}
