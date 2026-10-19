"""
Plano de testes do CU11 – Treinar Modelo, Cenário 02 (retreinar o modelo periodicamente): o passo 1 (o registro do
retreinamento pelo agendador) e o resumo consultado pela tela do Admin. Rodam no host, sem TensorFlow; os passos 2 a 10
estão em tests/modelo/test_cu11_c2_retreinamento.py. Rodam contra um PostgreSQL temporário.
"""
from datetime import date

from helpers_auth import cabecalho, cadastrar_e_entrar

from src.models.modelo import ExecucaoTreinamento, ModeloPreditivo
from src.models.usuario import Usuario
from src.services.treinamento_service import TreinamentoService

FE1 = "Não foi possível concluir o treinamento do modelo. Verifique o log de execução"


def _modelo(db_session, relogio, regiao: str, vigente: bool = True, **campos) -> ModeloPreditivo:
    modelo = ModeloPreditivo(
        regiao=regiao, treinado_em=relogio(), data_inicio=date(2022, 9, 4), corte_validacao=date(2025, 7, 25),
        corte_teste=date(2026, 5, 22), data_fim=date(2026, 10, 19), itens_elegiveis=10, itens_treino=8,
        itens_avaliados=9, amostras_treino=100, amostras_validacao=30, amostras_teste=15, epocas=40, melhor_epoca=30,
        segundos_por_epoca=30.0, duracao_segundos=1200.0, caminho_artefatos="modelos/v1",
        assinatura_normalizacao="a" * 16, vigente=vigente, **campos,
    )
    db_session.add(modelo)
    db_session.commit()
    return modelo


def _execucoes(db_session) -> list[tuple]:
    db_session.expire_all()
    return [(e.tipo, e.disparo, e.regiao, e.status) for e in db_session.query(ExecucaoTreinamento).order_by(
        ExecucaoTreinamento.id)]


def test_cu11_c2_agendador_registra_um_retreinamento_por_regiao_com_modelo_vigente(db_session, relogio):
    _modelo(db_session, relogio, "US")
    _modelo(db_session, relogio, "EU")
    _modelo(db_session, relogio, "EU", vigente=False)  # versão antiga: não conta

    registros = TreinamentoService(db_session, relogio).registrar_retreinamentos()

    assert [(r.regiao, r.motivo) for r in registros] == [("EU", None), ("US", None)]
    assert _execucoes(db_session) == [("RETREINAMENTO", "AGENDADO", "EU", "AGUARDANDO"),
                                      ("RETREINAMENTO", "AGENDADO", "US", "AGUARDANDO")]

    db_session.query(ModeloPreditivo).filter(ModeloPreditivo.regiao == "EU").update({"vigente": False})
    db_session.query(ExecucaoTreinamento).delete()
    db_session.commit()
    registros = TreinamentoService(db_session, relogio).registrar_retreinamentos()
    assert [(r.regiao, r.id_execucao is None, r.motivo) for r in registros] == [
        ("EU", True, "sem modelo vigente"), ("US", False, None)]  # região sem modelo vigente: só o log


def test_cu11_c2_agendador_nao_duplica_execucao_em_andamento(db_session, relogio):
    _modelo(db_session, relogio, "US")
    servico = TreinamentoService(db_session, relogio)
    servico.registrar_retreinamentos(["US"])

    aguardando = servico.registrar_retreinamentos(["US"])
    servico.pegar_proximo()
    executando = servico.registrar_retreinamentos(["us"])

    assert [r.motivo for r in aguardando + executando] == ["já existe uma execução aguardando ou em andamento"] * 2
    assert _execucoes(db_session) == [("RETREINAMENTO", "AGENDADO", "US", "EXECUTANDO")]

    relogio.avancar(hours=7)  # o retreinamento parou com o processo: deixa de bloquear
    assert servico.registrar_retreinamentos(["US"])[0].id_execucao is not None


