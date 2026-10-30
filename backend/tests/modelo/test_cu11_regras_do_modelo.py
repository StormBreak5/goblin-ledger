"""
Plano de testes do CU11 – regras do modelo preditivo (RN03, RN10, RN24, RN25, RN27) e passo 2 do C1, portados de
`estudos/lstm/tests/test_estudo.py`. Usam dados sintéticos em memória, sem banco e sem TensorFlow.
"""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

pytest.importorskip("pandas")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sinteticos import gerar, serie_constante  # noqa: E402
from src.ml.avaliacao import avaliar  # noqa: E402
from src.ml.configuracao import PERIODOS, ConfigModelo  # noqa: E402
from src.ml.dados import Entrada, padronizar_eventos, padronizar_itens, padronizar_precos  # noqa: E402
from src.ml.dataset import DadosPreparados, assinatura_normalizacao, conferir_compatibilidade  # noqa: E402
from src.ml.preparacao import (BasePreparada, calcular_cortes, chave_da_subclasse, preparar,  # noqa: E402
                               retorno_da_subclasse, rn03_por_serie, variaveis_de_calendario)
from src.ml.selecao import precos_da_regiao, selecionar  # noqa: E402

CFG = ConfigModelo()
CORTES = {"corte_validacao": "2025-07-14", "corte_teste": "2026-02-24"}


def entrada_de(dados: dict[str, pd.DataFrame], aptos: set[int] | None = None) -> Entrada:
    precos = padronizar_precos(dados["precos"])
    return Entrada(precos=precos, itens=padronizar_itens(dados.get("itens")),
                   eventos=padronizar_eventos(dados.get("eventos")),
                   regiao_da_serie={s: "US" for s in precos["serie"].unique()},
                   aptos=set(precos["item_id"].astype(int)) if aptos is None else aptos)


def preparar_dados(dados: dict[str, pd.DataFrame], fora_do_treino: frozenset[tuple[str, int]] = frozenset(),
                   excluir: set[int] | None = None, **kwargs) -> BasePreparada:
    entrada = entrada_de(dados)
    precos = precos_da_regiao(entrada, "US")
    if excluir:
        precos = precos[~precos["item_id"].isin(excluir)]
    return preparar(entrada, precos, CFG, fora_do_treino, **kwargs)


def chaves(dados: dict[str, pd.DataFrame], itens: set[int]) -> frozenset[tuple[str, int]]:
    p = dados["precos"].drop_duplicates(["serie", "item_id"])
    return frozenset((str(s), int(i)) for s, i in zip(p["serie"], p["item_id"]) if int(i) in itens)


@pytest.fixture(scope="module")
def sinteticos() -> dict[str, pd.DataFrame]:
    return gerar(n_itens=24, semente=11)


@pytest.fixture(scope="module")
def preparado(sinteticos: dict[str, pd.DataFrame]) -> BasePreparada:
    return preparar_dados(sinteticos, **CORTES)


def serie_simples(precos_por_item: dict[int, list[float | None]]) -> dict[str, pd.DataFrame]:
    linhas = []
    for item, precos in precos_por_item.items():
        for d, p in zip(pd.date_range("2024-01-01", periods=len(precos)), precos):
            if p is not None:
                linhas.append({"serie": "32512", "item_id": item, "data": d, "preco": p, "quantidade": 100})
    return {"precos": pd.DataFrame(linhas)}


def _rn03(precos: list[float | None]) -> tuple[np.ndarray, np.ndarray]:
    preco = np.array([np.nan if p is None else p for p in precos], dtype="float64")
    inicio = np.zeros(len(preco), dtype=bool)
    inicio[0] = True
    return rn03_por_serie(preco, inicio, CFG)


