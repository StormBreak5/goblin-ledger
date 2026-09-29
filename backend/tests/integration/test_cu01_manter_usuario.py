"""
Plano de testes do CU01 – Manter Usuário (RF01): um teste por fluxo do documento do TC.
Rodam contra um PostgreSQL temporário (ver tests/conftest.py); relógio e e-mail são falsos.
"""
import pytest

from helpers_auth import (
    EMAIL,
    SENHA,
    abridor_que_falha,
    cabecalho,
    cadastrar,
    cadastrar_e_entrar,
    entrar,
    erro_de_banco,
    sem_detalhe_tecnico,
)
from src.models.usuario import Sessao, TentativaLogin, TokenRecuperacao, Usuario
from src.services import security

CAMPOS_INVALIDOS = "Verifique os campos destacados"
FALHA_CADASTRO = "Não foi possível concluir o cadastro no momento. Tente novamente mais tarde"
FALHA_ATUALIZACAO = "Não foi possível atualizar os dados no momento. Tente novamente mais tarde"
FALHA_EXCLUSAO = "Não foi possível excluir a conta no momento. Tente novamente mais tarde"


# ---------------------------------------------------------------- CU01-C1: cadastrar usuário

def test_cu01_c1_fluxo_principal_cadastra_usuario(auth_client, db_session, relogio):
    resposta = cadastrar(auth_client, email="  Maria@Exemplo.COM ", regiao="us")

    assert resposta.status_code == 201
    assert resposta.json() == {"message": "Conta criada com sucesso"}
    usuario = db_session.query(Usuario).one()
    assert usuario.email == EMAIL  # normalizado: sem espaços e em minúsculas
    assert usuario.regiao == "US"
    assert usuario.role == "usuario"
    assert usuario.data_criacao == relogio()
    assert usuario.senha_hash != SENHA and usuario.senha_hash.startswith("$2")  # somente o hash bcrypt (RNF06)
    assert security.senha_confere(SENHA, usuario.senha_hash)


def test_cu01_c1_fa1_dados_invalidos(auth_client, db_session):
    casos = {
        "e-mail vazio": ({"email": ""}, ["email"]),
        "e-mail sem arroba": ({"email": "mariaexemplo.com"}, ["email"]),
        "e-mail longo demais": ({"email": "a" * 145 + "@b.com"}, ["email"]),
        "senha vazia": ({"senha": "", "confirmacao_senha": ""}, ["senha"]),
        "senha curta": ({"senha": "abc", "confirmacao_senha": "abc"}, ["senha"]),
        "confirmação divergente": ({"confirmacao_senha": "OutraSenha123"}, ["confirmacao_senha"]),
        "região fora de US/EU (RN11)": ({"regiao": "BR"}, ["regiao"]),
        "região vazia": ({"regiao": ""}, ["regiao"]),
    }
    for descricao, (alteracoes, campos_esperados) in casos.items():
        resposta = cadastrar(auth_client, **alteracoes)

        assert resposta.status_code == 422, descricao
        detalhe = resposta.json()["detail"]
        assert detalhe["message"] == CAMPOS_INVALIDOS, descricao
        assert set(campos_esperados) <= set(detalhe["fields"]), descricao

    assert db_session.query(Usuario).count() == 0


def test_cu01_c1_fa2_email_ja_cadastrado_rn18(auth_client, db_session):
    assert cadastrar(auth_client).status_code == 201

    resposta = cadastrar(auth_client, email=" MARIA@exemplo.com ", regiao="EU")

    assert resposta.status_code == 409
    assert resposta.json() == {"detail": "Já existe uma conta cadastrada com este e-mail"}
    assert db_session.query(Usuario).count() == 1
    assert db_session.query(Usuario).one().regiao == "US"  # a conta original não foi tocada


