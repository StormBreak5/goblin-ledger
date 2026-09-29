"""
Histórico da Ficha do WoW: importação do arquivo `token-us.bin` da Undermine Exchange para `item_prices`, a mesma série
que o preço atual da Blizzard alimenta. O arquivo de teste é uma cópia real (29/09/2026): 1.007 pontos a cada 20 min.
Rodam contra um PostgreSQL temporário; nenhum teste acessa a internet.
"""
import gzip
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from src.models.api_models import WoWTokenResponse
from src.models.item_price import ItemPrice
from src.repositories.item_price_repository import ItemPriceRepository
from src.scraper import token_history
from src.scraper.backfill import FonteIndisponivelError, FormatoAlteradoError
from src.scraper.token_history import decodificar_arquivo_da_ficha, importar_historico_da_ficha

ARQUIVO_REAL = (Path(__file__).parent.parent / "fixtures" / "token-us.bin").read_bytes()
UTC = timezone.utc


def _arquivo(registros: list[tuple[int, int]], atual: tuple[int, int], versao: int = 1, compactar: bool = True) -> bytes:
    corpo = struct.pack("<BIIH", versao, atual[0], atual[1], len(registros))
    corpo += b"".join(struct.pack("<II", *registro) for registro in registros)
    return gzip.compress(corpo) if compactar else corpo


@pytest.fixture
def limpar_precos(db_session):
    yield
    db_session.rollback()
    db_session.query(ItemPrice).delete()
    db_session.commit()


def _quantos(db_session) -> int:
    return db_session.query(ItemPrice).filter(ItemPrice.item_id == 122284).count()


# ---------------------------------------------------------------------- decodificação


def test_ficha_decodifica_o_arquivo_real_da_undermine():
    pontos = decodificar_arquivo_da_ficha(ARQUIVO_REAL)

    assert len(pontos) == 1007  # o ponto atual do cabeçalho é o último registro: não conta duas vezes
    (primeiro, preco_primeiro), (ultimo, preco_ultimo) = pontos[0], pontos[-1]
    assert primeiro == datetime(2026, 9, 15, 22, 32, 23, tzinfo=UTC) and preco_primeiro == 281_452 * 10_000  # cobre (RN01)
    assert ultimo == datetime(2026, 9, 29, 22, 23, 7, tzinfo=UTC) and preco_ultimo == 286_541 * 10_000
    assert all(depois[0] > antes[0] for antes, depois in zip(pontos, pontos[1:]))  # do mais antigo para o mais novo
    intervalos = {int((depois[0] - antes[0]).total_seconds()) for antes, depois in zip(pontos, pontos[1:])}
    assert min(intervalos) >= 1200  # um preço a cada 20 minutos


def test_ficha_aceita_o_arquivo_com_ou_sem_gzip_e_em_ordem_qualquer():
    desordenado = [(1_790_000_400, 280_000), (1_790_000_000, 279_000)]
    compactado = _arquivo(desordenado, atual=(1_790_000_800, 281_000))
    puro = _arquivo(desordenado, atual=(1_790_000_800, 281_000), compactar=False)

    assert decodificar_arquivo_da_ficha(compactado) == decodificar_arquivo_da_ficha(puro)
    assert [preco for _, preco in decodificar_arquivo_da_ficha(puro)] == [27_900_000, 28_000_000, 28_100_000]  # x100 cobre


@pytest.mark.parametrize(
    "arquivo",
    [
        b"",  # vazio
        gzip.compress(b"\x01\x00\x00"),  # menor que o cabeçalho
        _arquivo([(1_790_000_000, 280_000)], atual=(1_790_000_000, 280_000), versao=2),  # versão desconhecida
        gzip.compress(struct.pack("<BIIH", 1, 1_790_000_000, 280_000, 3) + struct.pack("<II", 1_790_000_000, 280_000)),  # cortado
        _arquivo([(1_790_000_000, 280_000)], atual=(1_790_000_000, 280_000), compactar=False) + b"\x00",  # sobra de bytes
        gzip.compress(b"<html>Not Found</html>" * 5),  # uma página de erro no lugar do arquivo
    ],
)
def test_ficha_formato_alterado_e_recusado(arquivo):
    with pytest.raises(FormatoAlteradoError):
        decodificar_arquivo_da_ficha(arquivo)


# ---------------------------------------------------------------------- importação


def test_ficha_importa_o_historico_em_item_prices_com_instante_utc_e_preco_em_cobre(db_session, limpar_precos):
    resultado = importar_historico_da_ficha(db_session, baixar=lambda url: ARQUIVO_REAL)

    assert (resultado.lidos, resultado.importados, resultado.descartados, resultado.duplicados) == (1007, 1007, 0, 0)
    linhas = ItemPriceRepository(db_session).history(122284, "us")
    assert len(linhas) == 1007 and {linha.region for linha in linhas} == {"us"}
    assert linhas[-1].created_at == datetime(2026, 9, 29, 22, 23, 7, tzinfo=UTC)
    assert linhas[-1].price_copper == 2_865_410_000  # 286.541 de ouro
    assert linhas[-1].created_at.utcoffset() == timedelta(0)