def _zero_normalizado(dados: DadosPreparados) -> np.ndarray:
    """Saída do modelo que corresponde a log-retorno 0: o próprio modelo ingênuo."""
    alvo = dados.normalizacao["alvo"]
    return (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"])


# ------------------------------------------------------------------------------------------------------- RN24
def test_rn24_ida_e_volta_recupera_o_preco(preparado: BasePreparada) -> None:
    """Passando o próprio y verdadeiro pela desnormalização, o preço reconstruído é o da linha original (Cobre, RN01);
    log-retorno 0 reproduz o preço base (ingênuo). As entradas da LSTM ficam entre −1 e 1."""
    dados = DadosPreparados(preparado)
    jan = dados.janelas("teste")
    av = avaliar(dados, "teste", jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64"))
    ok = av.detalhe[av.detalhe["avaliavel"]]
    assert len(ok) > 0 and ok["erro_pct"].max() < 1e-5

    ingenuo = avaliar(dados, "teste", jan["id_amostra"].to_numpy(), np.tile(_zero_normalizado(dados), (len(jan), 1)))
    assert (ingenuo.detalhe["preco_previsto"] == ingenuo.detalhe["preco_base"]).all()

    t = dados.tensores(dados.janelas("treino").head(64))
    assert t["X_seq"].shape == (64, CFG.janela, 16) and t["X_est"].shape == (64, 4) and t["X_cat"].shape == (64, 2)
    assert np.isfinite(t["X_seq"]).all() and (np.abs(t["X_seq"]) <= 1.0 + 1e-6).all()


def test_rn24_calculos_por_item() -> None:
    """O primeiro dia de um item não pode usar o último preço do item anterior."""
    base = preparar_dados(serie_simples({1: [10.0] * 80, 2: [5_000_000.0] * 80}),
                          corte_validacao="2024-03-10", corte_teste="2024-03-15")
    n = base.normalizadas
    primeiro_do_item_2 = n.index[n["item_id"] == 2][0]
    assert pd.isna(n.loc[primeiro_do_item_2, "f_log_return"])
    assert not base.originais.loc[primeiro_do_item_2, "descartado_rn03"]
    assert (n.loc[n["item_id"] == 2, "f_log_return"].dropna() == 0).all()


def test_rn24_normalizacao_de_outra_versao_em_itens_fora_do_treino(sinteticos: dict[str, pd.DataFrame],
                                                                   preparado: BasePreparada) -> None:
    """Prever um item com uma versão já treinada: a base dos itens novos recebe a normalização da versão (cortes,
    constantes, vocabulário, alvo). Uma subclasse que a versão nunca viu vira a categoria desconhecida (0)."""
    mesma = preparar_dados(sinteticos, normalizacao_base=preparado.normalizacao)
    assert mesma.normalizacao["assinatura"] == preparado.normalizacao["assinatura"]
    pd.testing.assert_frame_equal(mesma.normalizadas, preparado.normalizadas)
    pd.testing.assert_frame_equal(mesma.janelas, preparado.janelas)

    itens = sinteticos["itens"]
    so_em_b = set(itens.loc[itens["subclasse_id"] == 8, "item_id"])
    b_ids = so_em_b | (set(itens["item_id"].iloc[::4]) - so_em_b)
    a = preparar_dados(sinteticos, excluir=b_ids, **CORTES)
    b = preparar_dados(sinteticos, excluir=set(itens["item_id"]) - b_ids, normalizacao_base=a.normalizacao)
    assert set(b.itens["item_id"]) == b_ids
    for k in ("constantes", "nivel_item", "vocabulario", "alvo", "variaveis"):
        assert b.normalizacao[k] == a.normalizacao[k]
    assert b.normalizacao["normalizacao_de"]["assinatura"] == a.normalizacao["assinatura"]
    assert "7008" not in a.normalizacao["vocabulario"]["subclasse_id"]  # o par (7, 8)
    assert (b.normalizadas.loc[b.normalizadas["item_id"].isin(so_em_b), "subclasse_idx"] == 0).all()
    assert len(b.janelas[b.janelas["periodo"] == "teste"]) > 0
    conferir_compatibilidade(a.normalizacao, b.normalizacao)
    with pytest.raises(ValueError):
        conferir_compatibilidade(preparado.normalizacao, b.normalizacao)


# Variáveis 6 e 15 pelo par (classe, subclasse), da etapa 2i do estudo. As versões treinadas antes usam o código
# sozinho, e o normalizacao.json delas não tem o campo `subclasse_por_classe`.
CFG_ANTIGA = ConfigModelo.de_dict({k: v for k, v in CFG.como_dict().items()
                                   if k not in ("subclasse_por_classe", "ativacao")})


def _mudar_classe(dados: dict[str, pd.DataFrame], classe: int, subclasse: int,
                  nova_classe: int) -> tuple[dict[str, pd.DataFrame], set[int], set[int]]:
    """Metade dos itens de (classe, subclasse) passa para `nova_classe`: o mesmo código de subclasse fica em duas
    classes, como na API da Blizzard. Devolve os dados, os itens que mudaram e os que ficaram."""
    dados = {k: v.copy() for k, v in dados.items()}
    itens = dados["itens"]
    ids = itens.loc[(itens["classe_id"] == classe) & (itens["subclasse_id"] == subclasse), "item_id"].to_numpy()
    mudaram = set(int(i) for i in ids[::2])
    itens.loc[itens["item_id"].isin(mudaram), "classe_id"] = nova_classe
    return dados, mudaram, set(int(i) for i in ids) - mudaram


def _preparar_com(dados: dict[str, pd.DataFrame], cfg: ConfigModelo, excluir: set[int] | None = None,
                  **kwargs) -> BasePreparada:
    entrada = entrada_de(dados)
    precos = precos_da_regiao(entrada, "US")
    if excluir:
        precos = precos[~precos["item_id"].isin(excluir)]
    return preparar(entrada, precos, cfg, **kwargs)


def _indices_da_subclasse(base: BasePreparada, itens: set[int]) -> set[int]:
    n = base.normalizadas
    return set(n.loc[n["item_id"].isin(itens), "subclasse_idx"].unique())


def test_rn24_subclasse_pelo_par_classe_subclasse(sinteticos: dict[str, pd.DataFrame]) -> None:
    """CU11-C1 passo 5 / RN24, variáveis 6 e 15: o tecido (7, 5) e a comida e bebida (0, 5) têm o mesmo código de
    subclasse. Com o par, cada um só entra no índice da própria subclasse da própria classe, e os dois ganham índices de
    subclasse diferentes. O resto da base não muda."""
    linhas = pd.DataFrame({"regiao": "US", "data": pd.Timestamp("2025-01-01"), "observado": True,
                           "log_return": [0.10, 0.30, -0.20], "quantidade": [1.0, 3.0, 1.0],
                           "classe_id": [7.0, 7.0, 0.0], "subclasse_id": [5.0, 5.0, 5.0]})
    sozinho = retorno_da_subclasse(linhas, chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], CFG_ANTIGA))
    par = retorno_da_subclasse(linhas, chave_da_subclasse(linhas["classe_id"], linhas["subclasse_id"], CFG))
    assert sozinho[0] == pytest.approx((0.30 * 3 - 0.20 * 1) / 4)  # o tecido misturado com a comida
    assert par[0] == pytest.approx(0.30) and par[1] == pytest.approx(0.10)
    assert np.isnan(par[2])  # a comida não tem outro item da mesma classe e subclasse no dia

    dados, na_0, na_7 = _mudar_classe(sinteticos, 7, 5, 0)
    antiga, nova = _preparar_com(dados, CFG_ANTIGA, **CORTES), _preparar_com(dados, CFG, **CORTES)
    assert "7005" not in antiga.normalizacao["vocabulario"]["subclasse_id"]
    assert {"5", "7005"} <= set(nova.normalizacao["vocabulario"]["subclasse_id"])  # (0, 5) = 0 × 1000 + 5 e (7, 5)
    assert len(_indices_da_subclasse(antiga, na_0 | na_7)) == 1
    assert _indices_da_subclasse(nova, na_0).isdisjoint(_indices_da_subclasse(nova, na_7))
    na, nn = antiga.normalizadas, nova.normalizadas
    v6 = na["item_id"].isin(na_0 | na_7)
    assert not np.allclose(na.loc[v6, "f_retorno_subclasse"], nn.loc[v6, "f_retorno_subclasse"])
    resto = [c for c in na.columns if c not in ("f_retorno_subclasse", "subclasse_idx")]
    pd.testing.assert_frame_equal(na[resto], nn[resto])
    pd.testing.assert_frame_equal(antiga.janelas, nova.janelas)
    assert nova.normalizacao["config"]["subclasse_por_classe"] is True
    assert nova.normalizacao["assinatura"] != antiga.normalizacao["assinatura"]


