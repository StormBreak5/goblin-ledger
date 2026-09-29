import argparse
import gzip
import logging
import os
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Tuple

import requests
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.item_price import REGIAO_DA_FICHA, WOW_TOKEN_ID
from src.repositories.item_price_repository import ItemPriceRepository
from src.scraper.backfill import FonteIndisponivelError, FormatoAlteradoError

logger = logging.getLogger(__name__)

URL_DA_FICHA = "https://undermine.exchange/data/global/token-{regiao}.bin"
TIMEOUT_SEGUNDOS = 30
# O preço vem em unidades de 100 cobre (como nos arquivos dos itens): RN01 pede o valor em Cobre.
COBRE_POR_UNIDADE = 100
MIN_VALID_TIMESTAMP = datetime(2004, 1, 1, tzinfo=timezone.utc)
FUTURE_TOLERANCE = timedelta(days=1)

# Arquivo da Ficha do WoW (token-us.bin), decodificado:
#   cabeçalho:  u8 versão (1) | u32 instante atual (s Unix) | u32 preço atual | u16 quantidade de registros
#   registros:  N × (u32 instante em s Unix | u32 preço), do mais antigo para o mais novo, a cada 20 min (~14 dias)
_CABECALHO = struct.Struct("<BIIH")
_REGISTRO = struct.Struct("<II")
VERSAO_CONHECIDA = 1


@dataclass
class ResultadoDaImportacaoDaFicha:
    """Resumo da importação do histórico da Ficha do WoW (no mesmo espírito do CU10-C1 passo 10)."""
    lidos: int
    importados: int
    descartados: int
    duplicados: int


def decodificar_arquivo_da_ficha(dados: bytes) -> List[Tuple[datetime, int]]:
    """Decodifica o arquivo da Ficha em (instante UTC, preço em Cobre): o ponto atual do cabeçalho e os registros do
    histórico, sem repetidos e do mais antigo para o mais novo. Qualquer divergência de formato (versão, tamanho) levanta
    FormatoAlteradoError: o arquivo tem tamanho exato (11 + 8 x N bytes) e um corte ou uma mudança não passa despercebido."""
    try:
        conteudo = gzip.decompress(dados)
    except (OSError, EOFError):
        conteudo = dados  # já vinha descompactado
    if len(conteudo) < _CABECALHO.size:
        raise FormatoAlteradoError(f"Arquivo da Ficha com {len(conteudo)} bytes: menor que o cabeçalho.")
    versao, instante_atual, preco_atual, quantidade = _CABECALHO.unpack_from(conteudo, 0)
    if versao != VERSAO_CONHECIDA:
        raise FormatoAlteradoError(f"Versão {versao} do arquivo da Ficha; só a {VERSAO_CONHECIDA} é conhecida.")
    esperado = _CABECALHO.size + quantidade * _REGISTRO.size
    if len(conteudo) != esperado:
        raise FormatoAlteradoError(f"Arquivo da Ficha com {len(conteudo)} bytes; o cabeçalho anuncia {esperado}.")

    brutos = [(instante_atual, preco_atual)]
    brutos += [_REGISTRO.unpack_from(conteudo, _CABECALHO.size + i * _REGISTRO.size) for i in range(quantidade)]
    pontos = {}
    for instante, preco in brutos:
        pontos.setdefault(instante, preco)
    return [(datetime.fromtimestamp(i, tz=timezone.utc), p * COBRE_POR_UNIDADE) for i, p in sorted(pontos.items())]


def _baixar(url: str) -> bytes:
    cabecalhos = {"User-Agent": "GoblinLedger/1.0 (Backfill Bot)", "Accept-Encoding": "gzip"}
    try:
        resposta = requests.get(url, headers=cabecalhos, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise FonteIndisponivelError(f"{type(e).__name__}: {e}") from e
    if resposta.status_code != 200:
        raise FonteIndisponivelError(f"HTTP {resposta.status_code} em {url}")
    return resposta.content


def importar_historico_da_ficha(
    session: Session, regiao: str = REGIAO_DA_FICHA, baixar: Callable[[str], bytes] = _baixar
) -> ResultadoDaImportacaoDaFicha:
    """
    Importa o histórico da Ficha do WoW (cerca de 14 dias, a cada 20 min) do arquivo da Undermine Exchange para
    `item_prices`, a mesma série que o preço atual da Blizzard alimenta (o instante de cada ponto é o do preço, e não o da
    coleta). Registros com data ou preço inválidos são descartados; os que já existem são ignorados. É uma única
    requisição: uma falha da fonte (FonteIndisponivelError) ou do formato (FormatoAlteradoError) não grava nada.
    """
    pontos = decodificar_arquivo_da_ficha(baixar(URL_DA_FICHA.format(regiao=regiao.lower())))
    limite = datetime.now(timezone.utc) + FUTURE_TOLERANCE
    validos = [(i, p) for i, p in pontos if MIN_VALID_TIMESTAMP <= i <= limite and p > 0]
    importados = ItemPriceRepository(session).importar_historico(WOW_TOKEN_ID, regiao.lower(), validos)
    session.commit()
    resultado = ResultadoDaImportacaoDaFicha(
        lidos=len(pontos), importados=importados, descartados=len(pontos) - len(validos), duplicados=len(validos) - importados
    )
    logger.info("Histórico da Ficha (%s): %s", regiao, resultado)
    return resultado


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Importa o histórico da Ficha do WoW da Undermine Exchange.")
    parser.add_argument("--regiao", default=REGIAO_DA_FICHA, help="Região do arquivo (token-<região>.bin). Padrão: us.")
    args = parser.parse_args()

    from dotenv import load_dotenv
    from src.repositories.database import get_session, init_db

    load_dotenv()
    init_db()
    sessao = get_session()
    try:
        print(importar_historico_da_ficha(sessao, args.regiao))
    finally:
        sessao.close()