@pytest.mark.parametrize("ponto_de_falha", ["gravacao", "sessao"])
def test_cu01_c1_fe1_falha_na_comunicacao_com_banco_de_dados(
    make_auth_client, auth_client, db_session, mocker, ponto_de_falha
):
    if ponto_de_falha == "gravacao":
        mocker.patch.object(db_session, "commit", side_effect=erro_de_banco())  # falha no passo 7
        cliente = auth_client
    else:
        cliente = make_auth_client(abridor_que_falha())

    resposta = cadastrar(cliente)

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_CADASTRO}
    assert sem_detalhe_tecnico(resposta)
    mocker.stopall()
    assert db_session.query(Usuario).count() == 0


# ---------------------------------------------------------------- CU01-C2: alterar dados do usuário

def _alterar(client, token, **campos):
    corpo = {"regiao": "EU", "senha_atual": "", "nova_senha": "", "confirmacao_nova_senha": ""}
    corpo.update(campos)
    return client.put("/api/users/me", json=corpo, headers=cabecalho(token))


def test_cu01_c2_fluxo_principal_altera_regiao_e_senha(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)
    perfil = auth_client.get("/api/users/me", headers=cabecalho(token))
    assert perfil.json() == {"email": EMAIL, "regiao": "US", "role": "usuario"}  # passo 2: e-mail somente leitura

    resposta = _alterar(
        auth_client, token, senha_atual=SENHA, nova_senha="NovaSenha456", confirmacao_nova_senha="NovaSenha456"
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"message": "Dados atualizados com sucesso"}
    db_session.expire_all()
    usuario = db_session.query(Usuario).one()
    assert usuario.regiao == "EU"
    assert security.senha_confere("NovaSenha456", usuario.senha_hash)
    assert not security.senha_confere(SENHA, usuario.senha_hash)
    assert entrar(auth_client, senha=SENHA).status_code == 401
    assert entrar(auth_client, senha="NovaSenha456").status_code == 200


def test_cu01_c2_fa1_altera_somente_a_regiao(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)
    hash_antes = db_session.query(Usuario).one().senha_hash

    resposta = _alterar(auth_client, token, regiao="EU")

    assert resposta.status_code == 200
    db_session.expire_all()
    usuario = db_session.query(Usuario).one()
    assert usuario.regiao == "EU"
    assert usuario.senha_hash == hash_antes  # sem conferência nem nova criptografia de senha


def test_cu01_c2_fa2_confirmacao_divergente(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)

    resposta = _alterar(
        auth_client, token, senha_atual=SENHA, nova_senha="NovaSenha456", confirmacao_nova_senha="Diferente789"
    )

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "A nova senha e a confirmação não coincidem"}
    db_session.expire_all()
    usuario = db_session.query(Usuario).one()
    assert usuario.regiao == "US" and security.senha_confere(SENHA, usuario.senha_hash)


def test_cu01_c2_fa3_senha_atual_incorreta_rn19(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)

    resposta = _alterar(
        auth_client, token, senha_atual="ErradaErrada1", nova_senha="NovaSenha456", confirmacao_nova_senha="NovaSenha456"
    )

    assert resposta.status_code == 400
    assert resposta.json() == {"detail": "Senha atual incorreta"}
    db_session.expire_all()
    usuario = db_session.query(Usuario).one()
    assert usuario.regiao == "US" and security.senha_confere(SENHA, usuario.senha_hash)


@pytest.mark.parametrize("ponto_de_falha", ["gravacao", "sessao"])
def test_cu01_c2_fe1_falha_de_banco_mantem_dados(
    make_auth_client, auth_client, db_session, mocker, ponto_de_falha
):
    token = cadastrar_e_entrar(auth_client)
    if ponto_de_falha == "gravacao":
        mocker.patch.object(db_session, "commit", side_effect=erro_de_banco())  # falha no passo 8
        cliente = auth_client
    else:
        cliente = make_auth_client(abridor_que_falha())

    resposta = _alterar(cliente, token, regiao="EU")

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_ATUALIZACAO}
    assert sem_detalhe_tecnico(resposta)
    mocker.stopall()
    db_session.expire_all()
    assert db_session.query(Usuario).one().regiao == "US"  # dados anteriores mantidos


def test_cu01_c2_email_nao_pode_ser_alterado_rn18(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)

    resposta = auth_client.put(
        "/api/users/me",
        json={"email": "outro@exemplo.com", "regiao": "EU"},
        headers=cabecalho(token),
    )

    assert resposta.status_code == 200
    db_session.expire_all()
    assert db_session.query(Usuario).one().email == EMAIL  # o campo extra é ignorado


