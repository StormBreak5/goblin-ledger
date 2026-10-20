"""
Plano de testes do CU11 – Treinar Modelo, Cenário 03 (consolidar predições diárias): os passos 2 a 6, o FA2, o FA3 e o
registro dos dias (FE1), que não precisam do TensorFlow. Rodam no host, contra um PostgreSQL temporário. O passo 7 (as
previsões), o FA1, o FA4, o FE1 de ponta a ponta e o agendamento estão em tests/modelo/test_cu11_c3_ponta_a_ponta.py.
"""
from datetime import date, datetime, timedelta

from src.ml.configuracao import ConfigModelo
from src.models.modelo import ConsolidacaoDiaria, ModeloPreditivo, PredicaoDiaria, ProjecaoItem
from src.scraper.models import ExecutionStatus, HistoricalItemPrice, ScraperExecutionLog
from src.services.consolidacao_service import ConsolidacaoService

D = date(2026, 9, 27)  # o dia de referência: a véspera da data do relógio falso (28/09/2026)
CFG = ConfigModelo()


def _versao(db_session, relogio, vigente: bool = True) -> int:
    modelo = ModeloPreditivo(
        regiao="US", treinado_em=relogio(), data_inicio=date(2024, 1, 1), corte_validacao=date(2025, 12, 7),
        corte_teste=date(2026, 6, 26), data_fim=date(2026, 9, 1), itens_elegiveis=3, itens_treino=3, itens_avaliados=3,
        amostras_treino=1, amostras_validacao=1, amostras_teste=1, epocas=1, melhor_epoca=1, segundos_por_epoca=1.0,
        duracao_segundos=1.0, caminho_artefatos="v", assinatura_normalizacao="a", vigente=vigente)
    db_session.add(modelo)
    db_session.commit()
    return modelo.versao


def _liberado(db_session, relogio, item_id: int, versao: int, situacao: str = "LIBERADA", motivo=None) -> None:
    db_session.add(ProjecaoItem(serie="3209", item_id=item_id, regiao="US", versao=versao, integra_treino=True,
                                situacao=situacao, motivo=motivo, atualizado_em=relogio()))
    db_session.commit()


def _preco(db_session, item_id: int, dia: date, preco: int, **campos) -> None:
    db_session.add(HistoricalItemPrice(item_id=item_id, region="3209", timestamp=datetime.combine(dia, datetime.min.time()),
                                       price=preco, quantity=100, **{"origem": "UNDERMINE", "granularidade": "DIARIA",
                                                                     **campos}))
    db_session.commit()


def _predicao(db_session, item_id: int, versao: int, data_prevista: date, h: int, previsto: int,
              erro=None) -> PredicaoDiaria:
    predicao = PredicaoDiaria(data_previsao=data_prevista - timedelta(days=h), serie="3209", item_id=item_id,
                              versao=versao, h=h, data_prevista=data_prevista, preco_previsto=previsto,
                              erro_pct=erro, preco_real=None if erro is None else 1)
    db_session.add(predicao)
    db_session.commit()
    return predicao


