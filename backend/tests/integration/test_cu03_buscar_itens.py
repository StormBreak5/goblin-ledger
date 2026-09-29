"""
Plano de testes do CU03 – Buscar Itens (RF02), fluxos que dependem do banco de dados.

Cada teste usa o nome do fluxo no documento do TC (CU03-C1, C2 e C3). Rodam contra um PostgreSQL temporário
(ver conftest.py) porque a busca sem acentuação usa a extensão `unaccent`.
"""
from datetime import datetime, timezone

from src.services.item_service import (
    MSG_ITEM_INDISPONIVEL,
    MSG_NENHUM_ITEM_POR_ID,
    MSG_NENHUM_ITEM_POR_NOME,
)

ICONE = "https://render.worldofwarcraft.com/us/icons/56/inv_potion_92.jpg"


def _buscar(client, termo: str, **params):
    return client.get("/api/items/search", params={"q": termo, **params})


def _nomes(resposta) -> list[str]:
    return [item["name"] for item in resposta.json()["items"]]


# ---------------------------------------------------------------- CU03-C1: pesquisar item por nome

def test_cu03_c1_fluxo_principal_lista_itens_paginada_com_nome_e_icone(client, add_item):
    add_item(2001, "Flask of Supreme Power", ICONE)
    add_item(2002, "Flask of Alchemical Chaos")
    add_item(3001, "Iron Bar")

    resposta = _buscar(client, "flask")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["search_type"] == "name"
    assert corpo["message"] is None
    assert (corpo["page"], corpo["page_size"], corpo["total"], corpo["total_pages"]) == (1, 10, 2, 1)
    assert [(i["id"], i["name"], i["icon_url"]) for i in corpo["items"]] == [
        (2002, "Flask of Alchemical Chaos", None),
        (2001, "Flask of Supreme Power", ICONE),
    ]


def test_cu03_c1_fluxo_principal_desconsidera_acentuacao_e_caixa(client, add_item):
    add_item(1001, "Poção de Cura Maior")
    add_item(1002, "POÇÃO DE MANA")
    add_item(1003, "Pocao de Velocidade")
    add_item(1004, "Elixir de Fúria")
    add_item(1005, "Barra de Ferro")

    for termo in ("pocao", "POÇÃO", "poção", "PoCaO"):
        assert _nomes(_buscar(client, termo)) == [
            "POÇÃO DE MANA",
            "Pocao de Velocidade",
            "Poção de Cura Maior",
        ], termo

    assert _nomes(_buscar(client, "furia")) == ["Elixir de Fúria"]
    assert _nomes(_buscar(client, "FÚRIA")) == ["Elixir de Fúria"]


def test_cu03_c1_fluxo_principal_recupera_data_ultima_atualizacao_do_leilao(client, add_item, add_history):
    add_item(4001, "Copper Ore")
    add_item(4002, "Tin Ore")
    add_history(4001, datetime(2026, 6, 14), region="3209")
    add_history(4001, datetime(2026, 6, 16, 13, 30), region="3209")
    add_history(4001, datetime(2026, 6, 15), region="32512")
    add_history(4999, datetime(2026, 9, 1))  # histórico de outro item não interfere

    itens = {i["name"]: i for i in _buscar(client, "ore").json()["items"]}

    ultima = datetime.fromisoformat(itens["Copper Ore"]["last_auction_update"].replace("Z", "+00:00"))
    assert ultima == datetime(2026, 6, 16, 13, 30, tzinfo=timezone.utc)
    assert itens["Tin Ore"]["last_auction_update"] is None


def test_cu03_c1_fluxo_principal_segunda_pagina_nao_repete_itens(client, add_item):
    for numero in range(1, 13):
        add_item(5000 + numero, f"Herb {numero:02d}")

    paginas = [_buscar(client, "herb", page=pagina, page_size=5).json() for pagina in (1, 2, 3)]
    ids = [item["id"] for pagina in paginas for item in pagina["items"]]

    assert [len(pagina["items"]) for pagina in paginas] == [5, 5, 2]
    assert len(set(ids)) == 12
    assert all(pagina["total"] == 12 and pagina["total_pages"] == 3 for pagina in paginas)
    assert [pagina["page"] for pagina in paginas] == [1, 2, 3]

    alem_do_fim = _buscar(client, "herb", page=4, page_size=5).json()
    assert alem_do_fim["items"] == [] and alem_do_fim["total"] == 12 and alem_do_fim["message"] is None


