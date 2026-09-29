"""Atalhos compartilhados pelos testes do CU01 e do CU02."""
from contextlib import contextmanager

from sqlalchemy.exc import OperationalError

SENHA = "SenhaForte123"
EMAIL = "maria@exemplo.com"
DETALHE_TECNICO = 'connection to server at "db" (172.18.0.2), port 5435 failed: password authentication failed'


def erro_de_banco() -> OperationalError:
    return OperationalError("UPDATE usuario SET ...", {}, Exception(DETALHE_TECNICO))


def sem_detalhe_tecnico(resposta) -> bool:
    return "password" not in resposta.text and "172.18" not in resposta.text


def abridor_que_falha():
    """Simula o banco fora do ar já na abertura da sessão."""
    @contextmanager
    def abrir():
        raise erro_de_banco()
        yield  # pragma: no cover

    return abrir


def dados_cadastro(**alteracoes) -> dict:
    dados = {"email": EMAIL, "senha": SENHA, "confirmacao_senha": SENHA, "regiao": "US"}
    dados.update(alteracoes)
    return dados


def cadastrar(client, **alteracoes):
    return client.post("/api/users", json=dados_cadastro(**alteracoes))


def entrar(client, email: str = EMAIL, senha: str = SENHA):
    return client.post("/api/auth/login", json={"email": email, "senha": senha})


def cabecalho(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def cadastrar_e_entrar(client, **alteracoes) -> str:
    """Cadastra a conta e devolve o token da sessão."""
    assert cadastrar(client, **alteracoes).status_code == 201
    resposta = entrar(client, alteracoes.get("email", EMAIL), alteracoes.get("senha", SENHA))
    assert resposta.status_code == 200
    return resposta.json()["access_token"]