def test_cu01_c2_regiao_invalida_e_campo_exigido_para_trocar_senha(auth_client):
    token = cadastrar_e_entrar(auth_client)

    regiao_invalida = _alterar(auth_client, token, regiao="BR")
    senha_sem_atual = _alterar(auth_client, token, nova_senha="NovaSenha456", confirmacao_nova_senha="NovaSenha456")

    assert regiao_invalida.status_code == 422
    assert regiao_invalida.json()["detail"] == {"message": CAMPOS_INVALIDOS, "fields": ["regiao"]}
    assert senha_sem_atual.status_code == 422
    assert senha_sem_atual.json()["detail"] == {"message": CAMPOS_INVALIDOS, "fields": ["senha_atual"]}


def test_cu01_c2_exige_sessao_autenticada(auth_client):
    sem_token = auth_client.get("/api/users/me")
    token_invalido = auth_client.get("/api/users/me", headers=cabecalho("nao-e-um-jwt"))

    assert sem_token.status_code == token_invalido.status_code == 401
    assert sem_token.json() == {"detail": "Sua sessão expirou. Faça login novamente"}


# ---------------------------------------------------------------- CU01-C3: excluir conta do usuário

def _excluir(client, token, senha):
    return client.request("DELETE", "/api/users/me", json={"senha": senha}, headers=cabecalho(token))


def test_cu01_c3_fluxo_principal_exclui_conta_e_dados_rn20(auth_client, db_session, email_falso):
    token = cadastrar_e_entrar(auth_client)
    entrar(auth_client, senha="ErradaErrada1")  # gera uma linha de tentativas de login
    auth_client.post("/api/auth/password-recovery", json={"email": EMAIL})  # gera um token de recuperação
    assert db_session.query(Sessao).count() == 1
    assert db_session.query(TokenRecuperacao).count() == 1
    assert db_session.query(TentativaLogin).count() == 1

    resposta = _excluir(auth_client, token, SENHA)

    assert resposta.status_code == 204
    assert db_session.query(Usuario).count() == 0
    assert db_session.query(Sessao).count() == 0  # RN20: nada de residual
    assert db_session.query(TokenRecuperacao).count() == 0
    assert db_session.query(TentativaLogin).count() == 0
    assert auth_client.get("/api/users/me", headers=cabecalho(token)).status_code == 401  # a sessão foi encerrada
    assert entrar(auth_client).status_code == 401  # a conta não existe mais


def test_cu01_c3_fa2_senha_incorreta_rn19(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)

    for senha in ("ErradaErrada1", ""):
        resposta = _excluir(auth_client, token, senha)

        assert resposta.status_code == 400
        assert resposta.json() == {"detail": "Senha incorreta. A conta não foi excluída"}

    assert db_session.query(Usuario).count() == 1
    assert auth_client.get("/api/users/me", headers=cabecalho(token)).status_code == 200


@pytest.mark.parametrize("ponto_de_falha", ["gravacao", "sessao"])
def test_cu01_c3_fe1_falha_desfaz_remocoes_rn20(make_auth_client, auth_client, db_session, mocker, ponto_de_falha):
    token = cadastrar_e_entrar(auth_client)
    entrar(auth_client, senha="ErradaErrada1")
    if ponto_de_falha == "gravacao":
        # As remoções já foram feitas na transação (flush) quando o banco cai no commit: tudo deve ser desfeito.
        mocker.patch.object(db_session, "commit", side_effect=erro_de_banco())
        cliente = auth_client
    else:
        cliente = make_auth_client(abridor_que_falha())

    resposta = _excluir(cliente, token, SENHA)

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_EXCLUSAO}
    assert sem_detalhe_tecnico(resposta)
    mocker.stopall()
    db_session.expire_all()
    assert db_session.query(Usuario).count() == 1  # conta e dados vinculados inalterados
    assert db_session.query(Sessao).count() == 1
    assert db_session.query(TentativaLogin).count() == 1