def test_cu03_c1_fluxo_principal_curingas_like_sao_tratados_como_texto(client, add_item):
    add_item(6001, "100% Pure Water")
    add_item(6002, "Water of 1000 Uses")
    add_item(6003, "Under_score Item")
    add_item(6004, "Underscore Item")
    add_item(6005, r"Back\slash Item")

    assert _nomes(_buscar(client, "100%")) == ["100% Pure Water"]
    assert _nomes(_buscar(client, "Under_s")) == ["Under_score Item"]
    assert _nomes(_buscar(client, "k\\s")) == [r"Back\slash Item"]


def test_cu03_c1_fluxo_principal_termo_com_apostrofo_e_virgula_e_aceito(client, add_item):
    add_item(6101, "Sylvanas' Hood")
    add_item(6102, "Thunderfury, Blessed Blade of the Windseeker")

    assert _nomes(_buscar(client, "sylvanas'")) == ["Sylvanas' Hood"]
    assert _nomes(_buscar(client, "thunderfury, blessed")) == ["Thunderfury, Blessed Blade of the Windseeker"]


def test_cu03_c1_fa1_limite_de_tres_caracteres_executa_a_consulta(client, add_item):
    add_item(7001, "Iron Bar")

    assert _nomes(_buscar(client, "iro")) == ["Iron Bar"]
    assert _nomes(_buscar(client, "  iro  ")) == ["Iron Bar"]


def test_cu03_c1_fa2_nenhum_item_encontrado(client, add_item):
    add_item(7002, "Iron Bar")

    resposta = _buscar(client, "xyzabc")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["items"] == [] and corpo["total"] == 0 and corpo["total_pages"] == 0
    assert corpo["search_type"] == "name"
    assert corpo["message"] == MSG_NENHUM_ITEM_POR_NOME == "Nenhum item encontrado para o termo pesquisado"


# ---------------------------------------------------------------- CU03-C2: pesquisar item por identificador

def test_cu03_c2_fluxo_principal_busca_por_identificador_retorna_item_unico(client, add_item):
    add_item(7972, "Ghost Iron Bar", ICONE)
    add_item(79720, "Outro Item")  # o identificador é comparado por igualdade, não por parte do número

    for termo in ("7972", "007972", "  7972  "):
        resposta = _buscar(client, termo)
        corpo = resposta.json()
        assert resposta.status_code == 200, termo
        assert corpo["search_type"] == "id"
        assert corpo["total"] == 1 and corpo["total_pages"] == 1 and corpo["message"] is None
        assert [(i["id"], i["name"], i["icon_url"]) for i in corpo["items"]] == [(7972, "Ghost Iron Bar", ICONE)]


def test_cu03_c2_fluxo_principal_recupera_data_ultima_atualizacao_do_leilao(client, add_item, add_history):
    add_item(7972, "Ghost Iron Bar")
    add_history(7972, datetime(2026, 5, 1))
    add_history(7972, datetime(2026, 6, 16))

    item = _buscar(client, "7972").json()["items"][0]

    assert datetime.fromisoformat(item["last_auction_update"].replace("Z", "+00:00")) == datetime(
        2026, 6, 16, tzinfo=timezone.utc
    )


def test_cu03_c2_fa1_identificador_inexistente(client, add_item):
    add_item(7972, "Ghost Iron Bar")

    resposta = _buscar(client, "99999")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["items"] == [] and corpo["total"] == 0
    assert corpo["search_type"] == "id"
    assert corpo["message"] == MSG_NENHUM_ITEM_POR_ID == "Nenhum item corresponde ao identificador informado"


def test_cu03_c2_fa2_termo_alfanumerico_e_tratado_como_busca_textual(client, add_item):
    add_item(7972, "Ghost Iron Bar")
    add_item(8001, "Rune 7972a")
    add_item(8002, "Item 12b")

    resposta = _buscar(client, "7972a")
    assert resposta.json()["search_type"] == "name"
    assert _nomes(resposta) == ["Rune 7972a"]

    assert _nomes(_buscar(client, "Item 12b")) == ["Item 12b"]


# ---------------------------------------------------------------- CU03-C3: selecionar item do resultado

def test_cu03_c3_fluxo_principal_detalhes_do_item_selecionado(client, add_item):
    add_item(7972, "Ghost Iron Bar", ICONE)

    resposta = client.get("/api/items/7972")

    assert resposta.status_code == 200
    assert resposta.json() == {"id": 7972, "name": "Ghost Iron Bar", "icon_url": ICONE}


def test_cu03_c3_fe1_item_removido_durante_a_navegacao(client, add_item, db_session):
    item = add_item(7972, "Ghost Iron Bar")
    assert client.get("/api/items/7972").status_code == 200

    db_session.delete(item)  # o item deixa de existir entre a busca e a abertura dos detalhes
    db_session.commit()
    resposta = client.get("/api/items/7972")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": MSG_ITEM_INDISPONIVEL}
    assert MSG_ITEM_INDISPONIVEL == "Item indisponível. Realize uma nova busca"
