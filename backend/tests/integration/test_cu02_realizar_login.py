"""
Plano de testes do CU02 – Realizar Login (RF01): um teste por fluxo do documento do TC.
Rodam contra um PostgreSQL temporário (ver tests/conftest.py); relógio e e-mail são falsos.
"""
from datetime import datetime

import pytest
from sqlalchemy import text

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
from src.repositories.usuario_repository import UsuarioRepository
from src.services import security

CAMPOS_INVALIDOS = "Verifique os campos destacados"
CREDENCIAIS_INVALIDAS = "Credenciais inválidas"
ACESSO_BLOQUEADO = "Acesso temporariamente bloqueado por excesso de tentativas. Tente novamente mais tarde"
FALHA_LOGIN = "Não foi possível realizar o login no momento. Tente novamente mais tarde"
RECUPERACAO_SOLICITADA = "Se o e-mail estiver cadastrado, você receberá as instruções de recuperação"
FALHA_RECUPERACAO = "Não foi possível processar a solicitação no momento. Tente novamente mais tarde"
LINK_INVALIDO = "Link de recuperação inválido ou expirado. Solicite uma nova recuperação de senha"
FALHA_REDEFINICAO = "Não foi possível redefinir a senha no momento. Tente novamente mais tarde"
SESSAO_EXPIRADA = "Sua sessão expirou. Faça login novamente"


# ---------------------------------------------------------------- CU02-C1: autenticar usuário

def test_cu02_c1_fluxo_principal_inicia_sessao(auth_client, db_session, relogio):
    assert cadastrar(auth_client).status_code == 201

    resposta = entrar(auth_client, email=" MARIA@Exemplo.com ")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["usuario"] == {"email": EMAIL, "regiao": "US", "role": "usuario"}
    assert datetime.fromisoformat(corpo["expires_at"]) == relogio() + security.DURACAO_DA_SESSAO  # 24 h
    sessao = db_session.query(Sessao).one()
    conteudo = security.ler_token(corpo["access_token"])
    assert conteudo["jti"] == str(sessao.id_sessao) and conteudo["sub"] == str(sessao.id_usuario)
    assert conteudo["exp"] - conteudo["iat"] == 24 * 3600
    assert auth_client.get("/api/users/me", headers=cabecalho(corpo["access_token"])).status_code == 200


def test_cu02_c1_fa1_dados_invalidos(auth_client, db_session):
    casos = [
        ({"email": "", "senha": SENHA}, ["email"]),
        ({"email": "sem-arroba", "senha": SENHA}, ["email"]),
        ({"email": EMAIL, "senha": ""}, ["senha"]),
        ({"email": "", "senha": ""}, ["email", "senha"]),
    ]
    for corpo, campos in casos:
        resposta = auth_client.post("/api/auth/login", json=corpo)

        assert resposta.status_code == 422, corpo
        assert resposta.json()["detail"] == {"message": CAMPOS_INVALIDOS, "fields": campos}, corpo

    assert db_session.query(TentativaLogin).count() == 0  # dados inválidos não contam como tentativa


def test_cu02_c1_fa2_credenciais_invalidas(auth_client, db_session):
    assert cadastrar(auth_client).status_code == 201

    senha_errada = entrar(auth_client, senha="ErradaErrada1")
    email_inexistente = entrar(auth_client, email="ninguem@exemplo.com")

    assert senha_errada.status_code == email_inexistente.status_code == 401
    assert senha_errada.json() == email_inexistente.json() == {"detail": CREDENCIAIS_INVALIDAS}  # sem dizer o que errou
    assert {t.email: t.falhas for t in db_session.query(TentativaLogin)} == {EMAIL: 1, "ninguem@exemplo.com": 1}
    assert db_session.query(Sessao).count() == 0


