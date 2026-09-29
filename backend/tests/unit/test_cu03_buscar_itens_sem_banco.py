"""
Plano de testes do CU03 – Buscar Itens (RF02), fluxos que não dependem de dados no banco:
termo insuficiente (C1-FA1) e falhas de comunicação com o banco de dados (C1-FE1 e C2-FE1).
"""
import pytest
from sqlalchemy.exc import OperationalError

from src.services.item_service import ItemService

MSG_TERMO_INSUFICIENTE = "Digite ao menos três caracteres para pesquisar"
MSG_FALHA_NA_BUSCA = "Não foi possível realizar a busca no momento. Tente novamente mais tarde"
DETALHE_TECNICO = 'connection to server at "db" (172.18.0.2), port 5435 failed: password authentication failed'


def _erro_de_banco() -> OperationalError:
    return OperationalError("SELECT items.id FROM items", {}, Exception(DETALHE_TECNICO))


class _ServicoComBancoForaDoAr:
    def search_items(self, **kwargs):
        raise _erro_de_banco()


def test_cu03_c1_fa1_termo_com_menos_de_tres_caracteres(make_client, mocker):
    sessao = mocker.Mock()
    client = make_client(lambda: ItemService(sessao))

    for termo in ("", "a", "ab", "  ab  ", "   "):
        resposta = client.get("/api/items/search", params={"q": termo})

        assert resposta.status_code == 422, repr(termo)
        assert resposta.json() == {"detail": MSG_TERMO_INSUFICIENTE}, repr(termo)

    assert sessao.mock_calls == []  # a consulta não é executada


@pytest.mark.parametrize("ponto_de_falha", ["consulta", "sessao"])
def test_cu03_c1_fe1_falha_na_comunicacao_com_banco_de_dados(make_client, mocker, ponto_de_falha):
    client = _cliente_com_banco_fora_do_ar(make_client, mocker, ponto_de_falha)

    resposta = client.get("/api/items/search", params={"q": "flask"})

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": MSG_FALHA_NA_BUSCA}
    assert "password" not in resposta.text and "172.18" not in resposta.text  # sem detalhe técnico


@pytest.mark.parametrize("ponto_de_falha", ["consulta", "sessao"])
def test_cu03_c2_fe1_falha_na_comunicacao_com_banco_de_dados(make_client, mocker, ponto_de_falha):
    client = _cliente_com_banco_fora_do_ar(make_client, mocker, ponto_de_falha)

    resposta = client.get("/api/items/search", params={"q": "7972"})

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": MSG_FALHA_NA_BUSCA}
    assert "password" not in resposta.text and "172.18" not in resposta.text


def _cliente_com_banco_fora_do_ar(make_client, mocker, ponto_de_falha: str):
    """'consulta': o banco cai durante a consulta. 'sessao': a sessão nem chega a ser obtida."""
    if ponto_de_falha == "consulta":
        return make_client(lambda: _ServicoComBancoForaDoAr())
    mocker.patch("src.controllers.item_controller.get_session", side_effect=_erro_de_banco())
    return make_client(None)