def test_rn24_versao_antiga_mantem_o_codigo_da_subclasse(sinteticos: dict[str, pd.DataFrame]) -> None:
    """RN24 (CU11-C2 e C3): o normalizacao.json de uma versão treinada antes da mudança não tem `subclasse_por_classe`
    nem `ativacao`. Ela é lida com o código da subclasse sozinho e a ReLU, e a normalização dela, aplicada de novo,
    reproduz a base e a assinatura que ela gravou."""
    assert (CFG_ANTIGA.subclasse_por_classe, CFG_ANTIGA.ativacao) == (False, "relu")
    assert (CFG.subclasse_por_classe, CFG.ativacao) == (True, "gelu")

    dados, _, _ = _mudar_classe(sinteticos, 7, 5, 0)
    gravada = _preparar_com(dados, CFG_ANTIGA, **CORTES).normalizacao
    sem_campos = copy.deepcopy(gravada)
    for campo in ("subclasse_por_classe", "ativacao"):
        del sem_campos["config"][campo]
    assert assinatura_normalizacao(sem_campos) == gravada["assinatura"]
    assert set(gravada["vocabulario"]["subclasse_id"]) == {"1", "2", "5", "7", "8"}  # os códigos sozinhos

    de_novo = _preparar_com(dados, CFG, normalizacao_base=sem_campos)  # a configuração vem da versão, não do padrão
    assert de_novo.normalizacao["assinatura"] == gravada["assinatura"]
    assert de_novo.normalizacao["vocabulario"] == gravada["vocabulario"]
    assert de_novo.normalizacao["config"]["subclasse_por_classe"] is False