def test_cu02_c1_fa3_conta_bloqueada_rn21(auth_client, db_session, relogio):
    assert cadastrar(auth_client).status_code == 201

    for _ in range(5):  # cinco tentativas consecutivas malsucedidas
        assert entrar(auth_client, senha="ErradaErrada1").json() == {"detail": CREDENCIAIS_INVALIDAS}

    bloqueada = entrar(auth_client)  # até a senha certa é recusada durante o bloqueio
    assert bloqueada.status_code == 429
    assert bloqueada.json() == {"detail": ACESSO_BLOQUEADO}

    relogio.avancar(minutes=14, seconds=59)
    assert entrar(auth_client).status_code == 429
    relogio.avancar(seconds=2)  # 15 minutos depois: o bloqueio terminou
    assert entrar(auth_client).status_code == 200
    assert db_session.query(TentativaLogin).count() == 0  # o contador foi reiniciado pelo login bem-sucedido


def test_cu02_c1_fa3_contador_zera_apos_login_bem_sucedido_e_vale_para_email_sem_conta(auth_client, db_session):
    assert cadastrar(auth_client).status_code == 201
    for _ in range(4):
        entrar(auth_client, senha="ErradaErrada1")
    assert entrar(auth_client).status_code == 200  # login com sucesso zera as 4 falhas
    for _ in range(4):
        entrar(auth_client, senha="ErradaErrada1")
    assert entrar(auth_client).status_code == 200  # 4 novas falhas não bastam para bloquear

    for _ in range(5):  # e-mail sem conta: mesmo bloqueio, para não revelar quem tem conta
        entrar(auth_client, email="ninguem@exemplo.com")
    assert entrar(auth_client, email="ninguem@exemplo.com").json() == {"detail": ACESSO_BLOQUEADO}


@pytest.mark.parametrize("ponto_de_falha", ["consulta", "sessao"])
def test_cu02_c1_fe1_falha_de_banco(make_auth_client, auth_client, mocker, ponto_de_falha):
    assert cadastrar(auth_client).status_code == 201
    if ponto_de_falha == "consulta":
        mocker.patch.object(UsuarioRepository, "buscar_por_email", side_effect=erro_de_banco())  # passos 5 e 6
        cliente = auth_client
    else:
        cliente = make_auth_client(abridor_que_falha())

    resposta = entrar(cliente)

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_LOGIN}
    assert sem_detalhe_tecnico(resposta)


# ---------------------------------------------------------------- CU02-C2: solicitar recuperação de senha

def test_cu02_c2_fluxo_principal_envia_link_de_recuperacao(auth_client, db_session, email_falso, relogio):
    assert cadastrar(auth_client).status_code == 201

    resposta = auth_client.post("/api/auth/password-recovery", json={"email": " Maria@EXEMPLO.com "})

    assert resposta.status_code == 200
    assert resposta.json() == {"message": RECUPERACAO_SOLICITADA}
    assert len(email_falso.enviados) == 1
    envio = email_falso.enviados[0]
    assert envio["para"] == EMAIL and envio["validade_minutos"] == 10
    assert "/redefinir-senha?token=" in envio["link"]
    token = email_falso.token_do_ultimo_link()
    registro = db_session.query(TokenRecuperacao).one()
    assert registro.token_hash == security.hash_do_token(token)  # só o hash é armazenado (RN22)
    assert token not in registro.token_hash
    assert registro.expira_em == relogio() + security.timedelta(minutes=10)
    assert registro.invalidado_em is None


def test_cu02_c2_fa1_email_invalido(auth_client, db_session, email_falso):
    for email in ("", "sem-arroba", "a@b"):
        resposta = auth_client.post("/api/auth/password-recovery", json={"email": email})

        assert resposta.status_code == 422, email
        assert resposta.json() == {"detail": "Informe um e-mail válido"}

    assert email_falso.enviados == [] and db_session.query(TokenRecuperacao).count() == 0


