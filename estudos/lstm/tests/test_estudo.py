"""Verificações do estudo: o mecanismo de identificação e as regras de normalização e separação (RN03, RN24, RN25)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from avaliar import avaliar
from config import PERIODOS, Config
from dataset import DadosPreparados
from gerar_sinteticos import gerar
from io_dados import Entrada, _atributos_do_metadata, _padronizar_eventos, _padronizar_itens, _padronizar_precos
from preparar_dados import Resultado, preparar, rn03_por_serie, salvar, variaveis_de_calendario

CFG = Config()
CORTES = {"corte_validacao": "2025-07-14", "corte_teste": "2026-02-24"}


def entrada_de(dados: dict[str, pd.DataFrame]) -> Entrada:
    precos = _padronizar_precos(dados["precos"])
    return Entrada(precos=precos, itens=_padronizar_itens(dados.get("itens")),
                   eventos=_padronizar_eventos(dados.get("eventos")),
                   regiao_da_serie={s: "US" for s in precos["serie"].unique()},
                   aptos=None, origem="teste")


@pytest.fixture(scope="module")
def sinteticos() -> dict[str, pd.DataFrame]:
    return gerar(n_itens=24, semente=11)


@pytest.fixture(scope="module")
def preparado(sinteticos: dict[str, pd.DataFrame], tmp_path_factory: pytest.TempPathFactory) -> tuple[Resultado, Path]:
    res = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, **CORTES)
    pasta = tmp_path_factory.mktemp("saida")
    salvar(res, pasta)
    return res, pasta


# ------------------------------------------------------------------------------------ mecanismo de identificação
def test_ida_e_volta_recupera_o_preco_original(preparado: tuple[Resultado, Path]) -> None:
    """Passando o próprio y verdadeiro pela desnormalização, o preço reconstruído é o da linha original."""
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    av = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64"))
    ok = av.detalhe[av.detalhe["avaliavel"]]
    assert len(ok) > 0
    assert ok["erro_pct"].max() < 1e-5


def test_modelo_ingenuo_reproduz_o_preco_base(preparado: tuple[Resultado, Path]) -> None:
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("teste")
    alvo = dados.normalizacao["alvo"]
    zero = (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"])
    av = avaliar(dados, "teste", jan["id_amostra"].to_numpy(), np.tile(zero, (len(jan), 1)))
    assert (av.detalhe["preco_previsto"] == av.detalhe["preco_base"]).all()
    assert np.allclose(av.por_item["mape"], av.por_item["mape_ingenuo"])
    assert (av.por_item["situacao"] == "Bloqueada").all()  # não supera o ingênuo (RN10)


def test_id_linha_liga_original_e_normalizada(preparado: tuple[Resultado, Path]) -> None:
    res, pasta = preparado
    o, n = res.linhas_originais, res.linhas_normalizadas
    assert np.array_equal(o["id_linha"], np.arange(len(o)))
    assert np.array_equal(o["id_linha"], n["id_linha"])
    assert (o[["serie", "item_id", "data", "periodo"]].to_numpy() == n[["serie", "item_id", "data", "periodo"]].to_numpy()).all()

    dados = DadosPreparados(pasta)
    a, entrada, alvos = dados.amostra(int(dados.janelas("validacao")["id_amostra"].iloc[0]))
    assert len(entrada) == CFG.janela and len(alvos) == CFG.horizonte
    assert entrada["id_linha"].iloc[-1] == a["id_linha_origem"]
    assert (entrada["item_id"] == a["item_id"]).all()
    assert (alvos["id_linha"].to_numpy() == a["id_linha_origem"] + np.arange(1, CFG.horizonte + 1)).all()


def test_tensores_tem_o_formato_da_lstm(preparado: tuple[Resultado, Path]) -> None:
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    t = dados.tensores(dados.janelas("treino").head(64))
    assert t["X_seq"].shape == (64, CFG.janela, 16)
    assert t["X_est"].shape == (64, 4) and t["X_cat"].shape == (64, 2) and t["y"].shape == (64, CFG.horizonte)
    assert np.isfinite(t["X_seq"]).all()
    assert (np.abs(t["X_seq"]) <= 1.0 + 1e-6).all()  # RN24: tudo entre −1 e 1


# ------------------------------------------------------------------------------------------------------- RN25
def test_janelas_respeitam_as_datas_de_corte(preparado: tuple[Resultado, Path]) -> None:
    res, _ = preparado
    jan, n = res.janelas, res.linhas_normalizadas
    cv, ct = pd.Timestamp(CORTES["corte_validacao"]), pd.Timestamp(CORTES["corte_teste"])
    um, h = pd.Timedelta(days=1), pd.Timedelta(days=CFG.horizonte)
    t = jan[jan["periodo"] == "treino"]
    v = jan[jan["periodo"] == "validacao"]
    te = jan[jan["periodo"] == "teste"]
    assert (t["data_origem"] + h < cv).all()
    assert (v["data_origem"] + um >= cv).all() and (v["data_origem"] + h < ct).all()
    assert (te["data_origem"] + um >= ct).all()
    inicio = jan["id_linha_origem"].to_numpy() - CFG.janela + 1
    assert (n["item_id"].to_numpy()[inicio] == jan["item_id"].to_numpy()).all()  # a janela não mistura itens
    assert n.loc[jan["id_linha_origem"], "apta"].all()


def test_sem_vazamento_do_futuro(sinteticos: dict[str, pd.DataFrame], preparado: tuple[Resultado, Path]) -> None:
    """Alterar os preços da validação e do teste não muda nenhuma constante nem nenhuma linha do treino."""
    res_a, _ = preparado
    alterado = {k: v.copy() for k, v in sinteticos.items()}
    p = alterado["precos"]
    futuro = pd.to_datetime(p["data"]) >= pd.Timestamp(CORTES["corte_validacao"])
    rng = np.random.default_rng(0)
    p.loc[futuro, "preco"] = (p.loc[futuro, "preco"] * rng.uniform(0.2, 5.0, futuro.sum())).round().clip(lower=1)
    p.loc[futuro, "quantidade"] = p.loc[futuro, "quantidade"] * 3
    res_b = preparar(entrada_de(alterado), CFG, filtro_liquidez=False, **CORTES)

    na, nb = res_a.normalizacao, res_b.normalizacao
    assert na["constantes"] == nb["constantes"]
    assert na["nivel_item"] == nb["nivel_item"] and na["vocabulario"] == nb["vocabulario"]
    assert na["alvo"] == nb["alvo"]
    treino = res_a.linhas_normalizadas["periodo"] == "treino"
    pd.testing.assert_frame_equal(res_a.linhas_normalizadas[treino], res_b.linhas_normalizadas[treino])
    ja, jb = (r.janelas[r.janelas["periodo"] == "treino"].reset_index(drop=True) for r in (res_a, res_b))
    pd.testing.assert_frame_equal(ja, jb)


def test_dias_ate_patch_so_depois_do_anuncio() -> None:
    eventos = _padronizar_eventos(pd.DataFrame([{"tipo": "PATCH", "nome": "Patch", "data_inicio": "2025-01-20"}]))
    datas = pd.DatetimeIndex(["2025-01-01", "2025-01-06", "2025-01-10", "2025-01-19", "2025-01-20", "2025-01-21"])
    v = variaveis_de_calendario(datas, eventos, CFG)["f_dias_ate_patch"].to_numpy()
    assert v[0] == 1.0                      # 19 dias antes: ainda não anunciado
    assert v[1] == pytest.approx(14 / 14)   # 14 dias antes
    assert v[2] == pytest.approx(10 / 14)
    assert v[3] == pytest.approx(1 / 14)
    assert v[4] == 1.0 and v[5] == 1.0      # no dia e depois: não há próximo patch
    desde = variaveis_de_calendario(datas, eventos, CFG)["f_dias_desde_patch"].to_numpy()
    assert desde[4] == 0.0 and desde[5] == pytest.approx(1 / 60)


def test_temporada_ativa_e_evento_sazonal() -> None:
    eventos = _padronizar_eventos(pd.DataFrame([
        {"tipo": "TEMPORADA", "nome": "T1", "data_inicio": "2025-01-10"},
        {"tipo": "TEMPORADA", "nome": "T2", "data_inicio": "2025-05-01", "data_fim": "2025-06-30"},
        {"tipo": "EVENTO_SAZONAL", "nome": "Festival", "data_inicio": "2025-02-01", "data_fim": "2025-02-03"},
    ]))
    datas = pd.DatetimeIndex(["2025-01-09", "2025-01-10", "2025-02-02", "2025-04-30", "2025-05-31", "2025-07-01"])
    v = variaveis_de_calendario(datas, eventos, CFG)
    assert v["f_temporada_ativa"].tolist() == [0, 1, 1, 1, 1, 0]
    assert v["f_dias_temporada"].tolist() == pytest.approx([0, 0, 23 / 60, 1, 30 / 60, 0])
    assert v["f_evento"].tolist() == [0, 0, 1, 0, 0, 0]


# --------------------------------------------------------------------------------------- RN03, RN24 e groupby
def serie_simples(precos_por_item: dict[int, list[float | None]]) -> dict[str, pd.DataFrame]:
    linhas = []
    for item, precos in precos_por_item.items():
        for d, p in zip(pd.date_range("2024-01-01", periods=len(precos)), precos):
            if p is not None:
                linhas.append({"serie": "32512", "item_id": item, "data": d, "preco": p, "quantidade": 100})
    return {"precos": pd.DataFrame(linhas)}


def test_rn03_descarta_o_pico_e_preenche_ate_3_dias() -> None:
    base: list[float | None] = [100.0 + (i % 3) for i in range(120)]
    base[60] = 500.0                        # pico: > EMA·4 só se a EMA não incluir o próprio dia (EMA anterior ≈ 101)
    base[70] = 5.0                          # queda absurda: < EMA·0,1
    base[80:83] = [None, None, None]        # 3 dias sem registro: preenchidos
    base[90:94] = [None, None, None, None]  # 4 dias: o quarto fica sem preço
    res = preparar(entrada_de(serie_simples({1: base})), CFG, filtro_liquidez=False,
                   corte_validacao="2024-03-20", corte_teste="2024-04-10")
    o = res.linhas_originais.set_index("id_linha")
    assert o.loc[60, "descartado_rn03"] and not o.loc[60, "observado"] and o.loc[60, "preco_cobre"] == o.loc[59, "preco_cobre"]
    assert o.loc[70, "descartado_rn03"]
    assert o.loc[[80, 81, 82], "preenchido"].all() and o.loc[[80, 81, 82], "preco_cobre"].notna().all()
    assert o.loc[[90, 91, 92], "preenchido"].all() and pd.isna(o.loc[93, "preco_cobre"])
    n = res.linhas_normalizadas.set_index("id_linha")
    assert n.loc[80, "f_observado"] == 0.0 and n.loc[79, "f_observado"] == 1.0
    assert not n.loc[93, "apta"]


def test_calculos_sao_feitos_item_a_item() -> None:
    """O primeiro dia de um item não pode usar o último preço do item anterior."""
    res = preparar(entrada_de(serie_simples({1: [10.0] * 80, 2: [5_000_000.0] * 80})), CFG, filtro_liquidez=False,
                   corte_validacao="2024-03-10", corte_teste="2024-03-15")
    n = res.linhas_normalizadas
    primeiro_do_item_2 = n.index[n["item_id"] == 2][0]
    assert pd.isna(n.loc[primeiro_do_item_2, "f_log_return"])
    assert not res.linhas_originais.loc[primeiro_do_item_2, "descartado_rn03"]
    assert (n.loc[n["item_id"] == 2, "f_log_return"].dropna() == 0).all()


def test_periodos_cobrem_70_20_10_do_calendario(sinteticos: dict[str, pd.DataFrame]) -> None:
    res = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False)
    c = {k: pd.Timestamp(v) for k, v in res.normalizacao["cortes"].items()}
    total = (c["fim"] - c["inicio"]).days + 1
    assert (c["corte_validacao"] - c["inicio"]).days / total == pytest.approx(0.70, abs=0.002)
    assert (c["corte_teste"] - c["inicio"]).days / total == pytest.approx(0.90, abs=0.002)
    assert set(res.janelas["periodo"]) == set(PERIODOS)


# ------------------------------------------------------------------------- RN03: EMA só com os preços aceitos
def _rn03(precos: list[float | None]) -> tuple[np.ndarray, np.ndarray]:
    preco = np.array([np.nan if p is None else p for p in precos], dtype="float64")
    inicio = np.zeros(len(preco), dtype=bool)
    inicio[0] = True
    return rn03_por_serie(preco, inicio, CFG)


def test_rn03_pico_isolado_nao_contamina_a_ema() -> None:
    precos: list[float | None] = [100.0] * 30 + [999_990_100.0] + [100.0] * 30  # anúncio de 99.999 ouro num só dia
    ema, descartado = _rn03(precos)
    assert np.flatnonzero(descartado).tolist() == [30]  # com a EMA dos preços brutos, os 30 dias seguintes cairiam
    assert ema[31] == pytest.approx(100.0)


def test_rn03_novo_patamar_confirmado_e_aceito() -> None:
    precos: list[float | None] = [100.0] * 30 + [1_000.0] * 30  # mudança real: o preço passa a 10× e fica
    ema, descartado = _rn03(precos)
    assert not descartado.any()                     # os dias que confirmam o patamar também são aceitos
    assert ema[40] == pytest.approx(1_000.0)        # a EMA recomeça no novo patamar e não trava a série
    pico_de_dois_dias = [100.0] * 30 + [1_000.0, 1_000.0] + [100.0] * 10
    assert np.flatnonzero(_rn03(pico_de_dois_dias)[1]).tolist() == [30, 31]  # 2 dias não confirmam
    seis_dias = [100.0] * 30 + [1_000.0] * (CFG.rn03_confirmacao - 1) + [100.0] * 10
    assert _rn03(seis_dias)[1].sum() == CFG.rn03_confirmacao - 1  # um dia a menos que a confirmação: descartados


def test_rn03_pico_no_inicio_de_uma_mudanca_real_continua_descartado() -> None:
    """Item 5526: o preço passa de ~4.500 a 20.000 (mais de 4×, fora da faixa) e o primeiro dia da mudança tem um
    anúncio de 301 mil ouro. A sequência confirma o patamar de 20.000 pela mediana; o pico fica fora."""
    precos: list[float | None] = [4_500.0] * 30 + [3_011_110_000.0] + [20_000.0] * 20
    ema, descartado = _rn03(precos)
    assert np.flatnonzero(descartado).tolist() == [30]
    assert ema[45] == pytest.approx(20_000.0)


def test_rn03_salto_absurdo_so_vira_patamar_depois_de_28_dias() -> None:
    """Item 38518: anúncios de 1 milhão de ouro (1.000.000× o preço de 1 ouro) sozinhos por duas semanas."""
    duas_semanas: list[float | None] = [10_000.0] * 30 + [10_000_000_100.0] * 14 + [10_000.0] * 20
    _, descartado = _rn03(duas_semanas)
    assert np.flatnonzero(descartado).tolist() == list(range(30, 44))
    um_mes: list[float | None] = [10_000.0] * 30 + [10_000_000_100.0] * CFG.rn03_confirmacao_absurdo + [10_000_000_000.0] * 5
    _, descartado = _rn03(um_mes)
    assert not descartado.any()  # durou o suficiente: é o novo patamar


def test_rn03_placeholder_no_inicio_da_serie_e_descartado() -> None:
    precos: list[float | None] = [999_990_100.0, None, 999_990_100.0] + [1_000.0 + i for i in range(40)]
    _, descartado = _rn03(precos)
    assert descartado[[0, 2]].all()                 # o patamar inicial nunca foi confirmado
    assert not descartado[3:].any()                 # os preços reais confirmam o patamar e ficam
    longa = precos[:3] + [1_000.0 + (i % 5) for i in range(150)]
    res = preparar(entrada_de(serie_simples({1: longa})), CFG, filtro_liquidez=False,
                   corte_validacao="2024-04-01", corte_teste="2024-05-01")
    o = res.linhas_originais
    assert o.loc[[0, 2], "descartado_rn03"].all() and not o.loc[[0, 2], "observado"].any()


# ------------------------------------------------------------------------------ eventos: pré-patch e versões
def test_pre_patch_pela_versao_maior_e_versao_repetida_conta_uma_vez() -> None:
    eventos = _padronizar_eventos(pd.DataFrame([
        {"tipo": "PATCH", "nome": "Patch 11.2.7", "versao": "11.2.7", "data_inicio": "2025-12-02"},
        {"tipo": "PATCH", "nome": "Patch 12.0.0", "versao": "12.0.0", "data_inicio": "2026-01-20"},  # sem "pre-patch"
        {"tipo": "PATCH", "nome": "Patch 12.0.1", "versao": "12.0.1", "data_inicio": "2026-02-10"},
        {"tipo": "EXPANSAO", "nome": "Midnight", "data_inicio": "2026-03-02"},
        {"tipo": "PATCH", "nome": "Patch 12.0.5", "versao": "12.0.5", "data_inicio": "2026-04-21"},
        {"tipo": "PATCH", "nome": "Patch 12.0.5", "versao": "12.0.5", "data_inicio": "2026-05-19"},  # início de temporada
    ]))
    datas = pd.DatetimeIndex(["2026-01-01", "2026-01-10", "2026-02-01", "2026-02-20", "2026-05-20"])
    v = variaveis_de_calendario(datas, eventos, CFG)
    assert v["f_expansao"].tolist() == [0, 1, 0, 1, 0]  # 10 dias antes do pré-patch e 10 dias antes da expansão
    assert v["f_dias_desde_patch"].iloc[4] == pytest.approx(29 / 60)  # conta do 12.0.5 de abril, não da repetição


# --------------------------------------------------------------------------- variável 18: commodity
def test_commodity_pela_origem_do_arquivo_da_undermine() -> None:
    ids = frozenset({"32512", "32513"})
    assert _atributos_do_metadata(1, {"source_region": "32512"}, ids)["commodity"] is True
    assert _atributos_do_metadata(2, {"source_region": "3209"}, ids)["commodity"] is False
    assert _atributos_do_metadata(3, {"item_class_id": 7}, ids)["commodity"] is None
    assert _atributos_do_metadata(4, {"source_region": "32512", "is_commodity": False}, ids)["commodity"] is False