def test_rn24_par_desconhecido_vira_zero(sinteticos: dict[str, pd.DataFrame]) -> None:
    """RN24: um par que a versão do modelo não viu no treino vira subclasse desconhecida (0), mesmo com a classe e o
    código da subclasse conhecidos separadamente. Com o código sozinho, a subclasse seria reconhecida."""
    dados, novos, _ = _mudar_classe(sinteticos, 7, 8, 4)  # (4, 8) não existe; a classe 4 e a subclasse 8 existem
    for cfg in (CFG_ANTIGA, CFG):
        a = _preparar_com(dados, cfg, excluir=novos, **CORTES)
        b = _preparar_com(dados, cfg, excluir=set(a.itens["item_id"]), normalizacao_base=a.normalizacao)
        nb = b.normalizadas
        assert set(nb["item_id"]) == novos and len(b.janelas[b.janelas["periodo"] == "teste"]) > 0
        assert (nb["classe_idx"] > 0).all()
        if cfg.subclasse_por_classe:
            assert "4008" not in a.normalizacao["vocabulario"]["subclasse_id"]
            assert (nb["subclasse_idx"] == 0).all()
        else:
            assert (nb["subclasse_idx"] > 0).all()


# ------------------------------------------------------------------------------------------------------- RN25
def test_rn25_sem_vazamento_do_futuro(sinteticos: dict[str, pd.DataFrame], preparado: BasePreparada) -> None:
    """Alterar os preços da validação e do teste não muda nenhuma constante nem nenhuma linha do treino."""
    alterado = {k: v.copy() for k, v in sinteticos.items()}
    p = alterado["precos"]
    futuro = pd.to_datetime(p["data"]) >= pd.Timestamp(CORTES["corte_validacao"])
    rng = np.random.default_rng(0)
    p.loc[futuro, "preco"] = (p.loc[futuro, "preco"] * rng.uniform(0.2, 5.0, futuro.sum())).round().clip(lower=1)
    p.loc[futuro, "quantidade"] = p.loc[futuro, "quantidade"] * 3
    outra = preparar_dados(alterado, **CORTES)

    na, nb = preparado.normalizacao, outra.normalizacao
    assert na["constantes"] == nb["constantes"]
    assert na["nivel_item"] == nb["nivel_item"] and na["vocabulario"] == nb["vocabulario"]
    assert na["alvo"] == nb["alvo"]
    treino = preparado.normalizadas["periodo"] == "treino"
    pd.testing.assert_frame_equal(preparado.normalizadas[treino], outra.normalizadas[treino])
    ja, jb = (b.janelas[b.janelas["periodo"] == "treino"].reset_index(drop=True) for b in (preparado, outra))
    pd.testing.assert_frame_equal(ja, jb)