def test_cu11_c3_fluxo_principal_registra_snapshot_rn13(db_session, relogio):
    """Passos 3 a 6: cada predição feita para o dia encerrado (de D−7 a D−1, uma por horizonte, inclusive as de uma
    versão anterior do modelo) recebe o preço diário consolidado do item e o erro |previsto − real| ÷ real."""
    vigente, antiga = _versao(db_session, relogio), _versao(db_session, relogio, vigente=False)
    _liberado(db_session, relogio, 1, vigente)
    _preco(db_session, 1, D, 100_000)
    db_session.add(HistoricalItemPrice(item_id=1, region="3209", timestamp=datetime(2026, 9, 27, 12, 52), price=120_000,
                                       quantity=100, origem="BLIZZARD", granularidade="HORARIA"))
    db_session.commit()  # o ciclo da Blizzard (1º quartil, RN06) não entra no snapshot
    predicoes = [_predicao(db_session, 1, vigente, D, h, previsto) for h, previsto in ((1, 110_000), (2, 90_000),
                                                                                         (7, 100_000))]
    predicoes.append(_predicao(db_session, 1, antiga, D, 3, 200_000))
    servico = ConsolidacaoService(db_session, CFG, relogio)

    assert servico.dias_pendentes("US", D) == [D]  # nenhuma consolidação ainda: só o dia de referência
    servico.registrar("US", D - timedelta(days=2), "FALHA", erro="queda")
    assert servico.dias_pendentes("US", D) == [D - timedelta(days=2), D - timedelta(days=1), D]  # desde a falha
    db_session.rollback()
    do_dia, preenchidas, nd = servico.preencher_valores_reais("US", D)
    servico.registrar("US", D, "SUCESSO", predicoes_do_dia=do_dia, predicoes_preenchidas=preenchidas, predicoes_nd=nd)
    db_session.commit()

    assert (do_dia, preenchidas, nd) == (4, 4, 0)
    db_session.expire_all()
    snapshot = [(p.h, p.versao, p.preco_real, round(p.erro_pct, 6)) for p in predicoes]
    assert snapshot == [(1, vigente, 100_000, 0.1), (2, vigente, 100_000, 0.1), (7, vigente, 100_000, 0.0),
                        (3, antiga, 100_000, 1.0)]
    assert all(p.consolidado_em == relogio() for p in predicoes)
    registro = db_session.query(ConsolidacaoDiaria).one()
    assert (registro.regiao, registro.dia, registro.status) == ("US", D, "SUCESSO")
    assert servico.dias_pendentes("US", D + timedelta(days=3)) == [D + timedelta(days=k) for k in (1, 2, 3)]  # FE1


def test_cu11_c3_fa2_valor_real_indisponivel(db_session, relogio):
    """FA2: sem o preço diário consolidado do item no dia (ou só com o volume marcado como anômalo, RN12), o snapshot
    fica sem o valor real e sem o erro, "N/D", e o dia conta como consolidado."""
    vigente = _versao(db_session, relogio)
    for item_id in (1, 2, 3):
        _liberado(db_session, relogio, item_id, vigente)
    _preco(db_session, 1, D, 100_000)
    _preco(db_session, 2, D, 50_000, anomalia=True)
    _preco(db_session, 3, D - timedelta(days=1), 70_000)  # só do dia anterior
    predicoes = [_predicao(db_session, item_id, vigente, D, 1, 100_000) for item_id in (1, 2, 3)]

    do_dia, preenchidas, nd = ConsolidacaoService(db_session, CFG, relogio).preencher_valores_reais("US", D)
    db_session.commit()

    assert (do_dia, preenchidas, nd) == (3, 1, 2)
    db_session.expire_all()
    assert [(p.item_id, p.preco_real, p.erro_pct) for p in predicoes] == [(1, 100_000, 0.0), (2, None, None),
                                                                          (3, None, None)]
    assert all(p.consolidado_em is not None for p in predicoes)  # "N/D", e não "ainda não consolidado"


def test_cu11_c3_fa3_degradacao_bloqueia_item_rn13(db_session, relogio):
    """FA3 (RN13): a mediana do erro do item nos últimos 7 dias, em todos os horizontes, acima do limiar da RN10 (15%)
    bloqueia a projeção por "degradação" até o próximo retreinamento."""
    vigente = _versao(db_session, relogio)
    for item_id in (1, 2):
        _liberado(db_session, relogio, item_id, vigente)
    for k in range(7):  # 14 erros de cada item, de D−6 a D, em dois horizontes
        for h in (1, 4):
            _predicao(db_session, 1, vigente, D - timedelta(days=k), h, 1, erro=0.30)
            _predicao(db_session, 2, vigente, D - timedelta(days=k), h, 1, erro=0.10)

    bloqueados = ConsolidacaoService(db_session, CFG, relogio).aplicar_degradacao("US", D)
    db_session.commit()

    assert bloqueados == [("3209", 1)]
    db_session.expire_all()
    situacao = {p.item_id: (p.situacao, p.motivo) for p in db_session.query(ProjecaoItem)}
    assert situacao == {1: ("BLOQUEADA", "degradação"), 2: ("LIBERADA", None)}


