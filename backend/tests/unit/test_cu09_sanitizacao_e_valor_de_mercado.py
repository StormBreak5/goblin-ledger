"""
CU09-C2 (sanitizar e padronizar) e o cálculo do valor de mercado do C3 (RN06): funções puras.
"""
import pytest

from src.services import ingestao_config
from src.services.ingestao_config import TIPO_COMMODITIES, TIPO_LEILOES
from src.services.sanitizacao import PayloadForaDoFormatoError, para_cobre, sanitizar
from src.services.valor_de_mercado import primeiro_quartil_ponderado, volume_e_anomalo


def test_cu09_c2_conversao_para_cobre_rn01():
    assert para_cobre(ouro=1) == 10000
    assert para_cobre(prata=1) == 100
    assert para_cobre(ouro=1, prata=2, cobre=3) == 10203


def test_cu09_c2_fluxo_principal_commodity_usa_o_preco_unitario():
    payload = {"auctions": [{"id": 1, "item": {"id": 7}, "quantity": 20, "unit_price": 150, "time_left": "SHORT"}]}

    resultado = sanitizar(payload, TIPO_COMMODITIES)

    leilao = resultado.leiloes[0]
    assert (leilao.preco_unitario, leilao.preco_buyout, leilao.preco_bid) == (150, 3000, None)
    assert resultado.descartados == 0 and resultado.taxa_de_descarte == 0.0


def test_cu09_c2_fluxo_principal_preco_unitario_arredonda_o_buyout_do_lote():
    payload = {"auctions": [{"id": 1, "item": {"id": 7}, "quantity": 3, "buyout": 100}]}

    assert sanitizar(payload, TIPO_LEILOES).leiloes[0].preco_unitario == 33  # 100 / 3 = 33,33


def test_cu09_c2_fa1_taxa_de_descarte():
    payload = {"auctions": [{"id": 1, "item": {"id": 7}, "quantity": 1, "buyout": 5}, {"id": 2}, {"id": 3}, {"id": 4}]}

    resultado = sanitizar(payload, TIPO_LEILOES)

    assert (len(resultado.leiloes), resultado.descartados, resultado.total) == (1, 3, 4)
    assert resultado.taxa_de_descarte == 0.75 > ingestao_config.LIMITE_DE_DESCARTE


@pytest.mark.parametrize("payload", [None, [], "texto", {"auctions": None}, {"auctions": {}}, {"outra_chave": []}, 42])
def test_cu09_c2_fe1_payload_fora_do_formato_levanta_erro(payload):
    with pytest.raises(PayloadForaDoFormatoError):
        sanitizar(payload, TIPO_LEILOES)


def test_cu09_c2_lista_vazia_de_leiloes_e_um_payload_valido():
    resultado = sanitizar({"auctions": []}, TIPO_LEILOES)

    assert resultado.leiloes == [] and resultado.taxa_de_descarte == 0.0


def test_cu09_c3_valor_de_mercado_e_o_primeiro_quartil_ponderado_rn06():
    # 10 unidades: 25% = 2,5 unidades. O menor preço isolado (100) não é o valor de mercado.
    assert primeiro_quartil_ponderado([(100, 1), (200, 2), (300, 1), (400, 6)]) == 200
    # O mesmo resultado, independentemente da ordem de chegada.
    assert primeiro_quartil_ponderado([(400, 6), (300, 1), (100, 1), (200, 2)]) == 200
    # Uma unidade barata e 999 caras: o quartil ponderado vai para o preço da maioria das unidades.
    assert primeiro_quartil_ponderado([(1, 1), (5000, 999)]) == 5000
    assert primeiro_quartil_ponderado([(777, 5)]) == 777
    assert primeiro_quartil_ponderado([]) is None


def test_cu09_c2_anomalia_de_volume_criterio_rn12():
    # Base suficiente (24 pontos anteriores, mediana 10): anômalo acima de 10x a mediana e do piso de volume.
    assert volume_e_anomalo(5000, 10.0, 30) is True
    assert volume_e_anomalo(100, 10.0, 30) is False  # não passa de 10x a mediana
    assert volume_e_anomalo(50, 1.0, 30) is False  # 50x a mediana, mas abaixo do piso de 100 unidades
    assert volume_e_anomalo(5000, 10.0, 23) is False  # sem pontos suficientes, não se julga
    assert volume_e_anomalo(5000, None, 0) is False