def test_rn25_janelas_respeitam_os_cortes(preparado: BasePreparada) -> None:
    """Divisão 70/20/10 por data; nenhuma amostra tem alvos dos dois lados de um corte; a janela não mistura itens."""
    jan, n = preparado.janelas, preparado.normalizadas
    cv, ct = pd.Timestamp(CORTES["corte_validacao"]), pd.Timestamp(CORTES["corte_teste"])
    um, h = pd.Timedelta(days=1), pd.Timedelta(days=CFG.horizonte)
    t, v, te = (jan[jan["periodo"] == p] for p in PERIODOS)
    assert len(t) and len(v) and len(te)
    assert (t["data_origem"] + h < cv).all()
    assert (v["data_origem"] + um >= cv).all() and (v["data_origem"] + h < ct).all()
    assert (te["data_origem"] + um >= ct).all()
    inicio = jan["id_linha_origem"].to_numpy() - CFG.janela + 1
    assert (n["item_id"].to_numpy()[inicio] == jan["item_id"].to_numpy()).all()
    assert n.loc[jan["id_linha_origem"], "apta"].all()

    c = calcular_cortes(pd.DataFrame({"data": pd.date_range("2022-09-01", "2026-10-05")}), CFG)
    total = (c["fim"] - c["inicio"]).days + 1
    assert (c["corte_validacao"] - c["inicio"]).days / total == pytest.approx(0.70, abs=0.002)
    assert (c["corte_teste"] - c["inicio"]).days / total == pytest.approx(0.90, abs=0.002)


def test_rn25_dias_ate_patch_respeita_antecedencia() -> None:
    """Um patch só é conhecido 14 dias antes da data (evento_jogo não guarda a data do anúncio)."""
    eventos = padronizar_eventos(pd.DataFrame([{"tipo": "PATCH", "nome": "Patch", "data_inicio": "2025-01-20"}]))
    datas = pd.DatetimeIndex(["2025-01-01", "2025-01-06", "2025-01-10", "2025-01-19", "2025-01-20", "2025-01-21"])
    v = variaveis_de_calendario(datas, eventos, CFG)
    ate = v["f_dias_ate_patch"].to_numpy()
    assert ate[0] == 1.0                      # 19 dias antes: ainda não anunciado
    assert ate[1] == pytest.approx(14 / 14)   # 14 dias antes
    assert ate[2] == pytest.approx(10 / 14)
    assert ate[3] == pytest.approx(1 / 14)
    assert ate[4] == 1.0 and ate[5] == 1.0    # no dia e depois: não há próximo patch
    desde = v["f_dias_desde_patch"].to_numpy()
    assert desde[4] == 0.0 and desde[5] == pytest.approx(1 / 60)


