"""
Plano de testes do CU05 – Consultar Previsão Preditiva, Cenário 01, no serviço `modelo` (precisam do pipeline do CU11,
com pandas e TensorFlow). Rodam contra um PostgreSQL temporário. Os demais fluxos do C1 rodam no host
(tests/integration/test_cu05_consultar_previsao.py) e os de tela, no frontend.

- FA2: o critério de elegibilidade que a API recalcula em SQL (RN02 e RN27) é o mesmo do `selecionar` do CU11.
- Ponta a ponta: o treinamento (CU11-C1) salva a versão, a consolidação (CU11-C3) carrega o modelo salvo e grava as
  predições, e a API do CU05 as devolve, a partir do mesmo preço de D que a consolidação usou como base.
"""
from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("pandas")
pytest.importorskip("tensorflow")

import pandas as pd  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apoio_treino import CFG  # noqa: E402
from sinteticos import SERIE_REINO, gerar, gravar_no_banco, serie_constante  # noqa: E402
from src.controllers import item_controller  # noqa: E402
from src.ml.dados import carregar_banco  # noqa: E402
from src.ml.selecao import selecionar  # noqa: E402
from src.models.modelo import PredicaoDiaria  # noqa: E402
from src.repositories.projecao_repository import ProjecaoRepository  # noqa: E402
from src.services.projecao_service import ProjecaoService, atende_rn02, atende_rn27  # noqa: E402
from test_cu11_c3_ponta_a_ponta import (D, DIA_DO_C1, ESTAVEL, TreinadorDePrevisao, consolidar,  # noqa: E402
                                        importacao_de_hoje, preco_do_dia, vigente)

HOJE = date(2026, 10, 6)  # a base vai até 05/10, o último dia encerrado


def test_cu05_c1_fa2_criterio_da_api_igual_ao_do_selecao(pg_engine, db_session):
    """FA2: para cada série e item, a RN02 e a RN27 recalculadas pela API (SQL) dão o mesmo resultado que o `selecionar`
    do CU11 (pandas), com os mesmos dados sintéticos: itens líquidos e ilíquidos, nos limites de 50 unidades e de 60 dias,
    sem registros recentes, curtos e nas duas séries da região."""
    dados = gerar(n_itens=6, inicio="2025-01-01", fim="2026-10-05", semente=3)
    extras = [
        serie_constante(9001, "2025-01-01", "2026-10-05", quantidade=20),  # ilíquido
        serie_constante(9002, "2026-08-20", "2026-10-05"),  # 47 dias
        serie_constante(9003, "2026-09-01", "2026-10-05", quantidade=10),  # os dois
        serie_constante(9004, "2025-01-01", "2026-10-05", quantidade=50),  # no limite: não passa (> 50)
        serie_constante(9005, "2025-01-01", "2026-10-05", quantidade=51),
        serie_constante(9006, "2026-08-07", "2026-10-05"),  # 60 dias: passa
        serie_constante(9007, "2026-08-08", "2026-10-05"),  # 59 dias
        serie_constante(9008, "2025-01-01", "2026-09-20"),  # sem registros nos últimos 7 dias da base
        serie_constante(9009, "2025-01-01", "2026-10-05", quantidade=80, serie=SERIE_REINO),  # série do reino
        serie_constante(9010, "2025-01-01", "2026-10-05", quantidade=30, a_cada=3),  # registros espaçados
    ]
    dados["precos"] = pd.concat([dados["precos"], *extras], ignore_index=True)
    gravar_no_banco(db_session, dados, set(dados["precos"]["item_id"].astype(int)))

    with pg_engine.connect() as conexao:
        entrada = carregar_banco(conexao, CFG, ate=HOJE)
    do_cu11 = {(str(r.serie), int(r.item_id)): (bool(r.liquido_rn02), bool(r.historico_rn27))
               for r in selecionar(entrada, CFG, "US").itens.itertuples()}

    repositorio = ProjecaoRepository(db_session)
    da_api = {}
    for item_id in sorted({item for _, item in do_cu11}):
        for serie in repositorio.series_do_item(item_id, "US", HOJE):
            dados_da_serie = repositorio.dados_da_serie(serie, item_id, "US", HOJE, CFG.liquidez_dias)
            da_api[(serie, item_id)] = (atende_rn02(dados_da_serie, CFG), atende_rn27(dados_da_serie, CFG))

    assert da_api == do_cu11
    assert {chave: do_cu11[chave] for chave in [("32512", 9004), ("32512", 9005), ("32512", 9006), ("32512", 9007)]} == {
        ("32512", 9004): (False, True), ("32512", 9005): (True, True), ("32512", 9006): (True, True),
        ("32512", 9007): (True, False)}  # os limites estão mesmo nos casos


def test_cu05_c1_ponta_a_ponta_treino_consolidacao_e_projecao(pg_engine, db_session, relogio, tmp_path):
    """Histórico → treino (CU11-C1, a versão salva) → consolidação (CU11-C3, que carrega o modelo salvo e grava as
    predições) → projeção (CU05-C1): a API devolve as 7 predições gravadas, a partir do preço de D que a consolidação usou
    como base. Com o treinador "ingênuo", a previsão é o próprio preço de D, e a variação é zero."""
    versao = vigente(pg_engine, db_session, relogio, tmp_path)
    importacao_de_hoje(db_session, relogio)
    consolidar(pg_engine, relogio, TreinadorDePrevisao("ingenua"))
    gravadas = (db_session.query(PredicaoDiaria).filter_by(item_id=ESTAVEL, versao=versao)
                .order_by(PredicaoDiaria.data_prevista).all())
    assert [p.data_previsao for p in gravadas] == [D] * 7

    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    app.dependency_overrides[item_controller.get_servico_da_projecao] = lambda: ProjecaoService(db_session, lambda: DIA_DO_C1)
    resposta = TestClient(app).get(f"/api/items/{ESTAVEL}/projection")

    assert resposta.status_code == 200, resposta.text
    projecao = resposta.json()
    assert (projecao["situacao"], projecao["data_referencia"], projecao["desatualizada"]) == ("DISPONIVEL", D.isoformat(),
                                                                                              False)
    assert projecao["preco_referencia"] == preco_do_dia(db_session, ESTAVEL, D)  # a mesma base da consolidação
    assert [(p["data_prevista"], p["preco_previsto"]) for p in projecao["predicoes"]] == [
        (g.data_prevista.isoformat(), g.preco_previsto) for g in gravadas]
    assert {p["preco_previsto"] for p in projecao["predicoes"]} == {projecao["preco_referencia"]}
    assert {p["variacao_pct"] for p in projecao["predicoes"]} == {0.0}