def test_ficha_repetir_a_importacao_nao_duplica(db_session, limpar_precos):
    importar_historico_da_ficha(db_session, baixar=lambda url: ARQUIVO_REAL)

    repetida = importar_historico_da_ficha(db_session, baixar=lambda url: ARQUIVO_REAL)

    assert (repetida.importados, repetida.duplicados) == (0, 1007)
    assert _quantos(db_session) == 1007


def test_ficha_pede_o_arquivo_da_regiao_e_so_uma_requisicao(db_session, limpar_precos):
    urls = []

    def baixar(url):
        urls.append(url)
        return ARQUIVO_REAL

    importar_historico_da_ficha(db_session, baixar=baixar)

    assert urls == ["https://undermine.exchange/data/global/token-us.bin"]


def test_ficha_descarta_pontos_com_data_ou_preco_invalidos(db_session, limpar_precos):
    agora = int(datetime.now(UTC).timestamp())
    arquivo = _arquivo(
        [(agora - 1200, 280_000), (agora + 30 * 86_400, 281_000), (946_684_800, 282_000), (agora - 2400, 0)],  # futuro, ano 2000, preço 0
        atual=(agora, 283_000),
    )

    resultado = importar_historico_da_ficha(db_session, baixar=lambda url: arquivo)

    assert (resultado.lidos, resultado.importados, resultado.descartados) == (5, 2, 3)
    assert sorted(linha.price_copper for linha in ItemPriceRepository(db_session).history(122284, "us")) == [28_000_000, 28_300_000]


def test_ficha_fonte_indisponivel_nao_grava_nada(db_session, limpar_precos, mocker):
    mocker.patch.object(token_history.requests, "get", side_effect=requests.ConnectionError("fonte fora do ar"))

    with pytest.raises(FonteIndisponivelError):
        importar_historico_da_ficha(db_session)

    resposta_503 = mocker.Mock(status_code=503, content=b"")
    mocker.patch.object(token_history.requests, "get", return_value=resposta_503)
    with pytest.raises(FonteIndisponivelError):
        importar_historico_da_ficha(db_session)
    assert _quantos(db_session) == 0


def test_ficha_arquivo_ilegivel_nao_grava_nada(db_session, limpar_precos):
    with pytest.raises(FormatoAlteradoError):
        importar_historico_da_ficha(db_session, baixar=lambda url: gzip.compress(b"formato novo"))

    assert _quantos(db_session) == 0


# ---------------------------------------------------------------------- preço atual da Blizzard na mesma série


def test_ficha_preco_atual_da_blizzard_usa_o_instante_do_preco_e_nao_o_da_coleta(db_session, limpar_precos):
    instante = datetime(2026, 9, 29, 22, 3, 7, tzinfo=UTC)
    resposta = WoWTokenResponse(price=2_868_980_000, last_updated_timestamp=int(instante.timestamp() * 1000))  # em ms
    repositorio = ItemPriceRepository(db_session)

    primeira = repositorio.save_price(122284, "us", resposta)
    repetida = repositorio.save_price(122284, "us", resposta)  # a coleta de 15 min encontra o mesmo preço da Blizzard

    assert primeira.created_at == instante and repetida is None
    assert _quantos(db_session) == 1


def test_ficha_preco_atual_e_historico_importado_formam_uma_serie_sem_duplicar(db_session, limpar_precos):
    importar_historico_da_ficha(db_session, baixar=lambda url: ARQUIVO_REAL)
    ultimo_do_arquivo = datetime(2026, 9, 29, 22, 23, 7, tzinfo=UTC)

    ja_existia = ItemPriceRepository(db_session).save_price(
        122284, "us", WoWTokenResponse(price=2_865_410_000, last_updated_timestamp=int(ultimo_do_arquivo.timestamp() * 1000))
    )
    novo = ItemPriceRepository(db_session).save_price(
        122284, "us", WoWTokenResponse(price=2_870_000_000, last_updated_timestamp=int((ultimo_do_arquivo + timedelta(minutes=20)).timestamp() * 1000))
    )

    assert ja_existia is None and novo is not None  # o ponto do arquivo não repete; o próximo entra
    assert _quantos(db_session) == 1008


def test_ficha_instante_da_blizzard_aceita_milissegundos_e_segundos(db_session, limpar_precos):
    repositorio = ItemPriceRepository(db_session)

    em_ms = repositorio.save_price(122284, "us", WoWTokenResponse(price=1, last_updated_timestamp=1_790_000_000_000))
    em_s = repositorio.save_price(122284, "us", WoWTokenResponse(price=2, last_updated_timestamp=1_790_001_200))

    assert em_ms.created_at == datetime.fromtimestamp(1_790_000_000, tz=UTC)
    assert em_s.created_at == datetime.fromtimestamp(1_790_001_200, tz=UTC)