def test_rn13_degradacao_exige_minimo_de_erros(db_session, relogio):
    """Um único dia ruim não bloqueia: a regra só vale com ao menos MODELO_DEGRADACAO_MINIMO_ALVOS (14) erros avaliados
    nos últimos 7 dias. Erros fora da janela e de outra versão do modelo não contam."""
    vigente, antiga = _versao(db_session, relogio), _versao(db_session, relogio, vigente=False)
    _liberado(db_session, relogio, 1, vigente)
    for h in range(1, 8):
        _predicao(db_session, 1, vigente, D, h, 1, erro=0.50)
        _predicao(db_session, 1, vigente, D - timedelta(days=1), h, 1, erro=0.50)
    _predicao(db_session, 1, vigente, D - timedelta(days=2), 1, 1, erro=None)  # "N/D": não conta
    for h in range(1, 8):
        _predicao(db_session, 1, vigente, D - timedelta(days=7), h, 1, erro=0.90)  # fora da janela
        _predicao(db_session, 1, antiga, D - timedelta(days=3), h, 1, erro=0.90)  # de outra versão
    db_session.query(PredicaoDiaria).filter(PredicaoDiaria.data_prevista == D, PredicaoDiaria.h == 7).delete()
    db_session.commit()  # 13 erros da versão vigente na janela
    servico = ConsolidacaoService(db_session, CFG, relogio)

    assert servico.aplicar_degradacao("US", D) == []

    _predicao(db_session, 1, vigente, D, 7, 1, erro=0.50)  # o 14º
    assert servico.aplicar_degradacao("US", D) == [("3209", 1)]


def test_cu11_c3_espera_a_importacao_diaria(db_session, relogio):
    """Passo 2: a consolidação não importa nada; usa a importação diária do worker. Em andamento, espera ela terminar
    (até o limite); se ela falhou, não rodou ou passou do limite, segue com um aviso, e os valores reais que faltarem
    ficam "N/D"."""
    servico = ConsolidacaoService(db_session, CFG, relogio)
    log = ScraperExecutionLog(execution_start=relogio().replace(tzinfo=None) - timedelta(hours=1),
                              status=ExecutionStatus.RUNNING, triggered_by="DIARIA", region="3209")
    db_session.add(log)
    db_session.commit()
    esperas: list[float] = []

    def dormir(segundos: float) -> None:
        esperas.append(segundos)
        relogio.avancar(seconds=segundos)
        if len(esperas) == 2:  # a importação termina durante a espera
            db_session.query(ScraperExecutionLog).update({"status": ExecutionStatus.SUCCESS})
            db_session.commit()

    concluida = servico.aguardar_importacao_diaria(limite_minutos=60, dormir=dormir)
    assert (concluida.situacao, concluida.aviso, len(esperas)) == ("CONCLUIDA", None, 2)

    db_session.query(ScraperExecutionLog).update({"status": ExecutionStatus.RUNNING})
    db_session.commit()
    estourou = servico.aguardar_importacao_diaria(limite_minutos=5, dormir=lambda s: relogio.avancar(seconds=s))
    assert estourou.situacao == "EM_ANDAMENTO" and "N/D" in estourou.aviso

    db_session.query(ScraperExecutionLog).update({"status": ExecutionStatus.FAILED})
    db_session.commit()
    falhou = servico.aguardar_importacao_diaria(limite_minutos=60, dormir=lambda s: (_ for _ in ()).throw(AssertionError))
    assert falhou.situacao == "FALHA" and "falhou" in falhou.aviso

    db_session.query(ScraperExecutionLog).delete()
    db_session.commit()
    nao_rodou = servico.aguardar_importacao_diaria(limite_minutos=1, dormir=lambda s: relogio.avancar(seconds=s))
    assert nao_rodou.situacao == "NAO_RODOU" and "não rodou" in nao_rodou.aviso
    desligada = servico.aguardar_importacao_diaria(desligada=True, dormir=lambda s: (_ for _ in ()).throw(AssertionError))
    assert desligada.situacao == "NAO_RODOU"