# ------------------------------------------------------------------------------------------------------- RN03
def test_rn03_descarta_pico_com_ema_dos_aceitos() -> None:
    """O pico isolado é descartado sem contaminar a EMA; dias sem registro são preenchidos por até 3 dias (RN24)."""
    precos: list[float | None] = [100.0] * 30 + [999_990_100.0] + [100.0] * 30  # anúncio de 99.999 ouro num só dia
    ema, descartado = _rn03(precos)
    assert np.flatnonzero(descartado).tolist() == [30]  # com a EMA dos preços brutos, os 30 dias seguintes cairiam
    assert ema[31] == pytest.approx(100.0)

    serie: list[float | None] = [100.0 + (i % 3) for i in range(120)]
    serie[60] = 500.0                         # pico: > EMA·4
    serie[70] = 5.0                           # queda absurda: < EMA·0,1
    serie[80:83] = [None, None, None]         # 3 dias sem registro: preenchidos
    serie[90:94] = [None, None, None, None]   # 4 dias: o quarto fica sem preço
    base = preparar_dados(serie_simples({1: serie}), corte_validacao="2024-03-20", corte_teste="2024-04-10")
    o = base.originais.set_index("id_linha")
    assert o.loc[60, "descartado_rn03"] and not o.loc[60, "observado"]
    assert o.loc[60, "preco_cobre"] == o.loc[59, "preco_cobre"]
    assert o.loc[70, "descartado_rn03"]
    assert o.loc[[80, 81, 82], "preenchido"].all() and o.loc[[80, 81, 82], "preco_cobre"].notna().all()
    assert o.loc[[90, 91, 92], "preenchido"].all() and pd.isna(o.loc[93, "preco_cobre"])
    n = base.normalizadas.set_index("id_linha")
    assert n.loc[80, "f_observado"] == 0.0 and n.loc[79, "f_observado"] == 1.0
    assert not n.loc[93, "apta"]


def test_rn03_confirma_novo_patamar_em_7_dias() -> None:
    """7 registros seguidos fora da faixa, do mesmo lado, confirmam um novo patamar; o primeiro patamar da série só vale
    depois de 7 registros aceitos (o placeholder de um item novo é descartado)."""
    ema, descartado = _rn03([100.0] * 30 + [1_000.0] * 30)  # mudança real: o preço passa a 10× e fica
    assert not descartado.any()
    assert ema[40] == pytest.approx(1_000.0)
    assert np.flatnonzero(_rn03([100.0] * 30 + [1_000.0, 1_000.0] + [100.0] * 10)[1]).tolist() == [30, 31]
    seis_dias = [100.0] * 30 + [1_000.0] * (CFG.rn03_confirmacao - 1) + [100.0] * 10
    assert _rn03(seis_dias)[1].sum() == CFG.rn03_confirmacao - 1

    # O pico no primeiro dia de uma mudança real continua descartado (a mediana da sequência é o novo patamar).
    ema, descartado = _rn03([4_500.0] * 30 + [3_011_110_000.0] + [20_000.0] * 20)
    assert np.flatnonzero(descartado).tolist() == [30]
    assert ema[45] == pytest.approx(20_000.0)

    placeholder: list[float | None] = [999_990_100.0, None, 999_990_100.0] + [1_000.0 + i for i in range(40)]
    descartado = _rn03(placeholder)[1]
    assert descartado[[0, 2]].all() and not descartado[3:].any()


def test_rn03_salto_absurdo_exige_28_dias() -> None:
    """Um novo patamar a 1.000× ou mais do anterior só é aceito depois de 28 registros seguidos."""
    duas_semanas: list[float | None] = [10_000.0] * 30 + [10_000_000_100.0] * 14 + [10_000.0] * 20
    assert np.flatnonzero(_rn03(duas_semanas)[1]).tolist() == list(range(30, 44))
    um_mes: list[float | None] = [10_000.0] * 30 + [10_000_000_100.0] * CFG.rn03_confirmacao_absurdo + \
        [10_000_000_000.0] * 5
    assert not _rn03(um_mes)[1].any()  # durou o suficiente: é o novo patamar