def test_cu02_c2_fa2_email_nao_cadastrado(auth_client, db_session, email_falso):
    resposta = auth_client.post("/api/auth/password-recovery", json={"email": "ninguem@exemplo.com"})

    assert resposta.status_code == 200
    assert resposta.json() == {"message": RECUPERACAO_SOLICITADA}  # a mesma mensagem, sem revelar se há conta
    assert email_falso.enviados == []
    assert db_session.query(TokenRecuperacao).count() == 0


def test_cu02_c2_fe1_falha_no_envio_invalida_token(auth_client, db_session, email_falso, relogio):
    assert cadastrar(auth_client).status_code == 201
    email_falso.indisponivel = True

    resposta = auth_client.post("/api/auth/password-recovery", json={"email": EMAIL})

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_RECUPERACAO}
    registro = db_session.query(TokenRecuperacao).one()
    assert registro.invalidado_em == relogio()  # o token gerado foi invalidado


# ---------------------------------------------------------------- CU02-C3: redefinir senha

def _pedir_link(client, email_falso) -> str:
    assert client.post("/api/auth/password-recovery", json={"email": EMAIL}).status_code == 200
    return email_falso.token_do_ultimo_link()


def _redefinir(client, token, nova="NovaSenha456", confirmacao=None):
    return client.post(
        "/api/auth/password-reset",
        json={"token": token, "nova_senha": nova, "confirmacao_nova_senha": nova if confirmacao is None else confirmacao},
    )


def test_cu02_c3_fluxo_principal_redefine_senha_rn22(auth_client, db_session, email_falso):
    assert cadastrar(auth_client).status_code == 201
    token = _pedir_link(auth_client, email_falso)
    assert auth_client.post("/api/auth/password-reset/validate", json={"token": token}).status_code == 204  # passo 2

    resposta = _redefinir(auth_client, token)

    assert resposta.status_code == 200
    assert resposta.json() == {"message": "Senha redefinida com sucesso"}
    assert entrar(auth_client, senha=SENHA).status_code == 401
    assert entrar(auth_client, senha="NovaSenha456").status_code == 200
    # uso único: o token foi invalidado
    assert auth_client.post("/api/auth/password-reset/validate", json={"token": token}).status_code == 400
    assert _redefinir(auth_client, token, nova="OutraSenha789").status_code == 400


def test_cu02_c3_fa1_link_invalido_expirado_ou_usado(auth_client, email_falso, relogio):
    assert cadastrar(auth_client).status_code == 201

    def link_invalido(token) -> bool:
        validacao = auth_client.post("/api/auth/password-reset/validate", json={"token": token})
        redefinicao = _redefinir(auth_client, token)
        return (
            validacao.status_code == redefinicao.status_code == 400
            and validacao.json() == redefinicao.json() == {"detail": LINK_INVALIDO}
        )

    assert link_invalido("token-que-nunca-foi-emitido")  # inválido
    assert link_invalido("")

    expirado = _pedir_link(auth_client, email_falso)  # expirado: 10 minutos
    relogio.avancar(minutes=9, seconds=59)
    assert auth_client.post("/api/auth/password-reset/validate", json={"token": expirado}).status_code == 204
    relogio.avancar(seconds=2)
    assert link_invalido(expirado)

    usado = _pedir_link(auth_client, email_falso)  # já utilizado
    assert _redefinir(auth_client, usado).status_code == 200
    assert link_invalido(usado)

    anterior = _pedir_link(auth_client, email_falso)  # RN22: um novo link invalida os anteriores
    novo = _pedir_link(auth_client, email_falso)
    assert link_invalido(anterior)
    assert auth_client.post("/api/auth/password-reset/validate", json={"token": novo}).status_code == 204


def test_cu02_c3_fa2_confirmacao_divergente(auth_client, db_session, email_falso):
    assert cadastrar(auth_client).status_code == 201
    token = _pedir_link(auth_client, email_falso)

    resposta = _redefinir(auth_client, token, nova="NovaSenha456", confirmacao="Diferente789")

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "A nova senha e a confirmação não coincidem"}
    assert entrar(auth_client, senha=SENHA).status_code == 200  # a senha não mudou
    assert auth_client.post("/api/auth/password-reset/validate", json={"token": token}).status_code == 204  # token segue válido


