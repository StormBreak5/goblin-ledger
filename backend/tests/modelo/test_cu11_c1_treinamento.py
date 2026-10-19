"""
Plano de testes do CU11 – Treinar Modelo, Cenário 01 (executar treinamento inicial), passos 2 a 12: um teste por fluxo
(o passo 1 e o FA2 estão em tests/integration/test_cu11_c1_pedido.py). Rodam no serviço `modelo`, contra um
PostgreSQL temporário com dados sintéticos. O fluxo principal treina uma LSTM mínima de verdade (4 unidades, 1 época);
os demais usam um treinador falso, que controla as previsões de cada item.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import pytest

pytest.importorskip("pandas")
pytest.importorskip("tensorflow")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from sinteticos import gerar, gravar_no_banco, serie_constante  # noqa: E402
from src.ml.configuracao import ConfigModelo  # noqa: E402
from src.ml.dataset import DadosPreparados  # noqa: E402
from src.ml.rede import FalhaNoTreinamento, ResultadoDoTreino, TreinadorKeras  # noqa: E402
from src.ml.treinamento_inicial import TreinamentoInicial  # noqa: E402
from src.models.modelo import ExecucaoTreinamento, ModeloPreditivo, ProjecaoItem  # noqa: E402
from src.services.treinamento_service import ResumoDoTreinamento, TreinamentoService  # noqa: E402

FA1 = "Nenhum item apto ao treinamento. Verifique a validação da cobertura histórica"
FE1 = "Não foi possível concluir o treinamento do modelo. Verifique o log de execução"
FE2 = "Não foi possível concluir o treinamento no momento. Tente novamente mais tarde"

CFG = ConfigModelo(unidades=4, epocas_max=1, paciencia=1, lote=64, amostras_por_epoca=256, amostras_validacao=256)
FIM = "2026-10-05"
FORA_DO_TREINO = 200_003  # elegível, mas não apto ao treinamento (RN15)


def cenario(*extras: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """6 itens sintéticos de 2024-01-01 a 2026-10-05, todos líquidos (RN02); o 200003 não é apto (RN15)."""
    dados = gerar(n_itens=6, inicio="2024-01-01", fim=FIM, semente=5)
    dados["precos"]["quantidade"] = dados["precos"]["quantidade"].clip(lower=100)
    if extras:
        dados["precos"] = pd.concat([dados["precos"], *extras], ignore_index=True)
    return dados


def aptos_do(dados: dict[str, pd.DataFrame]) -> set[int]:
    return set(dados["precos"]["item_id"].astype(int)) - {FORA_DO_TREINO}


class TreinadorFalso:
    """Sem rede: devolve, para cada item, a previsão pedida em `modos` ("perfeita", "ingenua" ou "ruim", 50% acima)."""

    def __init__(self, modos: Optional[dict[int, str]] = None, padrao: str = "perfeita",
                 erro: Optional[BaseException] = None) -> None:
        self.modos = modos or {}
        self.padrao = padrao
        self.erro = erro
        self.itens_do_treino: set[int] = set()
        self.treinou = False

    def treinar(self, dados: DadosPreparados, jan_treino: pd.DataFrame, jan_validacao: pd.DataFrame,
                cfg: ConfigModelo, ao_fim_da_epoca: Any = None) -> ResultadoDoTreino:
        self.treinou = True
        if self.erro is not None:
            raise self.erro
        self.itens_do_treino = set(jan_treino["item_id"]) | set(jan_validacao["item_id"])
        if ao_fim_da_epoca is not None:
            ao_fim_da_epoca(1, cfg.epocas_max, 0.5)
        return ResultadoDoTreino(modelo="falso", epocas=1, melhor_epoca=1, melhor_val_loss=0.5, duracao_segundos=0.1,
                                 segundos_por_epoca=0.1, amostras_treino=len(jan_treino),
                                 amostras_validacao=len(jan_validacao), amostras_parada_antecipada=len(jan_validacao))

    def prever(self, modelo: Any, dados: DadosPreparados, jan: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        alvo = dados.normalizacao["alvo"]
        media, desvio = np.asarray(alvo["media"]), np.asarray(alvo["desvio"])
        yhat = jan[dados.colunas_alvo()].to_numpy("float64")
        modos = jan["item_id"].map(lambda i: self.modos.get(int(i), self.padrao)).to_numpy()
        yhat[modos == "ingenua"] = (0.0 - media) / desvio
        yhat[modos == "ruim"] = (np.log(1.5) - media) / desvio
        return jan["id_amostra"].to_numpy(), yhat

    def salvar(self, modelo: Any, caminho: Path) -> None:
        caminho.write_text("modelo falso", encoding="utf-8")


class TreinadorKerasComPrevisaoPerfeita(TreinadorKeras):
    """Treina a LSTM de verdade e grava o modelo.keras, mas a avaliação usa o próprio alvo, para o teste saber quais
    itens são liberados (a rede mínima de 1 época não atinge a RN10)."""

    def __init__(self) -> None:
        self.itens_do_treino: set[int] = set()

    def treinar(self, dados, jan_treino, jan_validacao, cfg, ao_fim_da_epoca=None):  # type: ignore[no-untyped-def]
        self.itens_do_treino = set(jan_treino["item_id"]) | set(jan_validacao["item_id"])
        return super().treinar(dados, jan_treino, jan_validacao, cfg, ao_fim_da_epoca)

    def prever(self, modelo, dados, jan):  # type: ignore[no-untyped-def]
        self.previsao_real = super().prever(modelo, dados, jan)
        return jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64")


def executar(pg_engine, db_session, relogio, pasta: Path, treinador: Any,
             cfg: ConfigModelo = CFG) -> ResumoDoTreinamento:
    servico = TreinamentoService(db_session, relogio)
    id_execucao = servico.registrar_pedido("US")
    assert servico.pegar_proximo() == id_execucao
    TreinamentoInicial(pg_engine, cfg, pasta, treinador, relogio).executar(id_execucao)
    db_session.expire_all()
    return servico.resumo(id_execucao)


def projecoes(db_session) -> dict[int, ProjecaoItem]:
    return {p.item_id: p for p in db_session.query(ProjecaoItem)}


def pastas(pasta: Path) -> set[str]:
    return {p.name for p in pasta.iterdir()} if pasta.exists() else set()


def test_cu11_c1_fluxo_principal_treina_e_libera_itens(pg_engine, db_session, relogio, tmp_path):
    dados = cenario()
    gravar_no_banco(db_session, dados, aptos_do(dados))
    treinador = TreinadorKerasComPrevisaoPerfeita()

    resumo = executar(pg_engine, db_session, relogio, tmp_path, treinador)

    # Passo 12: o resumo, com liberados, bloqueados e ignorados.
    assert (resumo.status, resumo.mensagem, resumo.etapa_da_falha) == ("SUCESSO", None, None)
    assert (resumo.itens_elegiveis, resumo.itens_treino) == (6, 5)
    assert resumo.itens_liberados + resumo.itens_bloqueados + resumo.itens_ignorados == 6
    assert resumo.itens_liberados >= 5 and resumo.liberados_fora_do_treino == 1
    assert resumo.andamento == "Concluído" and "RN07 desligada" in resumo.avisos

    # Passos 2, 8 e 9: o item fora do conjunto de treinamento não treina, mas é avaliado e pode ser liberado.
    assert FORA_DO_TREINO not in treinador.itens_do_treino and len(treinador.itens_do_treino) == 5
    proj = projecoes(db_session)
    assert set(proj) == set(dados["precos"]["item_id"])
    fora = proj[FORA_DO_TREINO]
    assert not fora.integra_treino and fora.situacao == "LIBERADA" and fora.dias_avaliados >= 30
    assert fora.mdape < fora.mdape_ingenuo and fora.mdape <= 0.15 and fora.mape is not None

    # Passo 11: a versão vigente, com as datas de corte (RN25), as métricas e os artefatos.
    modelo = db_session.get(ModeloPreditivo, resumo.modelo.versao)
    assert modelo.vigente and modelo.regiao == "US" and modelo.id_execucao == resumo.id_execucao
    assert modelo.data_inicio < modelo.corte_validacao < modelo.corte_teste <= modelo.data_fim
    assert modelo.epocas == 1 and modelo.amostras_teste > 0 and modelo.itens_avaliados == 6
    assert modelo.mediana_mdape < modelo.mediana_mdape_ingenuo
    destino = Path(modelo.caminho_artefatos)
    assert destino == tmp_path / f"v{modelo.versao}"
    assert pastas(destino) == {"modelo.keras", "normalizacao.json", "treino.json", "avaliacao_teste.parquet"}
    assert pastas(tmp_path) == {destino.name}
    assert all(p.versao == modelo.versao for p in proj.values())

    # A rede gravada carrega e prevê; a previsão de verdade tem o formato do horizonte e é finita.
    import keras
    keras.models.load_model(destino / "modelo.keras", compile=False)
    _, yhat = treinador.previsao_real
    assert yhat.shape == (modelo.amostras_teste, 7) and np.isfinite(yhat).all()


def test_cu11_c1_fa1_nenhum_item_apto(pg_engine, db_session, relogio, tmp_path):
    gravar_no_banco(db_session, cenario(), aptos=set())  # a validação da cobertura (CU10-C3) não aprovou nenhum item
    treinador = TreinadorFalso()

    resumo = executar(pg_engine, db_session, relogio, tmp_path, treinador)

    assert (resumo.status, resumo.etapa_da_falha, resumo.mensagem) == ("FALHA", "SELECAO", FA1)
    assert (resumo.itens_elegiveis, resumo.itens_treino) == (6, 0)
    assert not treinador.treinou
    assert db_session.query(ModeloPreditivo).count() == 0 and db_session.query(ProjecaoItem).count() == 0
    assert pastas(tmp_path) == set()


def test_cu11_c1_fa3_serie_insuficiente_item_ignorado(pg_engine, db_session, relogio, tmp_path):
    # Registros a cada 6 dias: o preenchimento de até 3 dias (RN24) não fecha as lacunas, e não há 30 dias seguidos
    # para compor uma amostra, embora o item tenha liquidez (RN02) e 200 dias de histórico (RN27).
    esparso = serie_constante(300_001, "2026-03-20", FIM, a_cada=6)
    dados = cenario(esparso)
    gravar_no_banco(db_session, dados, aptos_do(dados))
    treinador = TreinadorFalso()

    resumo = executar(pg_engine, db_session, relogio, tmp_path, treinador)

    assert resumo.status == "SUCESSO" and resumo.itens_elegiveis == 7
    assert resumo.itens_ignorados == 1
    ignorado = projecoes(db_session)[300_001]
    assert (ignorado.situacao, ignorado.motivo) == ("IGNORADA", "série insuficiente")
    assert ignorado.integra_treino and ignorado.mdape is None and ignorado.dias_avaliados is None
    assert 300_001 not in treinador.itens_do_treino  # fora do treino e da avaliação


def test_cu11_c1_fa4_projecao_reprovada_rn10(pg_engine, db_session, relogio, tmp_path):
    estavel = serie_constante(300_002, "2024-01-01", FIM, ruido=0.002, semente=1)  # o ingênuo erra ~0,2%
    dados = cenario(estavel)
    gravar_no_banco(db_session, dados, aptos_do(dados))
    treinador = TreinadorFalso(modos={300_002: "ingenua", 200_001: "ruim"})

    resumo = executar(pg_engine, db_session, relogio, tmp_path, treinador)

    assert resumo.status == "SUCESSO"
    proj = projecoes(db_session)
    empata = proj[300_002]  # no limiar, mas igual ao ingênuo
    assert (empata.situacao, empata.motivo) == ("BLOQUEADA", "não supera o ingênuo")
    assert empata.mdape <= 0.15 and empata.mdape == pytest.approx(empata.mdape_ingenuo)
    ruim = proj[200_001]  # previsões 50% acima do preço
    assert (ruim.situacao, ruim.motivo) == ("BLOQUEADA", "acima do limiar") and ruim.mdape > 0.15
    assert ruim.dias_avaliados >= 30 and ruim.mape is not None and ruim.rmse_cobre > 0  # as métricas ficam registradas
    assert resumo.bloqueados_nao_supera_ingenuo == 1 and resumo.bloqueados_acima_do_limiar == 1
    assert resumo.itens_liberados == 5 and resumo.itens_bloqueados == 2


def test_cu11_c1_fa5_avaliacao_insuficiente_rn10(pg_engine, db_session, relogio, tmp_path):
    # Item lançado há 90 dias: tem o histórico mínimo (RN27), mas só uns 25 dias de previsões avaliadas no teste.
    novo = serie_constante(300_003, "2026-07-08", FIM, ruido=0.03, semente=2)
    dados = cenario(novo)
    gravar_no_banco(db_session, dados, aptos_do(dados))

    resumo = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())  # previsões perfeitas

    assert resumo.status == "SUCESSO" and resumo.bloqueados_avaliacao_insuficiente == 1
    item = projecoes(db_session)[300_003]
    assert (item.situacao, item.motivo) == ("BLOQUEADA", "avaliação insuficiente")
    assert 0 < item.dias_avaliados < 30 and item.mdape < item.mdape_ingenuo  # seria liberado com 30 dias


def _primeira_versao(pg_engine, db_session, relogio, pasta: Path) -> tuple[int, dict[int, tuple[str, int]]]:
    """Um treinamento concluído antes da falha: os registros que precisam continuar como estavam."""
    dados = cenario()
    gravar_no_banco(db_session, dados, aptos_do(dados))
    resumo = executar(pg_engine, db_session, relogio, pasta, TreinadorFalso())
    assert resumo.status == "SUCESSO"
    return resumo.modelo.versao, {i: (p.situacao, p.versao) for i, p in projecoes(db_session).items()}


def _registros_mantidos(db_session, versao: int, situacao: dict[int, tuple[str, int]], pasta: Path) -> None:
    modelos = db_session.query(ModeloPreditivo).all()
    assert [(m.versao, m.vigente) for m in modelos] == [(versao, True)]
    assert {i: (p.situacao, p.versao) for i, p in projecoes(db_session).items()} == situacao
    assert pastas(pasta) == {f"v{versao}"}  # o modelo em treinamento foi descartado


def test_cu11_c1_fe1_falha_no_treinamento(pg_engine, db_session, relogio, tmp_path):
    versao, situacao = _primeira_versao(pg_engine, db_session, relogio, tmp_path)

    # O treino não converge: com uma taxa de aprendizado absurda, a perda deixa de ser finita (TerminateOnNaN).
    divergente = executar(pg_engine, db_session, relogio, tmp_path, TreinadorKeras(),
                          replace(CFG, taxa_aprendizado=1e30, amostras_por_epoca=2048))
    assert (divergente.status, divergente.etapa_da_falha, divergente.mensagem) == ("FALHA", "TREINO", FE1)
    assert "NaN" in divergente.erro
    _registros_mantidos(db_session, versao, situacao, tmp_path)

    # Esgotamento de recursos.
    sem_memoria = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso(erro=MemoryError()))
    assert (sem_memoria.status, sem_memoria.etapa_da_falha, sem_memoria.mensagem) == ("FALHA", "TREINO", FE1)
    _registros_mantidos(db_session, versao, situacao, tmp_path)

    falha = TreinadorFalso(erro=FalhaNoTreinamento("ResourceExhaustedError: OOM"))
    assert executar(pg_engine, db_session, relogio, tmp_path, falha).mensagem == FE1


def test_cu11_c1_fe2_falha_no_banco(pg_engine, db_session, relogio, tmp_path, mocker):
    versao, situacao = _primeira_versao(pg_engine, db_session, relogio, tmp_path)
    queda = OperationalError("SELECT ...", {}, Exception("server closed the connection unexpectedly"))

    # Passo 3: a leitura da série histórica falha.
    leitura = mocker.patch("src.ml.treinamento_inicial.carregar_banco", side_effect=queda)
    no_passo_3 = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())
    assert (no_passo_3.status, no_passo_3.etapa_da_falha, no_passo_3.mensagem) == ("FALHA", "BANCO", FE2)
    assert "server closed" in no_passo_3.erro
    _registros_mantidos(db_session, versao, situacao, tmp_path)
    assert leitura.called
    mocker.stopall()

    # Passo 11: a gravação da situação dos itens falha depois de a versão nova ter sido inserida: nada é mantido dela.
    mocker.patch.object(TreinamentoInicial, "_gravar_situacao", side_effect=queda)
    no_passo_11 = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())
    assert (no_passo_11.status, no_passo_11.etapa_da_falha, no_passo_11.mensagem) == ("FALHA", "BANCO", FE2)
    assert no_passo_11.modelo is None
    _registros_mantidos(db_session, versao, situacao, tmp_path)
    assert db_session.query(ExecucaoTreinamento).filter(ExecucaoTreinamento.status == "SUCESSO").count() == 1


def test_rn25_considera_somente_dias_encerrados(pg_engine, db_session, relogio, tmp_path):
    """RN25: o histórico considera somente os dias já encerrados. Executado em 05/10 (UTC), o treinamento usa a série até
    04/10; o registro do próprio dia 05/10, ainda em formação, fica de fora."""
    from datetime import date, datetime, timezone

    from src.ml.dados import carregar_banco

    dados = cenario()
    gravar_no_banco(db_session, dados, aptos_do(dados))
    with pg_engine.connect() as conexao:
        assert carregar_banco(conexao, CFG, date(2026, 10, 5)).precos["data"].max() == pd.Timestamp("2026-10-04")
    relogio.agora = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    resumo = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())

    assert resumo.status == "SUCESSO" and resumo.ultimo_dia == date(2026, 10, 4)
    assert db_session.get(ModeloPreditivo, resumo.modelo.versao).data_fim == date(2026, 10, 4)


def test_cu11_c1_liberados_sem_amostra_de_treino(pg_engine, db_session, relogio, tmp_path):
    """Passo 12: liberados sem nenhuma amostra no período de treinamento. O item lançado depois do fim desse período
    (07/12/2025) integra o conjunto de treinamento pela RN15, mas não ajustou os pesos."""
    novo = serie_constante(300_004, "2026-01-10", FIM, ruido=0.02, semente=4)
    dados = cenario(novo)
    gravar_no_banco(db_session, dados, aptos_do(dados))

    resumo = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())  # previsões perfeitas

    item = projecoes(db_session)[300_004]
    assert item.situacao == "LIBERADA" and item.integra_treino
    avaliacao = pd.read_parquet(Path(resumo_caminho(db_session, resumo)) / "avaliacao_teste.parquet")
    assert avaliacao.set_index("item_id").loc[300_004, "amostras_treino"] == 0
    esperado = int(((avaliacao["situacao"] == "LIBERADA") & (avaliacao["amostras_treino"] == 0)).sum())
    assert resumo.liberados_sem_amostra_de_treino == esperado >= 1


def resumo_caminho(db_session, resumo: ResumoDoTreinamento) -> str:
    return db_session.get(ModeloPreditivo, resumo.modelo.versao).caminho_artefatos


def test_cu11_c1_execucao_antiga_recebe_os_liberados_sem_amostra_de_treino(pg_engine, db_session, relogio, tmp_path):
    """As execuções concluídas antes da migração 0008 recebem o número a partir do artefato da versão (como a execução 1
    do banco real, que tem 292), quando o serviço `modelo` inicia. Só o que está em branco é preenchido."""
    from src.ml.treinamento_inicial import preencher_liberados_sem_amostra_de_treino

    dados = cenario()
    gravar_no_banco(db_session, dados, aptos_do(dados))
    resumo = executar(pg_engine, db_session, relogio, tmp_path, TreinadorFalso())
    original = resumo.liberados_sem_amostra_de_treino
    db_session.query(ExecucaoTreinamento).update({"liberados_sem_amostra_de_treino": None})
    db_session.commit()

    assert preencher_liberados_sem_amostra_de_treino(pg_engine) == 1
    db_session.expire_all()
    assert db_session.get(ExecucaoTreinamento, resumo.id_execucao).liberados_sem_amostra_de_treino == original
    assert preencher_liberados_sem_amostra_de_treino(pg_engine) == 0  # idempotente
