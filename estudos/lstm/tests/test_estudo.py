"""Verificações do estudo: o mecanismo de identificação e as regras de normalização e separação (RN03, RN24, RN25)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from avaliar import avaliar
from dataclasses import replace

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
    # padrão (etapa 2b): eventos agregados, só as 16 variáveis de sequência
    assert len(dados.var_seq) == 16
    assert t["X_seq"].shape == (64, CFG.janela, len(dados.var_seq))
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


# ------------------------------------------------------------------------------- variável 14 detalhada e máscara
def test_eventos_detalhados_um_par_por_festival_e_feira() -> None:
    eventos = _padronizar_eventos(pd.DataFrame([
        {"tipo": "EVENTO_SAZONAL", "nome": "Feast of Winter Veil", "data_inicio": "2025-12-16", "data_fim": "2026-01-02"},
        {"tipo": "EVENTO_SAZONAL", "nome": "Love is in the Air", "data_inicio": "2026-02-09", "data_fim": "2026-02-23"},
        {"tipo": "EVENTO_SAZONAL", "nome": "Noblegarden (aproximado)", "data_inicio": "2026-04-05",
         "data_fim": "2026-04-12"},
        {"tipo": "RECORRENTE", "nome": "Darkmoon Faire", "data_inicio": "2026-01-04", "data_fim": "2026-01-10"},
        {"tipo": "RECORRENTE", "nome": "Trading Post monthly rotation", "data_inicio": "2026-01-01",
         "data_fim": "2026-01-31"},
    ]))
    datas = pd.DatetimeIndex(["2025-12-10", "2025-12-16", "2026-01-02", "2026-01-03", "2026-02-10"])
    v = variaveis_de_calendario(datas, eventos, replace(CFG, eventos_detalhados=True))
    inverno = "f_festival_feast_of_winter_veil"
    assert v[inverno].tolist() == [0, 1, 1, 0, 0]
    # fração dos próximos 7 dias com o festival: em 10/12, só 16 e 17 → 2/7 (o calendário é conhecido antes, RN25)
    assert v[inverno + "_prox"].tolist() == pytest.approx([2 / 7, 1, 0, 0, 0])
    assert "f_festival_noblegarden" in v.columns  # sem a marca "(aproximado)"
    assert v["f_feira_negrilua"].tolist() == [0, 0, 0, 0, 0]
    assert v["f_feira_negrilua_prox"].tolist() == pytest.approx([0, 0, 6 / 7, 1, 0])
    assert not any("trading" in c for c in v.columns)  # a rotação do Posto de Troca não entra
    assert v["f_evento"].tolist() == [0, 1, 1, 0, 1]  # o agregado continua


def test_eventos_agregados_so_mantem_f_evento() -> None:
    eventos = _padronizar_eventos(pd.DataFrame([
        {"tipo": "EVENTO_SAZONAL", "nome": "Brewfest", "data_inicio": "2025-09-20", "data_fim": "2025-10-06"},
        {"tipo": "RECORRENTE", "nome": "Darkmoon Faire", "data_inicio": "2025-10-05", "data_fim": "2025-10-11"}]))
    v = variaveis_de_calendario(pd.DatetimeIndex(["2025-10-01"]), eventos, replace(CFG, eventos_detalhados=False))
    assert not any(c.startswith(("f_festival_", "f_feira")) for c in v.columns)
    assert v["f_evento"].tolist() == [1]


def test_festival_sem_dia_ativo_no_treino_fica_de_fora(sinteticos: dict[str, pd.DataFrame]) -> None:
    """Um festival que só aparece depois do corte da validação teria pesos nunca treinados: não entra nas variáveis."""
    dados = {k: v.copy() for k, v in sinteticos.items()}
    novo = pd.DataFrame([{"tipo": "EVENTO_SAZONAL", "nome": "Festival novo", "versao": None,
                          "data_inicio": "2026-08-01", "data_fim": "2026-08-10", "regiao": "GLOBAL"}])
    dados["eventos"] = pd.concat([dados["eventos"], novo], ignore_index=True)
    res = preparar(entrada_de(dados), replace(CFG, eventos_detalhados=True), filtro_liquidez=False, **CORTES)
    seq = res.normalizacao["variaveis"]["sequencia"]
    assert "f_festival_festival_novo" not in seq and "f_festival_festival_novo_prox" not in seq
    assert "Festival novo" in res.normalizacao["eventos_detalhados"]["sem_ocorrencia_no_treino"]
    assert {"f_feira_negrilua", "f_festival_festival_de_inverno", "f_festival_festival_de_verao"} <= set(seq)


def test_perda_mascarada_ignora_os_dias_nao_observados() -> None:
    keras = pytest.importorskip("keras")
    from treinar import criar_perdas

    perda, mae = criar_perdas("huber", 3)
    y_pred = np.array([[0.1, 0.5, -2.0]], dtype="float32")
    y = np.array([[0.0, 0.4, 1.0]], dtype="float32")
    m = np.array([[1, 1, 0]], dtype="float32")
    base = float(np.asarray(perda(np.concatenate([y, m], 1), y_pred))[0])
    assert base == pytest.approx(0.005, rel=1e-4)  # só os dois dias observados: Huber(0,1) = 0,005
    y_outro = y.copy()
    y_outro[0, 2] = 50.0  # mudar o dia não observado não muda nada
    assert float(np.asarray(perda(np.concatenate([y_outro, m], 1), y_pred))[0]) == pytest.approx(base)
    assert float(np.asarray(mae(np.concatenate([y, m], 1), y_pred))[0]) == pytest.approx(0.1, rel=1e-4)
    # com todos os dias observados, é a Huber do Keras
    um = np.ones_like(y)
    ref = float(np.asarray(keras.losses.Huber(delta=1.0, reduction=None)(y, y_pred))[0])
    assert float(np.asarray(perda(np.concatenate([y, um], 1), y_pred))[0]) == pytest.approx(ref, rel=1e-5)


def test_avaliacao_traz_mdape_erro_relativo_e_curva_de_liberacao(preparado: tuple[Resultado, Path]) -> None:
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    alvo = dados.normalizacao["alvo"]
    zero = (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"])
    av = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), np.tile(zero, (len(jan), 1)))
    # o próprio ingênuo: erro relativo 1 e nenhum item liberado (não supera a si mesmo)
    assert np.allclose(av.por_item["erro_relativo_ingenuo"].dropna(), 1.0)
    assert np.allclose(av.por_item["mdape"], av.por_item["mdape_ingenuo"])
    assert all(v == 0 for m in av.resumo["liberacao_por_limiar"].values() for v in m.values())
    assert set(av.resumo["liberacao_por_limiar"]["mdape"]) == {"10%", "15%", "20%", "25%", "30%"}


def test_rn10_libera_por_mdape_quem_supera_o_ingenuo(preparado: tuple[Resultado, Path]) -> None:
    """RN10 (decisão após a etapa 2b): MdAPE ≤ 15% e menor que o MdAPE do ingênuo."""
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    perfeito = jan[dados.colunas_alvo()].to_numpy("float64")  # o próprio y: erro ~0
    av = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), perfeito)
    assert av.resumo["rn10"] == {"metrica": "mdape", "limiar": 0.15, "minimo_dias": 30}
    esperado = av.por_item["mdape_ingenuo"] > av.por_item["mdape"]
    assert ((av.por_item["situacao"] == "Liberada") == esperado).all()
    # a regra antiga continua disponível para comparação
    av_mape = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), perfeito, limiar=0.15, metrica="mape")
    assert av_mape.resumo["rn10"]["metrica"] == "mape"


# ------------------------------------------------------------------------- etapa 2c: itens fora do treino
FRACAO = 0.25


@pytest.fixture(scope="module")
def com_reserva(sinteticos: dict[str, pd.DataFrame],
                tmp_path_factory: pytest.TempPathFactory) -> tuple[Resultado, Path]:
    res = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, reservar_itens=FRACAO, semente=3, **CORTES)
    pasta = tmp_path_factory.mktemp("reserva")
    salvar(res, pasta)
    return res, pasta


def test_reserva_estratificada_pela_classe_e_reprodutivel() -> None:
    from preparar_dados import sortear_reservados

    itens = pd.DataFrame({"item_id": range(100), "classe_id": [7.0] * 60 + [2.0] * 20 + [None] * 20})
    a = sortear_reservados(itens, 0.2, semente=1)
    assert a == sortear_reservados(itens, 0.2, semente=1)          # mesma semente, mesmos itens
    assert a != sortear_reservados(itens, 0.2, semente=2)
    por_classe = itens.assign(r=itens["item_id"].isin(a)).groupby(itens["classe_id"].fillna(-1))["r"].sum()
    assert por_classe.to_dict() == {-1.0: 4, 2.0: 4, 7.0: 12}       # 20% de cada classe


def test_reservados_nao_influenciam_a_normalizacao(sinteticos: dict[str, pd.DataFrame],
                                                   com_reserva: tuple[Resultado, Path]) -> None:
    """Constantes, faixa do nível, vocabulário e escala do alvo são as mesmas de uma base sem os itens reservados.
    (A variação do índice da subclasse é a exceção esperada: no dia, ela inclui os preços dos outros itens do mercado.)"""
    res, _ = com_reserva
    reservados = set(res.normalizacao["reserva"]["itens"])
    assert 0 < len(reservados) < res.itens["item_id"].nunique()
    sem = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, excluir_itens=reservados, **CORTES)
    assert not set(sem.janelas["item_id"]) & reservados
    ca, cb = res.normalizacao["constantes"], sem.normalizacao["constantes"]
    assert {k: v for k, v in ca.items() if k != "f_retorno_subclasse"} == \
           {k: v for k, v in cb.items() if k != "f_retorno_subclasse"}
    assert res.normalizacao["nivel_item"] == sem.normalizacao["nivel_item"]
    assert res.normalizacao["vocabulario"] == sem.normalizacao["vocabulario"]
    assert np.allclose(res.normalizacao["alvo"]["media"], sem.normalizacao["alvo"]["media"])
    assert np.allclose(res.normalizacao["alvo"]["desvio"], sem.normalizacao["alvo"]["desvio"])


def test_janelas_marcam_reservados_e_a_idade_do_item(com_reserva: tuple[Resultado, Path]) -> None:
    res, _ = com_reserva
    jan, o = res.janelas, res.linhas_originais
    reservados = set(res.normalizacao["reserva"]["itens"])
    assert (jan["reservado"] == jan["item_id"].isin(reservados)).all()
    assert set(res.itens.loc[res.itens["reservado"], "item_id"]) == reservados
    primeiro = o.groupby("item_id")["data"].min()
    esperado = (jan["data_origem"] - jan["item_id"].map(primeiro)).dt.days + 1
    assert (jan["dias_de_historico"] == esperado).all()
    assert jan["dias_de_historico"].min() >= CFG.janela  # não há amostra antes de a janela encher
    assert res.normalizacao["contagens"]["amostras_reservadas"]["treino"] == int(
        (jan["reservado"] & (jan["periodo"] == "treino")).sum())


def test_treino_deixa_os_reservados_de_fora_e_o_controle_os_inclui(com_reserva: tuple[Resultado, Path]) -> None:
    from treinar import separar_reservados

    _, pasta = com_reserva
    dados = DadosPreparados(pasta)
    tr, va = dados.janelas("treino"), dados.janelas("validacao")
    tr_a, va_a, info_a = separar_reservados(tr, va, incluir=False)
    assert not tr_a["reservado"].any() and not va_a["reservado"].any()   # nem no treino nem na parada antecipada
    assert len(tr_a) == int((~tr["reservado"]).sum())
    tr_b, va_b, info_b = separar_reservados(tr, va, incluir=True)
    assert len(tr_b) == len(tr) and len(va_b) == len(va)
    assert info_a["itens_reservados"] == info_b["itens_reservados"] > 0
    assert separar_reservados(tr.drop(columns="reservado"), va, False)[2] is None  # base sem reserva: nada muda


def test_normalizacao_de_outra_base_reproduz_a_mesma_base(sinteticos: dict[str, pd.DataFrame],
                                                          preparado: tuple[Resultado, Path]) -> None:
    """Aplicar a normalização gravada aos mesmos itens dá exatamente as mesmas linhas e amostras."""
    res_a, _ = preparado
    res_b = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, normalizacao_base=res_a.normalizacao)
    assert res_b.normalizacao["assinatura"] == res_a.normalizacao["assinatura"]
    pd.testing.assert_frame_equal(res_a.linhas_normalizadas, res_b.linhas_normalizadas)
    pd.testing.assert_frame_equal(res_a.janelas, res_b.janelas)


def test_normalizacao_de_outra_base_em_itens_que_ela_nao_tem(sinteticos: dict[str, pd.DataFrame]) -> None:
    """O caminho de um item qualquer: base B só com itens novos, normalizada como a versão do modelo (base A).
    Uma subclasse que a base A nunca viu vira categoria desconhecida (0)."""
    itens = sinteticos["itens"]
    so_em_b = set(itens.loc[itens["subclasse_id"] == 8, "item_id"])
    outros_b = set(itens["item_id"].iloc[::4]) - so_em_b
    b_ids = so_em_b | outros_b
    res_a = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, excluir_itens=b_ids, **CORTES)
    res_b = preparar(entrada_de(sinteticos), CFG, filtro_liquidez=False, normalizacao_base=res_a.normalizacao,
                     excluir_itens=set(res_a.itens["item_id"]))
    assert set(res_b.itens["item_id"]) == b_ids
    for k in ("constantes", "nivel_item", "vocabulario", "alvo", "variaveis"):
        assert res_b.normalizacao[k] == res_a.normalizacao[k]
    assert res_b.normalizacao["cortes"]["corte_validacao"] == res_a.normalizacao["cortes"]["corte_validacao"]
    assert res_b.normalizacao["normalizacao_de"]["assinatura"] == res_a.normalizacao["assinatura"]
    assert "8" not in res_a.normalizacao["vocabulario"]["subclasse_id"]
    nb = res_b.linhas_normalizadas
    assert (nb.loc[nb["item_id"].isin(so_em_b), "subclasse_idx"] == 0).all()
    assert len(res_b.janelas[res_b.janelas["periodo"] == "validacao"]) > 0


def test_prever_recusa_base_com_outra_normalizacao(preparado: tuple[Resultado, Path],
                                                   com_reserva: tuple[Resultado, Path]) -> None:
    from prever import conferir_compatibilidade

    a, b = preparado[0].normalizacao, com_reserva[0].normalizacao
    conferir_compatibilidade(a, a)
    with pytest.raises(ValueError, match="incompatível"):
        conferir_compatibilidade(a, b)  # a reserva muda as constantes e a escala do alvo


def test_avaliacao_por_grupo_e_por_idade(com_reserva: tuple[Resultado, Path]) -> None:
    _, pasta = com_reserva
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    av = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64"))
    g = av.resumo["por_grupo"]["reservado"]
    assert set(g) == {"False", "True"}
    assert g["False"]["itens"] + g["True"]["itens"] == av.resumo["itens"]
    assert "reservado" in av.por_item.columns and "commodity" in av.resumo["por_grupo"]
    idade = av.resumo["por_idade"]
    assert [f["faixa"] for f in idade][0] == "até 89 dias" and len(idade) == 5
    assert sum(f["alvos"] for f in idade) == av.resumo["alvos_avaliados"]


def test_comparacao_pareada_item_a_item() -> None:
    from comparar import comparar

    base = {"serie": ["1", "1", "1"], "item_id": [1, 2, 3], "mape": [0.3, 0.2, 0.5],
            "erro_relativo_ingenuo": [0.9, 0.8, 1.1], "reservado": [True, True, False]}
    a = pd.DataFrame({**base, "mdape": [0.12, 0.30, 0.50], "situacao": ["Liberada", "Bloqueada", "Bloqueada"]})
    b = pd.DataFrame({**base, "mdape": [0.10, 0.31, 0.10], "situacao": ["Liberada", "Bloqueada", "Liberada"]})
    r = comparar(a, b, filtro="reservado")
    assert r["itens"] == 2                                   # o item 3 não é reservado
    assert r["mdape"]["mediana_da_diferenca"] == pytest.approx(0.005)
    assert r["mdape"]["itens_a_pior_que_b"] == 1 and r["mdape"]["itens_com_diferenca_ate_1pp"] == 1
    assert r["rn10"] == {"liberados_a": 1, "liberados_b": 1, "liberados_nos_dois": 1, "so_a": 0, "so_b": 0}


# ------------------------------------------------------------------- etapa 2d: ciclo de vida do item (19 e 20)
LANCAMENTOS = np.array(["2022-11-28", "2024-08-26", "2026-03-02"], dtype="datetime64[D]")


def test_item_da_expansao_vigente_e_idade_do_item() -> None:
    from preparar_dados import expansao_do_item, variaveis_do_ciclo_do_item

    inicio = np.datetime64("2022-09-04")
    # já existia (censurado) · acesso antecipado da 2ª · lançado no meio da 2ª · acesso antecipado da 3ª
    primeiro = np.array(["2022-09-04", "2024-08-23", "2025-02-25", "2026-02-27"], dtype="datetime64[D]")
    assert expansao_do_item(primeiro, LANCAMENTOS, inicio, 7).tolist() == [-1, 1, 1, 2]

    def em(data: str) -> tuple[list[float], list[float]]:
        d = np.full(4, np.datetime64(data))
        f_vig, f_idade = variaveis_do_ciclo_do_item(np.maximum(d, primeiro), primeiro, LANCAMENTOS, inicio, CFG)
        return f_vig.tolist(), f_idade.tolist()

    assert em("2024-08-24")[0][:2] == [0, 0]     # acesso antecipado: a expansão do item ainda não é a vigente
    assert em("2025-06-01")[0] == [0, 1, 1, 0]    # (o 4º item é avaliado em 27/02/2026, antes do lançamento)
    assert em("2026-03-02")[0] == [0, 0, 0, 1]   # a troca: a 2ª deixa de ser vigente no dia do lançamento da 3ª
    idade = em("2026-04-27")[1]                   # 3ª expansão: 59 dias de idade
    assert idade[0] == 1.0 and idade[1] == 1.0 and idade[3] == pytest.approx(59 / CFG.idade_limite_dias)


def test_variaveis_do_ciclo_nao_mudam_as_amostras(sinteticos: dict[str, pd.DataFrame],
                                                  preparado: tuple[Resultado, Path]) -> None:
    """As variáveis 19 e 20 entram no fim da sequência e não mudam nenhuma amostra nem a normalização das demais."""
    from config import VARIAVEL_EXPANSAO_ITEM, VARIAVEL_IDADE_ITEM

    base, _ = preparado
    cfg = replace(CFG, variavel_expansao_item=True, variavel_idade_item=True)
    res = preparar(entrada_de(sinteticos), cfg, filtro_liquidez=False, **CORTES)
    seq = res.normalizacao["variaveis"]["sequencia"]
    assert seq == base.normalizacao["variaveis"]["sequencia"] + [VARIAVEL_EXPANSAO_ITEM, VARIAVEL_IDADE_ITEM]
    pd.testing.assert_frame_equal(res.janelas, base.janelas)
    assert res.normalizacao["constantes"] == base.normalizacao["constantes"]
    n = res.linhas_normalizadas
    assert set(n[VARIAVEL_EXPANSAO_ITEM].unique()) == {0.0, 1.0}
    assert n[VARIAVEL_IDADE_ITEM].between(0, 1).all()
    ciclo = res.normalizacao["ciclo_do_item"]
    assert ciclo["expansoes"] == ["Expansão A", "Expansão B", "Expansão C"]
    # itens que já existiam no início dos dados: expansão desconhecida, nunca "vigente", idade máxima
    velhos = set(res.itens.loc[res.itens["expansao"] == "anterior aos dados ou desconhecida", "item_id"])
    assert velhos and (n.loc[n["item_id"].isin(velhos), VARIAVEL_EXPANSAO_ITEM] == 0).all()
    assert (n.loc[n["item_id"].isin(velhos), VARIAVEL_IDADE_ITEM] == 1).all()
    # a mesma normalização aplicada de novo (caminho do prever.py) reproduz as variáveis
    res_b = preparar(entrada_de(sinteticos), cfg, filtro_liquidez=False, normalizacao_base=res.normalizacao)
    pd.testing.assert_frame_equal(res.linhas_normalizadas, res_b.linhas_normalizadas)


def test_transicao_separa_a_expansao_que_sai() -> None:
    from transicao import ANTERIORES, ENTRA, SAI, analisar

    lanc = ["2024-08-26", "2026-03-02"]
    det = pd.DataFrame({
        "item_id": [1, 1, 2, 2, 3],
        "data_origem": pd.to_datetime(["2026-02-20", "2025-10-01", "2026-02-25", "2025-10-01", "2026-04-20"]),
        "h": [7, 7, 7, 7, 7],
        "preco_real": [80.0, 100, 90, 100, 50], "preco_previsto": [100, 100, 95, 101, 50], "preco_base": [100] * 4 + [55],
        "avaliavel": [True] * 5,
    })
    det["erro_pct"] = (det["preco_previsto"] - det["preco_real"]).abs() / det["preco_real"]
    det["erro_pct_ingenuo"] = (det["preco_base"] - det["preco_real"]).abs() / det["preco_real"]
    exp = pd.Series({1: "B", 2: "A", 3: "C"})
    t = analisar(det, exp, ["B", "C"], lanc, pd.Timestamp("2026-03-02"), antes=21, depois=30).set_index(
        ["janela", "grupo", "horizonte"])
    assert t.loc[("troca", SAI, "todos"), "itens"] == 1 and t.loc[("troca", SAI, "todos"), "expansao"] == "B"
    assert t.loc[("troca", SAI, "todos"), "vies_mediano"] == pytest.approx(0.25)   # previu 100, foi 80
    assert t.loc[("troca", ANTERIORES, "todos"), "itens"] == 1
    assert t.loc[("resto", ENTRA, "todos"), "itens"] == 1                         # item 3: 49 dias depois
    assert t.loc[("troca", "todos", "h7"), "alvos"] == 2


# ------------------------------------------------------------------------- etapa 2e: perda MAE e taxa
def test_perda_mae_mascarada() -> None:
    keras = pytest.importorskip("keras")
    from treinar import criar_perdas

    perda, _ = criar_perdas("mae", 3)
    y_pred = np.array([[0.1, 0.5, -2.0]], dtype="float32")
    y = np.array([[0.0, 0.4, 1.0]], dtype="float32")
    m = np.array([[1, 1, 0]], dtype="float32")
    assert float(np.asarray(perda(np.concatenate([y, m], 1), y_pred))[0]) == pytest.approx(0.1, rel=1e-4)
    um = np.ones_like(y)
    ref = float(np.asarray(keras.losses.MeanAbsoluteError(reduction=None)(y, y_pred))[0])
    assert float(np.asarray(perda(np.concatenate([y, um], 1), y_pred))[0]) == pytest.approx(ref, rel=1e-5)
    with pytest.raises(ValueError):
        criar_perdas("quantil", 3)


def test_treino_curto_com_mae_e_reducao_da_taxa(preparado: tuple[Resultado, Path]) -> None:
    pytest.importorskip("keras")
    import json

    from treinar import main

    _, pasta = preparado
    assert main(["--pasta", str(pasta), "--nome", "t2e", "--perda", "mae", "--reduzir-taxa", "--paciencia-taxa", "1",
                 "--fator-taxa", "0.5", "--epocas", "4", "--paciencia", "4", "--unidades", "4", "--lote", "64",
                 "--amostras-por-epoca", "256", "--amostras-validacao", "256", "--semente", "1"]) == 0
    destino = pasta / "modelos" / "t2e"
    info = json.loads((destino / "treino.json").read_text(encoding="utf-8"))
    assert info["parametros"]["perda"] == "mae" and info["parametros"]["reduzir_taxa"] is True
    assert info["taxa_final"] <= 1e-3 + 1e-9
    assert (destino / "previsoes_validacao.parquet").exists()


def test_rn10_exige_minimo_de_dias_avaliados(preparado: tuple[Resultado, Path]) -> None:
    """Um item com menos de 30 dias de previsões avaliadas fica bloqueado por avaliação insuficiente, mesmo perfeito."""
    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    item = jan["item_id"].iloc[0]
    curto = jan[jan["item_id"] == item].sort_values("data_origem").head(20)   # 20 dias desse item
    resto = jan[jan["item_id"] != item]
    sel = pd.concat([curto, resto])
    perfeito = sel[dados.colunas_alvo()].to_numpy("float64")
    av = avaliar(dados, "validacao", sel["id_amostra"].to_numpy(), perfeito)
    linha = av.por_item.set_index("item_id").loc[item]
    assert linha["dias_avaliados"] == 20
    assert linha["situacao"] == "Bloqueada" and linha["motivo_bloqueio"] == "avaliação insuficiente"
    assert av.resumo["itens_com_avaliacao_insuficiente"] == 1
    sem = avaliar(dados, "validacao", sel["id_amostra"].to_numpy(), perfeito, minimo_dias=0)
    assert sem.resumo["itens_liberados_rn10"] == av.resumo["itens_liberados_rn10_sem_minimo_de_dias"]
    assert set(av.por_item["motivo_bloqueio"]) <= {"", "avaliação insuficiente", "acima do limiar", "não supera o ingênuo"}


# ------------------------------------------------------------------------- etapa 2f: análises da generalização
def test_generalizacao_por_liquidez_e_por_novidade(com_reserva: tuple[Resultado, Path], tmp_path: Path) -> None:
    from avaliar import gravar
    from generalizacao import FAIXAS_LIQUIDEZ, main, por_novidade

    _, pasta = com_reserva
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    av = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64"))
    gravar(av, pasta, "g2f")
    arq = pasta / "avaliacao_validacao_g2f_itens.csv"

    saida = tmp_path / "liq.csv"
    assert main(["liquidez", "--avaliacao", str(arq), "--saida", str(saida)]) == 0
    liq = pd.read_csv(saida)
    assert liq["itens"].sum() == av.resumo["itens"]                       # cada item cai em uma faixa
    assert set(liq["faixa"]) <= {f[2] for f in FAIXAS_LIQUIDEZ} | {"sem quantidade"}

    com_treino = set(dados.janelas("treino")["item_id"])
    tab = por_novidade(pd.read_csv(arq), com_treino)
    total = tab[tab["tem_amostra_de_treino"] == "todos"].iloc[0]
    assert total["itens"] == av.resumo["itens"]
    sem = set(av.por_item["item_id"]) - com_treino
    linhas_sem = tab[tab["tem_amostra_de_treino"].astype(str) == "False"]
    assert int(linhas_sem["itens"].sum()) == len(sem)


# ------------------------------------------------------------------------------ etapa 2g: melhorias baratas
def _tipos(modelo) -> list[str]:  # type: ignore[no-untyped-def]
    return [type(c).__name__ for c in modelo.layers]


def test_ativacao_padrao_mantem_a_rede(preparado: tuple[Resultado, Path]) -> None:
    """Sem --ativacao, a rede é a da configuração final: Dense(32, relu), sem camada a mais."""
    keras = pytest.importorskip("keras")
    from ativacoes import camada_densa
    from treinar import construir_modelo

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    padrao = construir_modelo(dados, 4, 0.2, 1e-3, "mae")
    relu = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "relu")
    assert _tipos(padrao) == _tipos(relu)
    assert not any(isinstance(c, keras.layers.LeakyReLU) for c in padrao.layers)
    assert camada_densa(padrao).get_config()["activation"] == "relu"
    assert padrao.count_params() == relu.count_params()


def test_ativacao_leaky_e_gelu_constroem(preparado: tuple[Resultado, Path]) -> None:
    keras = pytest.importorskip("keras")
    import json

    from ativacoes import camada_densa
    from treinar import INCLINACAO_LEAKY, construir_modelo, main

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    relu = construir_modelo(dados, 4, 0.2, 1e-3, "mae")
    leaky = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "leaky_relu")
    gelu = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "gelu")
    camada = [c for c in leaky.layers if isinstance(c, keras.layers.LeakyReLU)]
    assert len(camada) == 1 and camada[0].get_config()["negative_slope"] == pytest.approx(INCLINACAO_LEAKY)
    assert camada_densa(leaky).get_config()["activation"] == "linear"
    assert camada_densa(gelu).get_config()["activation"] == "gelu"
    assert relu.count_params() == leaky.count_params() == gelu.count_params()  # a ativação não tem parâmetros
    with pytest.raises(ValueError):
        construir_modelo(dados, 4, 0.2, 1e-3, "mae", "tanh")

    assert main(["--pasta", str(pasta), "--nome", "t2g", "--ativacao", "leaky_relu", "--epocas", "1", "--unidades",
                 "4", "--lote", "64", "--amostras-por-epoca", "256", "--amostras-validacao", "256"]) == 0
    info = json.loads((pasta / "modelos" / "t2g" / "treino.json").read_text(encoding="utf-8"))
    assert info["parametros"]["ativacao"] == "leaky_relu"
    recarregado = keras.models.load_model(pasta / "modelos" / "t2g" / "modelo.keras", compile=False)
    assert any(isinstance(c, keras.layers.LeakyReLU) for c in recarregado.layers)


def test_media_de_previsoes_iguais_e_a_propria(tmp_path: Path) -> None:
    from avaliar import salvar_previsoes
    from combinar import main, media

    rng = np.random.default_rng(3)
    ids = np.array([5, 1, 3, 2], dtype=np.int64)
    yhat = rng.normal(size=(4, 7))
    salvar_previsoes(ids, yhat, tmp_path / "a.parquet")
    ordem = np.array([2, 0, 3, 1])
    salvar_previsoes(ids[ordem], yhat[ordem], tmp_path / "b.parquet")  # mesmas amostras, outra ordem
    salvar_previsoes(ids, yhat + 2.0, tmp_path / "c.parquet")
    salvar_previsoes(ids[:3], yhat[:3], tmp_path / "d.parquet")

    por_id = np.argsort(ids)
    m_ids, m = media([tmp_path / "a.parquet", tmp_path / "b.parquet"])
    assert np.array_equal(m_ids, ids[por_id]) and np.allclose(m, yhat[por_id])
    _, m = media([tmp_path / "a.parquet", tmp_path / "c.parquet"])
    assert np.allclose(m, yhat[por_id] + 1.0)
    with pytest.raises(ValueError):
        media([tmp_path / "a.parquet", tmp_path / "d.parquet"])
    with pytest.raises(ValueError):
        media([tmp_path / "a.parquet"])
    assert main(["media", "--nome", "ens", "--saida", str(tmp_path / "comb"),
                 "--previsoes", str(tmp_path / "a.parquet"), str(tmp_path / "b.parquet")]) == 0
    assert np.allclose(pd.read_parquet(tmp_path / "comb" / "ens.parquet").filter(like="yhat_").to_numpy(),
                       yhat[por_id])


def test_encolher_alfa_1_e_o_modelo_e_alfa_0_e_o_ingenuo(preparado: tuple[Resultado, Path]) -> None:
    from combinar import encolher

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    yhat = jan[dados.colunas_alvo()].to_numpy("float64")
    H = dados.horizonte
    assert np.allclose(encolher(yhat, [1.0] * H, dados.normalizacao), yhat)
    zero = encolher(yhat, [0.0] * H, dados.normalizacao)
    alvo = dados.normalizacao["alvo"]
    assert np.allclose(zero, (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"]))  # = avaliar.py --ingenuo
    det = avaliar(dados, "validacao", jan["id_amostra"].to_numpy(), zero).detalhe
    assert (det["preco_previsto"] == det["preco_base"]).all()


def test_encolher_escolhe_alfa_so_na_primeira_metade(preparado: tuple[Resultado, Path], tmp_path: Path) -> None:
    """Uma previsão com o dobro do log-retorno real é corrigida por α = 0,5 em todos os horizontes; alterar as
    previsões da 2ª metade não muda os α, e a 2ª metade só tem amostras com todos os dias previstos depois do meio."""
    import json

    from avaliar import desnormalizar, salvar_previsoes
    from combinar import main

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao")
    alvo = dados.normalizacao["alvo"]
    media_alvo, desvio = np.asarray(alvo["media"]), np.asarray(alvo["desvio"])
    dobro = (2.0 * desnormalizar(jan[dados.colunas_alvo()].to_numpy("float64"), dados.normalizacao)
             - media_alvo) / desvio
    ids = jan["id_amostra"].to_numpy()
    salvar_previsoes(ids, dobro, tmp_path / "dobro.parquet")
    args = ["encolher", "--pasta", str(pasta), "--nome", "enc_t", "--saida", str(tmp_path / "comb")]
    assert main(args + ["--previsoes", str(tmp_path / "dobro.parquet")]) == 0
    info = json.loads((tmp_path / "comb" / "enc_t.json").read_text(encoding="utf-8"))
    assert info["alfa"] == [0.5] * dados.horizonte
    n = info["amostras"]
    assert n["primeira_metade"] > 0 and n["segunda_metade"] > 0
    assert n["primeira_metade"] + n["segunda_metade"] + n["atravessam_o_meio"] == len(jan)

    meio = pd.Timestamp(info["meio"])
    seg = pd.read_parquet(tmp_path / "comb" / "enc_t.parquet")
    origem = jan.set_index("id_amostra").loc[seg["id_amostra"], "data_origem"]
    assert (pd.to_datetime(origem) + pd.Timedelta(days=1) >= meio).all()
    ref2 = pd.read_parquet(tmp_path / "comb" / "ref2_t.parquet")
    assert np.allclose(ref2.filter(like="yhat_").to_numpy(),
                       pd.DataFrame(dobro, index=ids).loc[ref2["id_amostra"]].to_numpy())
    ing2 = pd.read_parquet(tmp_path / "comb" / "ing2.parquet").filter(like="yhat_").to_numpy()
    assert np.allclose(ing2, (0.0 - media_alvo) / desvio)

    na_segunda = (pd.to_datetime(jan["data_origem"]) + pd.Timedelta(days=1) >= meio).to_numpy()
    alterado = dobro.copy()
    alterado[na_segunda] *= 3.0
    salvar_previsoes(ids, alterado, tmp_path / "alterado.parquet")
    assert main(args + ["--nome", "enc_t2", "--previsoes", str(tmp_path / "alterado.parquet")]) == 0
    info2 = json.loads((tmp_path / "comb" / "enc_t2.json").read_text(encoding="utf-8"))
    assert info2["alfa"] == info["alfa"] and info2["mdape_primeira_metade"] == info["mdape_primeira_metade"]


def test_ativacoes_conta_amostras_sem_unidade_ativa(preparado: tuple[Resultado, Path]) -> None:
    """Com todas as pré-ativações negativas, toda amostra fica sem unidade ativa e, com a ReLU, a saída é o viés da
    camada `y` para qualquer item."""
    pytest.importorskip("keras")
    from ativacoes import camada_densa, pre_ativacoes, resumir
    from treinar import construir_modelo

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao").head(300)
    modelo = construir_modelo(dados, 4, 0.2, 1e-3, "mae")
    densa = camada_densa(modelo)
    pesos, vies = densa.get_weights()
    densa.set_weights([np.zeros_like(pesos), np.full_like(vies, -1.0)])
    morta = resumir(pre_ativacoes(modelo, dados, jan))
    assert morta["amostras"] == 300 and morta["fracao_sem_unidade_ativa"] == 1.0
    assert morta["unidades_nunca_ativas"] == morta["unidades"] == 32
    t = dados.tensores(jan)
    saida = modelo.predict_on_batch({"X_seq": t["X_seq"], "X_est": t["X_est"], "X_cat": t["X_cat"]})
    assert np.allclose(saida, modelo.get_layer("y").get_weights()[1][None, :])
    densa.set_weights([np.zeros_like(pesos), np.full_like(vies, 1.0)])
    viva = resumir(pre_ativacoes(modelo, dados, jan))
    assert viva["amostras_sem_unidade_ativa"] == 0 and viva["unidades_nunca_ativas"] == 0


# ------------------------------------------------------------------------- etapa 2h: calendário dos dias previstos
def _eventos(*linhas: dict[str, object]) -> pd.DataFrame:
    return _padronizar_eventos(pd.DataFrame([{"versao": None, "data_fim": None, "regiao": "GLOBAL", **ln}
                                             for ln in linhas]))


def test_calendario_futuro_desligado_mantem_a_rede(preparado: tuple[Resultado, Path]) -> None:
    pytest.importorskip("keras")
    from calendario_futuro import COLUNAS_FUTURAS
    from treinar import construir_modelo

    _, pasta = preparado
    dados = DadosPreparados(pasta)
    padrao = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "gelu")
    sem = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "gelu", None)
    com = construir_modelo(dados, 4, 0.2, 1e-3, "mae", "gelu", (dados.horizonte, len(COLUNAS_FUTURAS)))
    assert [i.name for i in padrao.inputs] == ["X_seq", "X_est", "X_cat"]
    assert padrao.count_params() == sem.count_params()
    # o X_fut achatado só acrescenta os pesos dele na camada densa de 32
    assert com.count_params() == padrao.count_params() + dados.horizonte * len(COLUNAS_FUTURAS) * 32
    assert [i.name for i in com.inputs] == ["X_seq", "X_est", "X_cat", "X_fut"]


def test_calendario_futuro_so_usa_o_que_se_sabe_em_d() -> None:
    """RN25: a linha de D só depende do calendário de D+1 a D+7; um patch em D+3 marca h3 a h7, um em D+8 não marca."""
    from calendario_futuro import COLUNA_EVENTO_NO_HORIZONTE, calcular

    d = pd.DatetimeIndex(["2025-03-01"])

    def linha(ev: pd.DataFrame) -> pd.Series:
        return calcular(d, ev, CFG).iloc[0]

    def valores(ln: pd.Series, coluna: str) -> list[float]:
        return [float(ln[f"{coluna}_h{h}"]) for h in range(1, 8)]

    base = _eventos({"tipo": "PATCH", "nome": "Patch A", "versao": "1.0.0", "data_inicio": "2025-01-07"})
    ln = linha(base)
    assert valores(ln, "fut_patch") == [0.0] * 7 and not ln[COLUNA_EVENTO_NO_HORIZONTE]
    dias = pd.date_range("2025-03-02", periods=7)
    assert np.allclose(valores(ln, "fut_dia_sin"), np.sin(2 * np.pi * dias.dayofweek.to_numpy() / 7))
    assert np.allclose(valores(ln, "fut_dia_cos"), np.cos(2 * np.pi * dias.dayofweek.to_numpy() / 7))

    patch3 = pd.concat([base, _eventos({"tipo": "PATCH", "nome": "Patch B", "versao": "1.1.0",
                                        "data_inicio": "2025-03-04"})])
    ln = linha(patch3)
    assert valores(ln, "fut_patch") == [0, 0, 1, 1, 1, 1, 1] and ln[COLUNA_EVENTO_NO_HORIZONTE]
    patch8 = pd.concat([base, _eventos({"tipo": "PATCH", "nome": "Patch B", "versao": "1.1.0",
                                        "data_inicio": "2025-03-09"})])
    assert valores(linha(patch8), "fut_patch") == [0.0] * 7

    outros = pd.concat([base, _eventos({"tipo": "TEMPORADA", "nome": "T", "data_inicio": "2025-03-03"},
                                       {"tipo": "EVENTO_SAZONAL", "nome": "F", "data_inicio": "2025-03-06",
                                        "data_fim": "2025-03-07"},
                                       {"tipo": "EXPANSAO", "nome": "E", "data_inicio": "2025-03-07"})])
    ln = linha(outros)
    assert valores(ln, "fut_temporada") == [0, 1, 1, 1, 1, 1, 1]
    assert valores(ln, "fut_evento") == [0, 0, 0, 0, 1, 1, 0]
    assert valores(ln, "fut_expansao") == [0, 0, 0, 0, 0, 1, 1]
    # eventos que começam depois de D+7 não mudam a linha de D
    depois = pd.concat([outros, _eventos({"tipo": "EVENTO_SAZONAL", "nome": "G", "data_inicio": "2025-03-09",
                                          "data_fim": "2025-03-20"},
                                         {"tipo": "TEMPORADA", "nome": "T2", "data_inicio": "2025-03-10"},
                                         {"tipo": "EXPANSAO", "nome": "E2", "data_inicio": "2025-03-12"})])
    pd.testing.assert_series_equal(linha(depois), ln)
    with pytest.raises(ValueError, match="RN25"):  # um patch a mais de 14 dias ainda não é conhecido em D
        calcular(d, base, replace(CFG, horizonte=15))


def test_calendario_futuro_confere_as_variaveis_da_base(preparado: tuple[Resultado, Path],
                                                        sinteticos: dict[str, pd.DataFrame]) -> None:
    from calendario_futuro import conferir

    _, pasta = preparado
    eventos = _padronizar_eventos(sinteticos["eventos"])
    assert conferir(pasta, eventos, CFG)["diferencas"] == 0
    alterado = eventos.copy()
    i = alterado.index[alterado["tipo"] == "PATCH"][3]
    alterado.loc[i, "data_inicio"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="não batem"):
        conferir(pasta, alterado, CFG)


def test_calendario_futuro_treina_e_preve(preparado: tuple[Resultado, Path], sinteticos: dict[str, pd.DataFrame],
                                          tmp_path: Path) -> None:
    keras = pytest.importorskip("keras")
    import json
    import shutil

    from calendario_futuro import CalendarioFuturo, gerar
    from treinar import main, prever

    _, pasta = preparado
    info = gerar(pasta, _padronizar_eventos(sinteticos["eventos"]), tmp_path / "cal", "teste")
    assert info["conferencia"]["diferencas"] == 0
    assert info["amostras_com_valor_diferente_de_zero"]["validacao"]["fut_patch"] > 0
    arquivo = tmp_path / "cal" / "calendario_futuro.parquet"
    assert main(["--pasta", str(pasta), "--nome", "t2h", "--ativacao", "gelu", "--calendario-futuro", str(arquivo),
                 "--epocas", "1", "--unidades", "4", "--lote", "64", "--amostras-por-epoca", "256",
                 "--amostras-validacao", "256"]) == 0
    destino = pasta / "modelos" / "t2h"
    t = json.loads((destino / "treino.json").read_text(encoding="utf-8"))
    assert t["parametros"]["calendario_futuro"] == str(arquivo) and t["previu_teste"] is False
    assert t["calendario_futuro"]["assinatura"] == info["assinatura"] and t["calendario_futuro"]["formato"] == [7, 6]

    dados = DadosPreparados(pasta)
    jan = dados.janelas("validacao").head(50)
    modelo = keras.models.load_model(destino / "modelo.keras", compile=False)
    cal = CalendarioFuturo.carregar(arquivo, pasta, dados.horizonte)
    ids, yhat = prever(modelo, dados, jan, calendario=cal)
    assert yhat.shape == (len(jan), 7) and np.isfinite(yhat).all()
    gravadas = pd.read_parquet(destino / "previsoes_validacao.parquet").set_index("id_amostra").loc[ids]
    assert np.allclose(gravadas.filter(like="yhat_").to_numpy(), yhat, atol=1e-5)
    with pytest.raises(ValueError):  # sem o calendário, o modelo com X_fut não prevê
        prever(modelo, dados, jan)

    adulterado = tmp_path / "adulterado"
    adulterado.mkdir()
    shutil.copy(arquivo.with_suffix(".json"), adulterado / "calendario_futuro.json")
    tab = pd.read_parquet(arquivo)
    tab.loc[0, "fut_patch_h1"] = 1.0 - tab.loc[0, "fut_patch_h1"]
    tab.to_parquet(adulterado / "calendario_futuro.parquet", index=False)
    with pytest.raises(ValueError, match="assinatura"):
        CalendarioFuturo.carregar(adulterado / "calendario_futuro.parquet", pasta, dados.horizonte)


def test_eventos_no_horizonte_separa_as_amostras(preparado: tuple[Resultado, Path],
                                                 sinteticos: dict[str, pd.DataFrame], tmp_path: Path) -> None:
    from avaliar import main as avaliar_main
    from calendario_futuro import gerar
    from eventos_no_horizonte import analisar, main

    det = pd.DataFrame({"id_amostra": [1, 1, 2, 2, 3, 3], "serie": "s", "item_id": [10, 10, 10, 10, 20, 20],
                        "avaliavel": [True, True, True, False, True, True],
                        "erro_pct": [0.1, 0.3, 0.2, np.nan, 0.4, 0.6],
                        "erro_pct_ingenuo": [0.2, 0.2, 0.4, np.nan, 0.5, 0.5]})
    t = analisar(det, np.array([True, True, False, False, True, True])).set_index("grupo")
    assert t.loc["com evento", "amostras"] == 2 and t.loc["com evento", "alvos"] == 4
    assert t.loc["com evento", "mediana_mdape_por_item"] == pytest.approx(0.35)    # itens: 0,2 e 0,5
    assert t.loc["com evento", "razao_mdape"] == pytest.approx(1.0)
    assert t.loc["sem evento", "alvos"] == 1 and t.loc["sem evento", "razao_mdape"] == pytest.approx(0.5)
    assert t.loc["todos", "alvos"] == 5 and t.loc["todos", "itens"] == 2

    _, pasta = preparado
    gerar(pasta, _padronizar_eventos(sinteticos["eventos"]), tmp_path / "cal")
    assert avaliar_main(["--pasta", str(pasta), "--periodo", "validacao", "--ingenuo", "--rotulo", "ing2h"]) == 0
    assert main(["--pasta", str(pasta), "--calendario", str(tmp_path / "cal" / "calendario_futuro.parquet"),
                 "--detalhe", str(pasta / "avaliacao_validacao_ing2h_detalhe.parquet"), "--rotulo", "ing2h"]) == 0
    r = pd.read_csv(pasta / "eventos_horizonte_ing2h.csv").set_index("grupo")
    assert r.loc["com evento", "amostras"] > 0 and r.loc["sem evento", "amostras"] > 0
    assert r.loc["com evento", "amostras"] + r.loc["sem evento", "amostras"] == r.loc["todos", "amostras"]
    assert np.allclose(r["razao_mdape"], 1.0)  # o ingênuo contra ele mesmo


# ------------------------------------------------------------------------- etapa 2i: subclasse dentro da classe
CFG_PAR = replace(CFG, subclasse_por_classe=True)


def _mudar_classe(dados: dict[str, pd.DataFrame], classe: int, subclasse: int,
                  nova_classe: int) -> tuple[dict[str, pd.DataFrame], set[int], set[int]]:
    """Metade dos itens de (classe, subclasse) passa para `nova_classe`: o mesmo código de subclasse fica em duas
    classes, como na API da Blizzard. Devolve os dados e os itens que mudaram e os que ficaram."""
    dados = {k: v.copy() for k, v in dados.items()}
    itens = dados["itens"]
    ids = itens.loc[(itens["classe_id"] == classe) & (itens["subclasse_id"] == subclasse), "item_id"].to_numpy()
    mudaram = set(int(i) for i in ids[::2])
    itens.loc[itens["item_id"].isin(mudaram), "classe_id"] = nova_classe
    return dados, mudaram, set(int(i) for i in ids) - mudaram


@pytest.fixture(scope="module")
def bases_2i(sinteticos: dict[str, pd.DataFrame], tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """A subclasse 5 em duas classes (4 e 7), preparada com a chave antiga e com o par."""
    dados, na_4, na_7 = _mudar_classe(sinteticos, 7, 5, 4)
    off = preparar(entrada_de(dados), CFG, filtro_liquidez=False, **CORTES)
    on = preparar(entrada_de(dados), CFG_PAR, filtro_liquidez=False, **CORTES)
    pasta_off, pasta_on = tmp_path_factory.mktemp("off2i"), tmp_path_factory.mktemp("on2i")
    salvar(off, pasta_off)
    salvar(on, pasta_on)
    return {"dados": dados, "na_4": na_4, "na_7": na_7, "off": off, "on": on, "pasta_off": pasta_off,
            "pasta_on": pasta_on}


def test_subclasse_por_classe_desligada_mantem_a_base(sinteticos: dict[str, pd.DataFrame],
                                                      preparado: tuple[Resultado, Path]) -> None:
    """Desligada (o padrão), a chave é o código da subclasse, e as bases sem o campo na configuração mantêm a
    assinatura. Sem código repetido entre classes, ligar a opção não muda a variável 6, só a assinatura."""
    import copy

    from dataset import assinatura_normalizacao
    from preparar_dados import chave_da_subclasse

    res, _ = preparado
    itens = _padronizar_itens(sinteticos["itens"])
    assert chave_da_subclasse(itens["classe_id"], itens["subclasse_id"], CFG).equals(
        itens["subclasse_id"].rename("subclasse_chave"))
    assert res.normalizacao["config"]["subclasse_por_classe"] is False
    sem_campo = copy.deepcopy(res.normalizacao)
    del sem_campo["config"]["subclasse_por_classe"]
    assert assinatura_normalizacao(sem_campo) == res.normalizacao["assinatura"]

    ligada = preparar(entrada_de(sinteticos), CFG_PAR, filtro_liquidez=False, **CORTES)
    assert np.array_equal(ligada.linhas_normalizadas["f_retorno_subclasse"],
                          res.linhas_normalizadas["f_retorno_subclasse"])
    assert ligada.normalizacao["constantes"] == res.normalizacao["constantes"]
    assert ligada.normalizacao["assinatura"] != res.normalizacao["assinatura"]


def test_subclasse_por_classe_separa_classes_diferentes(bases_2i: dict[str, object]) -> None:
    """Comida e bebida (0, 5) não entra no índice do tecido (7, 5): com o par, cada um só vê a própria subclasse da
    própria classe, e os dois ganham índices de subclasse diferentes. O resto da base não muda."""
    from preparar_dados import chave_da_subclasse, retorno_da_subclasse

    linhas = pd.DataFrame({"regiao": "US", "data": pd.Timestamp("2025-01-01"), "observado": True,
                           "log_return": [0.10, 0.30, -0.20], "quantidade": [1.0, 3.0, 1.0],
                           "classe_id": [7.0, 7.0, 0.0], "subclasse_id": [5.0, 5.0, 5.0]})
    sozinho = retorno_da_subclasse(linhas, chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], CFG))
    par = retorno_da_subclasse(linhas, chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], CFG_PAR))
    assert sozinho[0] == pytest.approx((0.30 * 3 - 0.20 * 1) / 4)  # o tecido misturado com a comida
    assert par[0] == pytest.approx(0.30) and par[1] == pytest.approx(0.10)
    assert np.isnan(par[2])  # a comida não tem outro item da mesma classe e subclasse no dia

    off, on = bases_2i["off"], bases_2i["on"]
    assert "5" in off.normalizacao["vocabulario"]["subclasse_id"]
    voc = on.normalizacao["vocabulario"]["subclasse_id"]
    assert {"4005", "7005"} <= set(voc) and "5" not in voc

    def indices(res: Resultado, ids: set[int]) -> set[int]:
        n = res.linhas_normalizadas
        return set(n.loc[n["item_id"].isin(ids), "subclasse_idx"].unique())

    na_4, na_7 = bases_2i["na_4"], bases_2i["na_7"]
    assert len(indices(off, na_4 | na_7)) == 1
    assert indices(on, na_4).isdisjoint(indices(on, na_7))
    n_off, n_on = off.linhas_normalizadas, on.linhas_normalizadas
    v6 = n_off["item_id"].isin(na_4 | na_7)
    assert not np.allclose(n_off.loc[v6, "f_retorno_subclasse"], n_on.loc[v6, "f_retorno_subclasse"])
    resto = [c for c in n_off.columns if c not in ("f_retorno_subclasse", "subclasse_idx")]
    pd.testing.assert_frame_equal(n_off[resto], n_on[resto])
    pd.testing.assert_frame_equal(off.janelas, on.janelas)
    assert on.normalizacao["config"]["subclasse_por_classe"] is True
    assert on.normalizacao["assinatura"] != off.normalizacao["assinatura"]


def test_subclasse_por_classe_par_desconhecido_vira_zero(sinteticos: dict[str, pd.DataFrame]) -> None:
    """Um par que a versão do modelo não viu no treino vira subclasse desconhecida (0), mesmo com a classe e o código
    da subclasse conhecidos separadamente. Com a chave antiga, o código sozinho seria reconhecido."""
    dados, novos, _ = _mudar_classe(sinteticos, 7, 8, 4)  # (4, 8) não existe; a classe 4 e a subclasse 8 existem
    for cfg in (CFG, CFG_PAR):
        res_a = preparar(entrada_de(dados), cfg, filtro_liquidez=False, excluir_itens=novos, **CORTES)
        res_b = preparar(entrada_de(dados), cfg, filtro_liquidez=False, normalizacao_base=res_a.normalizacao,
                         excluir_itens=set(res_a.itens["item_id"]))
        nb = res_b.linhas_normalizadas
        assert set(nb["item_id"]) == novos and len(res_b.janelas[res_b.janelas["periodo"] == "validacao"]) > 0
        assert (nb["classe_idx"] > 0).all()
        if cfg.subclasse_por_classe:
            assert "4008" not in res_a.normalizacao["vocabulario"]["subclasse_id"]
            assert (nb["subclasse_idx"] == 0).all()
        else:
            assert (nb["subclasse_idx"] > 0).all()


def test_refazer_subclasse_com_a_chave_antiga_reproduz_a_base(bases_2i: dict[str, object], tmp_path: Path) -> None:
    """A conferência: com a chave da base de origem, o refazer_subclasse.py reproduz a variável 6, a constante, o
    vocabulário e os índices gravados. Um item que mudou de subclasse depois da preparação faz a conferência falhar,
    e nada é gravado."""
    from refazer_subclasse import refazer

    itens = _padronizar_itens(bases_2i["dados"]["itens"])
    info = refazer(bases_2i["pasta_off"], itens, tmp_path / "ok")
    assert info["conferencia"]["diferencas"] == 0
    assert info["contagens"]["itens_com_codigo_compartilhado"] == len(bases_2i["na_4"] | bases_2i["na_7"])

    alterado = itens.copy()
    i = alterado.index[alterado["subclasse_id"] == 1][0]
    alterado.loc[i, "subclasse_id"] = 8
    with pytest.raises(ValueError, match="não batem"):
        refazer(bases_2i["pasta_off"], alterado, tmp_path / "falha")
    assert not (tmp_path / "falha").exists()
    with pytest.raises(ValueError, match="já usa"):
        refazer(tmp_path / "ok", itens, tmp_path / "de_novo")


def test_refazer_subclasse_so_muda_a_variavel_6_e_a_subclasse(bases_2i: dict[str, object], tmp_path: Path) -> None:
    """A cópia refeita é a mesma base que a preparação com o par daria: mesmas janelas e mesmas linhas, com só a
    variável 6 e o índice da subclasse diferentes da base de origem, e a mesma assinatura da preparação com o par."""
    import json

    from refazer_subclasse import main

    pasta_off, pasta_on, saida = bases_2i["pasta_off"], bases_2i["pasta_on"], tmp_path / "refeita"
    bases_2i["dados"]["itens"].to_csv(tmp_path / "itens.csv", index=False)
    assert main(["--csv", str(tmp_path), "--pasta", str(pasta_off), "--saida", str(saida)]) == 0

    for p in PERIODOS:
        pd.testing.assert_frame_equal(pd.read_parquet(saida / f"janelas_{p}.parquet"),
                                      pd.read_parquet(pasta_off / f"janelas_{p}.parquet"))
    pd.testing.assert_frame_equal(pd.read_parquet(saida / "linhas_originais.parquet"),
                                  pd.read_parquet(pasta_off / "linhas_originais.parquet"))
    refeita = pd.read_parquet(saida / "linhas_normalizadas.parquet")
    pd.testing.assert_frame_equal(refeita, pd.read_parquet(pasta_on / "linhas_normalizadas.parquet"))
    origem = pd.read_parquet(pasta_off / "linhas_normalizadas.parquet")
    resto = [c for c in origem.columns if c not in ("f_retorno_subclasse", "subclasse_idx")]
    pd.testing.assert_frame_equal(refeita[resto], origem[resto])

    n_refeita = json.loads((saida / "normalizacao.json").read_text(encoding="utf-8"))
    n_on = json.loads((pasta_on / "normalizacao.json").read_text(encoding="utf-8"))
    for k in ("constantes", "vocabulario", "alvo", "variaveis", "nivel_item", "assinatura"):
        assert n_refeita[k] == n_on[k], k
    assert n_refeita["subclasse_refeita"]["assinatura_base"] == bases_2i["off"].normalizacao["assinatura"]
    assert (saida / "subclasses.csv").exists()