# ------------------------------------------------------------------------------------------------------- RN10
def test_rn10_libera_por_mdape_quem_supera_o_ingenuo(preparado: BasePreparada) -> None:
    """MdAPE ≤ 15%, menor que o MdAPE do ingênuo, com ao menos 30 dias avaliados no período de teste."""
    dados = DadosPreparados(preparado)
    jan = dados.janelas("teste")
    perfeito = avaliar(dados, "teste", jan["id_amostra"].to_numpy(), jan[dados.colunas_alvo()].to_numpy("float64"))
    assert perfeito.resumo["rn10"] == {"metrica": "mdape", "limiar": 0.15, "minimo_dias": 30}
    pi = perfeito.por_item
    esperado = (pi["mdape_ingenuo"] > pi["mdape"]) & (pi["dias_avaliados"] >= 30)
    assert esperado.any()
    assert ((pi["situacao"] == "LIBERADA") == esperado).all()

    ingenuo = avaliar(dados, "teste", jan["id_amostra"].to_numpy(), np.tile(_zero_normalizado(dados), (len(jan), 1)))
    pi = ingenuo.por_item
    assert (pi["situacao"] == "BLOQUEADA").all()
    no_limiar = (pi["mdape"] <= 0.15) & (pi["dias_avaliados"] >= 30)
    assert no_limiar.any() and (pi.loc[no_limiar, "motivo"] == "não supera o ingênuo").all()
    assert (pi.loc[(pi["mdape"] > 0.15) & (pi["dias_avaliados"] >= 30), "motivo"] == "acima do limiar").all()
    assert np.allclose(pi["erro_relativo_ingenuo"].dropna(), 1.0)


def test_rn10_exige_minimo_de_dias_avaliados(preparado: BasePreparada) -> None:
    """Um item com menos de 30 dias de previsões avaliadas fica bloqueado por avaliação insuficiente, mesmo perfeito."""
    dados = DadosPreparados(preparado)
    jan = dados.janelas("teste")
    item = jan["item_id"].iloc[0]
    curto = jan[jan["item_id"] == item].sort_values("data_origem").head(20)  # 20 dias desse item
    sel = pd.concat([curto, jan[jan["item_id"] != item]])
    perfeito = sel[dados.colunas_alvo()].to_numpy("float64")
    av = avaliar(dados, "teste", sel["id_amostra"].to_numpy(), perfeito)
    linha = av.por_item.set_index("item_id").loc[item]
    assert linha["dias_avaliados"] == 20
    assert linha["situacao"] == "BLOQUEADA" and linha["motivo"] == "avaliação insuficiente"
    assert av.resumo["itens_com_avaliacao_insuficiente"] == 1
    sem_minimo = avaliar(dados, "teste", sel["id_amostra"].to_numpy(), perfeito, minimo_dias=0)
    assert sem_minimo.por_item.set_index("item_id").loc[item, "situacao"] == "LIBERADA"


# ---------------------------------------------------------------------------------------- RN27 e passo 2 do C1
def test_rn27_historico_minimo_para_projecao() -> None:
    """Só é elegível à projeção o item com ao menos 60 dias de histórico diário (configurável)."""
    fim = "2026-10-05"
    dados = {"precos": pd.concat([
        serie_constante(1, "2026-08-08", fim),  # 59 dias
        serie_constante(2, "2026-08-07", fim),  # 60 dias
        serie_constante(3, "2024-01-01", fim),
    ])}
    itens = selecionar(entrada_de(dados), CFG, "US").itens.set_index("item_id")
    assert itens.loc[1, "dias_de_historico"] == 59 and itens.loc[2, "dias_de_historico"] == 60
    assert not itens.loc[1, "elegivel"] and itens.loc[2, "elegivel"] and itens.loc[3, "elegivel"]
    curto = selecionar(entrada_de(dados), replace(CFG, historico_minimo_dias=30), "US").itens.set_index("item_id")
    assert curto.loc[1, "elegivel"]


