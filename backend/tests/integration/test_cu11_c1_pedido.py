"""
Plano de testes do CU11 – Treinar Modelo, Cenário 01 (executar treinamento inicial): o pedido do Admin, a fila e o
resumo. Estes testes rodam no host, sem TensorFlow. Os passos 2 a 12 (seleção, treino, avaliação e RN10) estão em
tests/modelo/, que roda no serviço `modelo`. Rodam contra um PostgreSQL temporário.
"""
from datetime import date

from helpers_auth import abridor_que_falha, cabecalho, cadastrar_e_entrar
from sqlalchemy import text

from src.models.modelo import ExecucaoTreinamento, ModeloPreditivo
from src.models.usuario import Usuario
from src.services.treinamento_service import TreinamentoService

FA1 = "Nenhum item apto ao treinamento. Verifique a validação da cobertura histórica"
FA2 = "Já existe um treinamento em andamento"
FE1 = "Não foi possível concluir o treinamento do modelo. Verifique o log de execução"
FE2 = "Não foi possível concluir o treinamento no momento. Tente novamente mais tarde"


def _token_de_admin(cliente, db_session) -> str:
    token = cadastrar_e_entrar(cliente)
    db_session.query(Usuario).update({"role": "admin"})  # o papel é lido a cada requisição
    db_session.commit()
    return token


def _solicitar(cliente, token, regiao="US"):
    return cliente.post("/api/admin/model-training", json={"regiao": regiao}, headers=cabecalho(token))


