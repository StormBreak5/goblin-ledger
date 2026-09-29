"""Atalhos compartilhados pelos testes do CU10 (importação de histórico): uma Undermine Exchange falsa."""
import struct
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.scraper.backfill import STATUS_ERRO_DE_REDE, STATUS_FORMATO_INVALIDO

REGIAO = "3209"
REGIAO_DAS_COMMODITIES = "32512"
INICIO = datetime(2026, 6, 1)


def dias(quantidade: int, inicio: datetime = INICIO) -> list[datetime]:
    return [inicio + timedelta(days=deslocamento) for deslocamento in range(quantidade)]


def _em_ms(momento: datetime) -> int:
    return int(momento.replace(tzinfo=timezone.utc).timestamp() * 1000)


def dados_decodificados(diarios: list[datetime], horarios: Optional[list[datetime]] = None, preco: int = 100000) -> dict:
    """Mesma forma devolvida por `decompress_and_parse` (datas em milissegundos)."""
    return {
        "snapshots": [{"snapshot": _em_ms(momento), "price": preco, "quantity": 7} for momento in (horarios or [])],
        "daily": [{"snapshot": _em_ms(dia), "price": preco, "quantity": 5} for dia in diarios],
    }


def arquivo_bin(snapshots: list[tuple[int, int, int]], diarios: list[tuple[int, int, int]], versao: int = 5) -> bytes:
    """Monta um arquivo no formato da Undermine (o mesmo que `parse_item_state` lê): snapshots como
    (segundos Unix, preço, quantidade) e diários como (dias desde 1970, preço, quantidade); preços em unidades de 100 cobre."""
    corpo = struct.pack("<B", versao) + struct.pack("<III", 1_790_000_000, 25, 3)
    corpo += struct.pack("<H", 0)  # leilões atuais
    corpo += struct.pack("<H", 0)  # variações do item
    corpo += struct.pack("<H", len(snapshots)) + b"".join(struct.pack("<III", *s) for s in snapshots)
    corpo += struct.pack("<H", len(diarios)) + b"".join(struct.pack("<HII", *d) for d in diarios)
    return corpo


class FonteFalsa:
    """
    Substitui `backfill.fetch_item_history`: nenhum teste acessa a Undermine Exchange.
    `series[item_id] = (dados decodificados, origem)`; `comportamentos[item_id]` = "rede", "formato", "5xx" ou "404"
    simula a falha da fonte para o item. `chamadas` guarda os alvos consultados.
    """

    def __init__(self) -> None:
        self.series: dict[int, tuple[dict, str]] = {}
        self.comportamentos: dict[int, str] = {}
        self.chamadas: list = []
        self.respeita_etag = False  # como a Undermine: com If-None-Match igual ao ETag do arquivo, responde 304

    def com_dias(self, item_id: int, diarios: list[datetime], origem: str = REGIAO, horarios: Optional[list[datetime]] = None) -> None:
        self.series[item_id] = (dados_decodificados(diarios, horarios), origem)

    async def buscar(self, http_session, region_id, target, **_):
        self.chamadas.append(target)
        falha = self.comportamentos.get(target.item_id)
        if falha == "rede":
            return STATUS_ERRO_DE_REDE, None, target.last_etag, "ConnectionResetError: fonte fora do ar", None
        if falha == "formato":
            return STATUS_FORMATO_INVALIDO, None, target.last_etag, "Arquivo ilegível: struct.error", None
        if falha == "5xx":
            return 503, None, target.last_etag, "HTTP 503", None
        if falha == "404" or target.item_id not in self.series:
            return 404, None, target.last_etag, "HTTP 404", None
        dados, origem = self.series[target.item_id]
        etag = f'"etag-{target.item_id}-{len(dados["daily"])}"'
        if self.respeita_etag and target.last_etag == etag:
            return 304, None, etag, None, origem
        return 200, dados, etag, None, origem