def test_cu11_c2_resumo_do_retreinamento(admin_client, db_session, relogio):
    """Passo 10: a tela do Admin lista o retreinamento com o tipo, a comparação no mesmo período de teste e a decisão. O
    C2 não tem mensagem ao usuário (o ator é o Sistema): numa falha, só a etapa e o erro do log."""
    token = cadastrar_e_entrar(admin_client)
    db_session.query(Usuario).update({"role": "admin"})
    db_session.commit()
    anterior = _modelo(db_session, relogio, "US", vigente=False)
    descartado = _modelo(db_session, relogio, "US", vigente=False, descartado=True)
    mantido = ExecucaoTreinamento(
        tipo="RETREINAMENTO", disparo="AGENDADO", regiao="US", status="SUCESSO", solicitado_em=relogio(),
        versao=descartado.versao, versao_anterior=anterior.versao, decisao="MANTIDO", mdape_novo=0.21,
        mdape_vigente=0.19, itens_comparados=6400, deixaram_de_ser_elegiveis=12,
        liberados_que_deixaram_de_ser_elegiveis=3, liberados_sem_amostra_de_treino=150, ultimo_dia=date(2026, 10, 19),
        avisos="série diária desatualizada (último dia encerrado: 15/10/2026)",
    )
    falha_do_c2 = ExecucaoTreinamento(tipo="RETREINAMENTO", disparo="AGENDADO", regiao="US", status="FALHA",
                                      solicitado_em=relogio(), etapa_da_falha="TREINO", erro="NaN")
    falha_do_c1 = ExecucaoTreinamento(tipo="INICIAL", disparo="ADMIN", regiao="US", status="FALHA",
                                      solicitado_em=relogio(), etapa_da_falha="TREINO", erro="NaN")
    db_session.add_all([mantido, falha_do_c2, falha_do_c1])
    db_session.commit()

    corpo = admin_client.get(f"/api/admin/model-training/{mantido.id}", headers=cabecalho(token)).json()
    assert (corpo["tipo"], corpo["decisao"], corpo["versao_anterior"]) == ("RETREINAMENTO", "MANTIDO", anterior.versao)
    assert (corpo["mdape_novo"], corpo["mdape_vigente"], corpo["itens_comparados"]) == (0.21, 0.19, 6400)
    assert (corpo["deixaram_de_ser_elegiveis"], corpo["liberados_que_deixaram_de_ser_elegiveis"]) == (12, 3)
    assert corpo["modelo"]["versao"] == descartado.versao and corpo["modelo"]["descartado"] is True
    assert "série diária desatualizada" in corpo["avisos"]

    mensagens = {r["id_execucao"]: r["mensagem"] for r in
                 admin_client.get("/api/admin/model-training", headers=cabecalho(token)).json()}
    assert mensagens[falha_do_c2.id] is None and mensagens[falha_do_c1.id] == FE1


def test_cu11_c2_retreinamento_perdido_com_o_computador_desligado_e_registrado_uma_vez(db_session, relogio):
    """Ao iniciar o serviço `modelo` depois do horário do agendador (computador desligado na terça às 18:00), cada região
    com modelo vigente e sem execução concluída desde aquele disparo recebe o retreinamento, uma vez."""
    from datetime import timedelta

    _modelo(db_session, relogio, "US")
    _modelo(db_session, relogio, "EU")
    disparo_perdido = relogio() - timedelta(days=1)
    db_session.add(ExecucaoTreinamento(tipo="RETREINAMENTO", disparo="AGENDADO", regiao="EU", status="SUCESSO",
                                       solicitado_em=disparo_perdido + timedelta(minutes=1)))  # a EU rodou
    db_session.add(ExecucaoTreinamento(tipo="RETREINAMENTO", disparo="AGENDADO", regiao="US", status="SUCESSO",
                                       solicitado_em=disparo_perdido - timedelta(days=7)))  # a da semana anterior
    db_session.commit()
    servico = TreinamentoService(db_session, relogio)

    registros = servico.registrar_retreinamentos_perdidos(disparo_perdido)

    assert [(r.regiao, r.id_execucao is not None) for r in registros] == [("US", True)]
    assert servico.registrar_retreinamentos_perdidos(disparo_perdido)[0].motivo == \
        "já existe uma execução aguardando ou em andamento"  # reiniciou de novo: não duplica
    assert [e for e in _execucoes(db_session) if e[3] == "AGUARDANDO"] == [
        ("RETREINAMENTO", "AGENDADO", "US", "AGUARDANDO")]