def test_cu11_c1_passo1_registra_o_pedido_do_admin(admin_client, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _solicitar(admin_client, token, regiao="us")

    assert resposta.status_code == 202
    corpo = resposta.json()
    assert (corpo["status"], corpo["tipo"], corpo["disparo"], corpo["regiao"]) == ("AGUARDANDO", "INICIAL", "ADMIN", "US")
    assert corpo["mensagem"] is None and corpo["modelo"] is None
    execucao = db_session.get(ExecucaoTreinamento, corpo["id_execucao"])
    assert execucao.status == "AGUARDANDO"  # o serviço `modelo` o retira da fila


def test_cu11_c1_fa2_treinamento_em_andamento(admin_client, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    primeiro = _solicitar(admin_client, token).json()["id_execucao"]

    repetido = _solicitar(admin_client, token)

    assert repetido.status_code == 409 and repetido.json()["detail"] == FA2
    assert db_session.query(ExecucaoTreinamento).count() == 1

    # Um treinamento parado além do prazo (o processo caiu) deixa de bloquear e é encerrado como falha.
    relogio.avancar(hours=7)
    novo = _solicitar(admin_client, token)
    assert novo.status_code == 202
    db_session.expire_all()
    antigo = db_session.get(ExecucaoTreinamento, primeiro)
    assert (antigo.status, antigo.etapa_da_falha) == ("FALHA", "INTERNA")


def test_cu11_c1_fila_entrega_um_treinamento_por_vez(db_session, relogio):
    servico = TreinamentoService(db_session, relogio)
    id_execucao = servico.registrar_pedido("US")

    assert servico.pegar_proximo() == id_execucao
    assert db_session.get(ExecucaoTreinamento, id_execucao).status == "EXECUTANDO"
    assert servico.pegar_proximo() is None  # fila vazia
    db_session.add(ExecucaoTreinamento(tipo="INICIAL", disparo="ADMIN", regiao="US", status="AGUARDANDO",
                                       solicitado_em=relogio()))
    db_session.commit()
    assert servico.pegar_proximo() is None  # outro treinamento já está rodando


def test_cu11_c1_fa2_reinicio_do_servico_libera_a_fila(db_session, relogio):
    """O serviço `modelo` é um só: ao reiniciar, o treinamento que estava em execução parou com ele e não bloqueia mais."""
    servico = TreinamentoService(db_session, relogio)
    interrompido = servico.registrar_pedido("US")
    servico.pegar_proximo()

    assert servico.encerrar_em_execucao() == 1

    db_session.expire_all()
    execucao = db_session.get(ExecucaoTreinamento, interrompido)
    assert (execucao.status, execucao.etapa_da_falha) == ("FALHA", "INTERNA")
    assert servico.resumo(interrompido).mensagem == FE2
    assert servico.registrar_pedido("US") != interrompido  # o FA2 não bloqueia mais


def test_cu11_c1_restrito_ao_admin(admin_client, db_session):
    token = cadastrar_e_entrar(admin_client)  # usuário comum

    pedido = _solicitar(admin_client, token)
    consulta = admin_client.get("/api/admin/model-training", headers=cabecalho(token))

    assert (pedido.status_code, consulta.status_code) == (403, 403)
    assert db_session.query(ExecucaoTreinamento).count() == 0


def test_cu11_c1_regiao_invalida(admin_client, db_session):
    token = _token_de_admin(admin_client, db_session)

    resposta = _solicitar(admin_client, token, regiao="BR")

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Informe uma região válida (US ou EU) com mercados monitorados"
    assert db_session.query(ExecucaoTreinamento).count() == 0


def test_cu11_c1_fe2_banco_indisponivel_no_pedido(make_auth_client, relogio):
    cliente = make_auth_client(abridor_que_falha(), relogio)

    resposta = cliente.post("/api/admin/model-training", json={"regiao": "US"}, headers=cabecalho("qualquer"))

    assert resposta.status_code == 503 and resposta.json()["detail"] == FE2


def test_cu11_c1_resumo_do_treinamento(admin_client, db_session, relogio):
    token = _token_de_admin(admin_client, db_session)
    modelo = ModeloPreditivo(
        regiao="US", treinado_em=relogio(), data_inicio=date(2022, 9, 4), corte_validacao=date(2025, 7, 16),
        corte_teste=date(2026, 5, 11), data_fim=date(2026, 10, 6), itens_elegiveis=10, itens_treino=8,
        itens_avaliados=9, amostras_treino=100, amostras_validacao=30, amostras_teste=15, epocas=40, melhor_epoca=30,
        segundos_por_epoca=30.0, duracao_segundos=1200.0, mediana_mdape=0.2, mediana_mdape_ingenuo=0.24,
        mediana_mape=0.38, mediana_mape_ingenuo=0.47, itens_supera_ingenuo=7, caminho_artefatos="modelos/v1",
        assinatura_normalizacao="a" * 64, vigente=True,
    )
    db_session.add(modelo)
    db_session.flush()
    concluido = ExecucaoTreinamento(
        tipo="INICIAL", disparo="ADMIN", regiao="US", status="SUCESSO", solicitado_em=relogio(), versao=modelo.versao,
        itens_elegiveis=10, itens_treino=8, itens_liberados=3, itens_bloqueados=6, bloqueados_acima_do_limiar=4,
        bloqueados_nao_supera_ingenuo=1, bloqueados_avaliacao_insuficiente=1, itens_ignorados=1,
        liberados_fora_do_treino=1, liberados_sem_amostra_de_treino=2, ultimo_dia=date(2026, 10, 5),
    )
    sem_itens = ExecucaoTreinamento(tipo="INICIAL", disparo="ADMIN", regiao="US", status="FALHA",
                                    solicitado_em=relogio(), etapa_da_falha="SELECAO")
    falha_no_treino = ExecucaoTreinamento(tipo="INICIAL", disparo="ADMIN", regiao="US", status="FALHA",
                                          solicitado_em=relogio(), etapa_da_falha="TREINO", erro="loss NaN")
    db_session.add_all([concluido, sem_itens, falha_no_treino])
    db_session.commit()

    corpo = admin_client.get(f"/api/admin/model-training/{concluido.id}", headers=cabecalho(token)).json()
    assert (corpo["itens_liberados"], corpo["itens_bloqueados"], corpo["itens_ignorados"]) == (3, 6, 1)  # passo 12
    assert corpo["liberados_fora_do_treino"] == 1 and corpo["bloqueados_avaliacao_insuficiente"] == 1
    assert corpo["liberados_sem_amostra_de_treino"] == 2 and corpo["ultimo_dia"] == "2026-10-05"
    assert corpo["modelo"]["versao"] == modelo.versao and corpo["modelo"]["corte_teste"] == "2026-05-11"
    assert corpo["mensagem"] is None

    falhas = {r["id_execucao"]: r["mensagem"] for r in admin_client.get("/api/admin/model-training", headers=cabecalho(token)).json()}
    assert falhas[sem_itens.id] == FA1 and falhas[falha_no_treino.id] == FE1

    inexistente = admin_client.get("/api/admin/model-training/999999", headers=cabecalho(token))
    assert inexistente.status_code == 404 and inexistente.json()["detail"] == "Treinamento não encontrado"


def test_cu11_uma_versao_vigente_por_regiao(db_session, relogio):
    """RN26: o índice parcial impede duas versões vigentes na mesma região."""
    comum = dict(treinado_em=relogio(), data_inicio=date(2022, 9, 4), corte_validacao=date(2025, 7, 16),
                 corte_teste=date(2026, 5, 11), data_fim=date(2026, 10, 6), itens_elegiveis=1, itens_treino=1,
                 itens_avaliados=1, amostras_treino=1, amostras_validacao=1, amostras_teste=1, epocas=1, melhor_epoca=1,
                 segundos_por_epoca=1.0, duracao_segundos=1.0, caminho_artefatos="x", assinatura_normalizacao="a" * 64)
    db_session.add(ModeloPreditivo(regiao="US", vigente=True, **comum))
    db_session.add(ModeloPreditivo(regiao="EU", vigente=True, **comum))
    db_session.commit()
    db_session.add(ModeloPreditivo(regiao="US", vigente=True, **comum))
    try:
        db_session.commit()
        raise AssertionError("duas versões vigentes na mesma região")
    except Exception as e:  # IntegrityError
        db_session.rollback()
        assert "uq_modelo_preditivo_vigente_por_regiao" in str(e)
    assert db_session.execute(text("SELECT count(*) FROM modelo_preditivo WHERE vigente")).scalar() == 2