@pytest.mark.parametrize("ponto_de_falha", ["gravacao", "sessao"])
def test_cu02_c3_fe1_falha_de_banco_mantem_senha_e_token(
    make_auth_client, auth_client, db_session, email_falso, mocker, ponto_de_falha
):
    assert cadastrar(auth_client).status_code == 201
    token = _pedir_link(auth_client, email_falso)
    if ponto_de_falha == "gravacao":
        mocker.patch.object(db_session, "commit", side_effect=erro_de_banco())  # passo 7
        cliente = auth_client
    else:
        cliente = make_auth_client(abridor_que_falha())

    resposta = _redefinir(cliente, token)

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": FALHA_REDEFINICAO}
    assert sem_detalhe_tecnico(resposta)
    mocker.stopall()
    db_session.expire_all()
    assert security.senha_confere(SENHA, db_session.query(Usuario).one().senha_hash)  # senha anterior mantida
    assert db_session.query(TokenRecuperacao).one().invalidado_em is None  # e o token continua válido


# ---------------------------------------------------------------- CU02-C4: encerrar sessão

def test_cu02_c4_fluxo_principal_encerra_sessao(auth_client, db_session, relogio):
    token = cadastrar_e_entrar(auth_client)
    assert auth_client.get("/api/users/me", headers=cabecalho(token)).status_code == 200

    resposta = auth_client.post("/api/auth/logout", headers=cabecalho(token))

    assert resposta.status_code == 204
    assert db_session.query(Sessao).one().revogada_em == relogio()
    apos_sair = auth_client.get("/api/users/me", headers=cabecalho(token))
    assert apos_sair.status_code == 401  # funcionalidades restritas indisponíveis até um novo login
    assert apos_sair.json() == {"detail": SESSAO_EXPIRADA}
    assert auth_client.post("/api/auth/logout", headers=cabecalho(token)).status_code == 204  # sair de novo não é erro
    assert auth_client.post("/api/auth/logout").status_code == 204  # nem sem token


def test_cu02_c4_fa1_sessao_expirada(auth_client, relogio):
    token = cadastrar_e_entrar(auth_client)

    relogio.avancar(hours=23, minutes=59)
    assert auth_client.get("/api/users/me", headers=cabecalho(token)).status_code == 200

    relogio.avancar(minutes=2)  # passou o limite de 24 h
    resposta = auth_client.get("/api/users/me", headers=cabecalho(token))

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": SESSAO_EXPIRADA}


def test_cu02_c4_token_adulterado_ou_de_outra_chave_e_recusado(auth_client, db_session):
    token = cadastrar_e_entrar(auth_client)
    adulterado = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    sessao = db_session.query(Sessao).one()
    de_outra_chave = security.jwt.encode(
        {"sub": str(sessao.id_usuario), "jti": str(sessao.id_sessao), "exp": int(sessao.expira_em.timestamp())},
        "outra-chave",
        algorithm="HS256",
    )

    for invalido in (adulterado, de_outra_chave):
        assert auth_client.get("/api/users/me", headers=cabecalho(invalido)).status_code == 401


# ---------------------------------------------------------------- infraestrutura de segurança (RNF06)

def test_senha_de_255_caracteres_e_verificada_sem_truncar_em_72_bytes():
    longa = "a" * 254 + "b"
    hash_da_longa = security.gerar_hash_da_senha(longa)

    assert len(hash_da_longa) <= 100  # cabe em usuario.senha_hash
    assert security.senha_confere(longa, hash_da_longa)
    assert not security.senha_confere("a" * 254 + "c", hash_da_longa)  # difere só depois do byte 72
    assert security.senha_confere("Sénha-com-acênto-€", security.gerar_hash_da_senha("Sénha-com-acênto-€"))