def test_cu11_c1_passo2_elegiveis_e_conjunto_de_treinamento() -> None:
    """Elegíveis: RN02 (quantidade média > 50 nos últimos 7 dias) e RN07 (equipamento abaixo do nível mínimo, só com
    MODELO_ILVL_MINIMO definido). Conjunto de treinamento: os elegíveis aptos (RN15); os demais ficam fora do treino."""
    fim = "2026-10-05"
    iliquido = serie_constante(2, "2024-01-01", fim, quantidade=500.0)
    iliquido.loc[pd.to_datetime(iliquido["data"]) > pd.Timestamp(fim) - pd.Timedelta(days=7), "quantidade"] = 50.0
    dados = {
        "precos": pd.concat([serie_constante(1, "2024-01-01", fim), iliquido,
                             serie_constante(3, "2024-01-01", fim, serie="3209"),
                             serie_constante(4, "2024-01-01", fim, serie="3209"),
                             serie_constante(5, "2024-01-01", fim)]),
        "itens": pd.DataFrame([{"item_id": 3, "classe_id": 4, "nivel_item": 200},
                               {"item_id": 4, "classe_id": 2, "nivel_item": 700}]),
    }
    entrada = entrada_de(dados, aptos={1, 2, 3, 4})
    sem_rn07 = selecionar(entrada, CFG, "US")
    itens = sem_rn07.itens.set_index("item_id")
    assert not sem_rn07.rn07_ativa
    assert itens["elegivel"].to_dict() == {1: True, 2: False, 3: True, 4: True, 5: True}
    assert itens["integra_treino"].to_dict() == {1: True, 2: False, 3: True, 4: True, 5: False}
    assert sem_rn07.fora_do_treino == {("32512", 5)}
    assert set(sem_rn07.precos["item_id"]) == {1, 3, 4, 5}

    com_rn07 = selecionar(entrada, replace(CFG, ilvl_minimo=600), "US").itens.set_index("item_id")
    assert com_rn07["elegivel"].to_dict() == {1: True, 2: False, 3: False, 4: True, 5: True}


def test_cu11_conjunto_de_treinamento_nao_entra_nas_constantes(sinteticos: dict[str, pd.DataFrame]) -> None:
    """Constantes, nível de item, vocabulário e escala do alvo saem só do conjunto de treinamento: são as mesmas de uma
    base sem os elegíveis fora do treino. A variação do índice da subclasse é a exceção esperada (usa todos os
    elegíveis do dia). Os itens fora do treino continuam com amostras, para serem avaliados."""
    itens = sinteticos["itens"]["item_id"]
    fora = set(itens.iloc[1::4].astype(int))
    com = preparar_dados(sinteticos, fora_do_treino=chaves(sinteticos, fora), **CORTES)
    sem = preparar_dados(sinteticos, excluir=fora, **CORTES)
    ca, cb = com.normalizacao["constantes"], sem.normalizacao["constantes"]
    assert {k: v for k, v in ca.items() if k != "f_retorno_subclasse"} == \
           {k: v for k, v in cb.items() if k != "f_retorno_subclasse"}
    assert com.normalizacao["nivel_item"] == sem.normalizacao["nivel_item"]
    assert com.normalizacao["vocabulario"] == sem.normalizacao["vocabulario"]
    assert np.allclose(com.normalizacao["alvo"]["media"], sem.normalizacao["alvo"]["media"])
    assert np.allclose(com.normalizacao["alvo"]["desvio"], sem.normalizacao["alvo"]["desvio"])
    jan = com.janelas
    assert (jan["fora_do_treino"] == jan["item_id"].isin(fora)).all()
    assert set(jan.loc[jan["periodo"] == "teste", "item_id"]) & fora
