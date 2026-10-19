"""
Plano de testes do CU11 – Treinar Modelo, Cenário 02 (retreinar o modelo periodicamente), passos 2 a 10: um teste por
fluxo (o registro do agendador, passo 1, também está em tests/integration/test_cu11_c2_agendador.py). Rodam no serviço
`modelo`, contra um PostgreSQL temporário com dados sintéticos de 2024-01-01 a 2026-10-05.

A versão vigente é treinada em 06/09/2026 (série até 05/09) e o retreinamento roda em 06/10/2026 (série até 05/10): 30
dias novos. Um treinador falso guarda no "modelo" o modo de previsão de cada item (perfeita, ingênua ou 50% acima do
preço), para o vigente ser melhor ou pior que o novo de forma controlada. A comparação usa a LSTM mínima de verdade.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pandas")
pytest.importorskip("tensorflow")

import pandas as pd  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from apoio_treino import (CFG, FIM, TreinadorFalso, aptos_do, cenario, executar, pastas, projecoes,  # noqa: E402
                          retreinar)
from sinteticos import gravar_no_banco, serie_constante  # noqa: E402
from src.ml.rede import FalhaNoTreinamento, TreinadorKeras  # noqa: E402
from src.ml.retreinamento import Retreinamento  # noqa: E402
from src.models.modelo import ExecucaoTreinamento, ModeloPreditivo  # noqa: E402

DIA_DO_C1 = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
DIA_DO_C2 = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def vigente_treinado(pg_engine, db_session, relogio, pasta: Path, dados, treinador) -> int:
    """O C1 de 06/09/2026, que deixa a versão vigente para o retreinamento."""
    gravar_no_banco(db_session, dados, aptos_do(dados))
    relogio.agora = DIA_DO_C1
    resumo = executar(pg_engine, db_session, relogio, pasta, treinador)
    assert resumo.status == "SUCESSO", resumo.erro
    relogio.agora = DIA_DO_C2
    return resumo.modelo.versao


def normalizacao_da_versao(db_session, versao: int) -> dict:
    caminho = Path(db_session.get(ModeloPreditivo, versao).caminho_artefatos) / "normalizacao.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_cu11_c2_fluxo_principal_substitui_modelo_rn26(pg_engine, db_session, relogio, tmp_path):
    v1 = vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(), TreinadorFalso(padrao="ruim"))

    resumo = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())  # o novo erra menos

    assert (resumo.status, resumo.tipo, resumo.disparo) == ("SUCESSO", "RETREINAMENTO", "AGENDADO")
    assert resumo.mensagem is None and resumo.decisao == "SUBSTITUIDO"
    assert (resumo.versao_anterior, resumo.itens_comparados) == (v1, 6)
    assert resumo.mdape_novo < resumo.mdape_vigente
    v2 = resumo.modelo.versao
    novo, anterior = db_session.get(ModeloPreditivo, v2), db_session.get(ModeloPreditivo, v1)
    assert novo.vigente and not novo.descartado
    assert not anterior.vigente and anterior.substituido_em is not None  # passo 8
    # Passos 3 e 4: os dados novos entram e a divisão 70/20/10 é recalculada até o último dia encerrado.
    assert resumo.ultimo_dia == date(2026, 10, 5) and novo.data_fim == date(2026, 10, 5)
    assert novo.corte_teste > anterior.corte_teste
    # Passo 9: a situação de todos os elegíveis com o modelo que ficou vigente.
    proj = projecoes(db_session)
    assert {p.versao for p in proj.values()} == {v2}
    assert resumo.itens_liberados + resumo.itens_bloqueados + resumo.itens_ignorados == resumo.itens_elegiveis == 6
    assert resumo.itens_liberados == 6 and resumo.liberados_fora_do_treino == 1
    assert resumo.liberados_sem_amostra_de_treino is not None
    assert pastas(Path(novo.caminho_artefatos)) == {"modelo.keras", "normalizacao.json", "treino.json",
                                                    "avaliacao_teste.parquet", "avaliacao_teste_vigente.parquet"}
    comparacao = json.loads((Path(novo.caminho_artefatos) / "treino.json").read_text(encoding="utf-8"))
    assert comparacao["comparacao_com_o_vigente"]["decisao"] == "SUBSTITUIDO"


def test_cu11_c2_fa1_item_deixou_de_ser_elegivel(pg_engine, db_session, relogio, tmp_path):
    """Um item liberado na versão vigente fica ilíquido (RN02) na última semana: no retreinamento, a projeção dele é
    bloqueada ("deixou de ser elegível") e ele conta entre os liberados que deixaram de ser elegíveis."""
    dados = cenario()
    p = dados["precos"]
    p.loc[(p["item_id"] == 200_002) & (pd.to_datetime(p["data"]) >= pd.Timestamp("2026-09-29")), "quantidade"] = 10
    vigente_treinado(pg_engine, db_session, relogio, tmp_path, dados, TreinadorFalso())
    assert projecoes(db_session)[200_002].situacao == "LIBERADA"
    metricas_antes = projecoes(db_session)[200_002].mdape

    resumo = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())

    item = projecoes(db_session)[200_002]
    assert (item.situacao, item.motivo) == ("BLOQUEADA", "deixou de ser elegível")
    assert item.mdape == metricas_antes  # as métricas da última avaliação ficam no registro
    assert (resumo.deixaram_de_ser_elegiveis, resumo.liberados_que_deixaram_de_ser_elegiveis) == (1, 1)
    assert resumo.itens_elegiveis == 5

    relogio.agora = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    segundo = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())
    assert segundo.deixaram_de_ser_elegiveis == 0  # já estava bloqueado: não conta de novo


def test_cu11_c2_fa2_novo_modelo_inferior_mantem_vigente(pg_engine, db_session, relogio, tmp_path):
    v1 = vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(), TreinadorFalso())

    resumo = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso(padrao="ruim"))

    assert resumo.status == "SUCESSO" and resumo.decisao == "MANTIDO"
    assert resumo.mdape_novo > resumo.mdape_vigente and resumo.versao_anterior == v1
    descartado = db_session.get(ModeloPreditivo, resumo.modelo.versao)
    assert descartado.descartado and not descartado.vigente and resumo.modelo.descartado
    assert descartado.mediana_mdape is not None  # as métricas do novo ficam registradas
    assert pastas(Path(descartado.caminho_artefatos)) >= {"modelo.keras", "normalizacao.json", "treino.json"}
    vigente = db_session.get(ModeloPreditivo, v1)
    assert vigente.vigente and vigente.substituido_em is None
    # Passo 9 com o vigente mantido: a situação é recalculada no período de teste novo, com a versão vigente.
    proj = projecoes(db_session)
    assert {p.versao for p in proj.values()} == {v1}
    assert {p.atualizado_em for p in proj.values()} == {DIA_DO_C2}
    assert resumo.itens_liberados == 6


def test_cu11_c2_fe1_falha_mantem_vigente(pg_engine, db_session, relogio, tmp_path, mocker):
    v1 = vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(), TreinadorFalso())
    situacao = {i: (p.situacao, p.versao, p.atualizado_em) for i, p in projecoes(db_session).items()}

    def mantidos() -> None:
        db_session.expire_all()
        assert [(m.versao, m.vigente) for m in db_session.query(ModeloPreditivo)] == [(v1, True)]
        assert {i: (p.situacao, p.versao, p.atualizado_em) for i, p in projecoes(db_session).items()} == situacao
        assert pastas(tmp_path) == {f"v{v1}"}

    # Passo 5: o treinamento não converge.
    no_treino = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso(erro=FalhaNoTreinamento("NaN")))
    assert (no_treino.status, no_treino.etapa_da_falha) == ("FALHA", "TREINO")
    assert no_treino.mensagem is None and "NaN" in no_treino.erro  # o C2 só registra a falha em log
    mantidos()

    # Passo 8: a gravação falha depois de o modelo novo ter sido inserido.
    queda = OperationalError("UPDATE ...", {}, Exception("server closed the connection unexpectedly"))
    mocker.patch.object(Retreinamento, "_gravar_situacao_do_retreino", side_effect=queda)
    no_banco = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())
    assert (no_banco.status, no_banco.etapa_da_falha, no_banco.modelo) == ("FALHA", "BANCO", None)
    mantidos()


class TreinadorKerasQueAnota(TreinadorKeras):
    """A LSTM de verdade, anotando a normalização e as amostras de cada previsão."""

    def __init__(self) -> None:
        self.previsoes: list[dict] = []

    def prever(self, modelo, dados, jan):  # type: ignore[no-untyped-def]
        self.previsoes.append({"normalizacao": dados.normalizacao,
                               "janelas": jan[["id_amostra", "serie", "item_id", "data_origem"]].copy()})
        return super().prever(modelo, dados, jan)


def test_cu11_c2_compara_os_dois_modelos_no_mesmo_periodo_com_as_constantes_de_cada_versao(
        pg_engine, db_session, relogio, tmp_path, mocker):
    """Passos 6 e 7 (RN26): o vigente (rede de verdade, carregada do modelo.keras) é avaliado nas mesmas amostras de
    teste do novo, com as constantes, o vocabulário e a escala do alvo da própria versão sobre as datas de corte novas.
    A base é lida uma vez só."""
    from src.ml import treinamento_inicial

    v1 = vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(), TreinadorKeras())
    leituras = mocker.spy(treinamento_inicial, "carregar_banco")
    treinador = TreinadorKerasQueAnota()

    resumo = retreinar(pg_engine, db_session, relogio, tmp_path, treinador)

    assert resumo.status == "SUCESSO", resumo.erro
    assert leituras.call_count == 1
    do_novo, do_vigente = treinador.previsoes
    norm_v1, norm_v2 = normalizacao_da_versao(db_session, v1), normalizacao_da_versao(db_session, resumo.modelo.versao)
    for chave in ("constantes", "vocabulario", "nivel_item", "alvo"):
        assert do_vigente["normalizacao"][chave] == norm_v1[chave]
        assert do_novo["normalizacao"][chave] == norm_v2[chave]
    assert do_vigente["normalizacao"]["cortes"] == norm_v2["cortes"] != norm_v1["cortes"]  # os cortes novos
    pd.testing.assert_frame_equal(do_novo["janelas"].reset_index(drop=True),
                                  do_vigente["janelas"].reset_index(drop=True))  # as mesmas amostras
    assert resumo.itens_comparados == 6
    assert (resumo.mdape_novo < resumo.mdape_vigente) == (resumo.decisao == "SUBSTITUIDO")


def test_cu11_c2_item_novo_liberado_ao_atingir_o_minimo_de_dias(pg_engine, db_session, relogio, tmp_path):
    """Item lançado em 25/06/2026: no C1 (série até 05/09) tem só uns 7 dias avaliados (FA5); no retreinamento, com 30
    dias a mais, passa dos 30 dias avaliados e é liberado (RN10)."""
    novo = serie_constante(300_005, "2026-06-25", FIM, ruido=0.03, semente=5)
    vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(novo), TreinadorFalso())
    antes = projecoes(db_session)[300_005]
    assert (antes.situacao, antes.motivo) == ("BLOQUEADA", "avaliação insuficiente") and antes.dias_avaliados < 30

    retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())

    depois = projecoes(db_session)[300_005]
    assert depois.situacao == "LIBERADA" and depois.dias_avaliados >= 30


def test_cu11_c2_aviso_de_serie_diaria_desatualizada(pg_engine, db_session, relogio, tmp_path):
    """O último dia encerrado da série (05/10) tem mais de 3 dias em 10/10: o resumo avisa, mas o retreinamento roda."""
    vigente_treinado(pg_engine, db_session, relogio, tmp_path, cenario(), TreinadorFalso())
    relogio.agora = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    resumo = retreinar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())

    assert resumo.status == "SUCESSO"
    assert "série diária desatualizada (último dia encerrado: 05/10/2026)" in resumo.avisos

    relogio.agora = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)  # 3 dias: ainda não
    assert "série diária desatualizada" not in (retreinar(pg_engine, db_session, relogio, tmp_path,
                                                          TreinadorFalso()).avisos or "")


def test_cu11_c2_agendador_usa_o_horario_configurado(monkeypatch):
    """Passo 1: terça-feira às 18:00 UTC, depois do reinício semanal dos EUA (MODELO_RETREINO_CRON; "off" desliga)."""
    from src import modelo_worker

    agora = datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc)  # segunda-feira
    monkeypatch.delenv("MODELO_RETREINO_CRON", raising=False)
    agendador = MagicMock()
    assert modelo_worker.agendar_retreinamento(agendador, MagicMock())
    gatilho = agendador.add_job.call_args.args[1]
    assert gatilho.get_next_fire_time(None, agora) == datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)

    monkeypatch.setenv("MODELO_RETREINO_CRON", "0 6 * * mon")
    agendador = MagicMock()
    modelo_worker.agendar_retreinamento(agendador, MagicMock())
    assert agendador.add_job.call_args.args[1].get_next_fire_time(None, agora) == \
        datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)

    monkeypatch.setenv("MODELO_RETREINO_CRON", "off")
    agendador = MagicMock()
    assert not modelo_worker.agendar_retreinamento(agendador, MagicMock())
    agendador.add_job.assert_not_called()


def test_cu11_c2_comando_retreinar_registra_pelo_mesmo_caminho(pg_engine, db_session, mocker, capsys):
    """`python -m src.modelo_worker --retreinar US` registra o retreinamento como o agendador (e o C3-FA4 o usará)."""
    from src import modelo_worker

    db_session.add(ModeloPreditivo(
        regiao="US", treinado_em=DIA_DO_C1, data_inicio=date(2024, 1, 1), corte_validacao=date(2025, 12, 7),
        corte_teste=date(2026, 6, 26), data_fim=date(2026, 10, 5), itens_elegiveis=1, itens_treino=1,
        itens_avaliados=1, amostras_treino=1, amostras_validacao=1, amostras_teste=1, epocas=1, melhor_epoca=1,
        segundos_por_epoca=1.0, duracao_segundos=1.0, caminho_artefatos="v1", assinatura_normalizacao="a",
        vigente=True))
    db_session.commit()
    mocker.patch.object(modelo_worker, "init_db", return_value=sessionmaker(bind=pg_engine))

    assert modelo_worker.main(["--retreinar", "US"]) == 0
    assert modelo_worker.main(["--retreinar"]) == 0  # todas: US já está na fila e EU não tem modelo vigente

    saida = capsys.readouterr().out
    assert "US: retreinamento" in saida and "registrado na fila" in saida
    assert "EU: não registrado (sem modelo vigente)" in saida
    assert "US: não registrado (já existe uma execução aguardando ou em andamento)" in saida
    execucoes = db_session.query(ExecucaoTreinamento).all()
    assert [(e.tipo, e.disparo, e.regiao, e.status) for e in execucoes] == [
        ("RETREINAMENTO", "AGENDADO", "US", "AGUARDANDO")]
