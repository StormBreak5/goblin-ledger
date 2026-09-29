import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp
from psycopg2.extras import execute_values
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.item import Item
from src.models.mercado import ORIGEM_UNDERMINE
from src.scraper.models import (
    FALHA_FONTE,
    FALHA_FORMATO,
    GRANULARIDADE_DIARIA,
    GRANULARIDADE_HORARIA,
    HistoricalItemPrice,
)
from src.scraper.parser import decompress_and_parse
from src.services.limitador import LimitadorDeIntervalo

logger = logging.getLogger(__name__)

# CU10-C1 passo 3: o Provider baixa até MAX_CONCURRENT_REQUESTS arquivos ao mesmo tempo; o intervalo mínimo entre o
# início de duas requisições (RN23 / FA3) fica em `src.services.limitador`.
MAX_CONCURRENT_REQUESTS = 50
US_COMMODITY_CONNECTED_ID = "32512"  # Undermine Exchange ID for US regional commodities

# CU10-C1: o histórico é baixado e gravado em lotes, dentro de uma única transação.
CHUNK_SIZE = 500  # itens baixados antes de cada gravação (limita a memória usada)
INSERT_PAGE_SIZE = 10_000  # linhas por INSERT
# CU10-C1 passo 8: na recuperação automática só chegam ao banco os pontos mais novos que o último já gravado do item.
# A margem cobre o agregado diário do dia corrente, que só é finalizado (com data 00:00) depois de já existirem
# snapshots do dia. A importação do Admin não usa o atalho: assim os duplicados são contados de forma exata.
INCREMENTAL_LOOKBACK = timedelta(days=2)
# CU10-C1 passo 7: pontos com data fora deste intervalo são registros inconsistentes e são descartados
# (o limite inferior é anterior ao lançamento do jogo; a tolerância no futuro cobre diferenças de relógio).
MIN_VALID_TIMESTAMP = datetime(2004, 1, 1)
FUTURE_TOLERANCE = timedelta(days=1)

# CU10-C1-FE1 / FE3: o documento não diz quando a fonte "não está disponível" nem quando o "formato mudou". Adotado:
# tantas falhas seguidas de rede, tempo limite, 429 ou 5xx (FE1), ou tantos arquivos seguidos que não decodificam (FE3).
LIMITE_DE_FALHAS_SEGUIDAS = int(os.getenv("IMPORTACAO_LIMITE_FALHAS_SEGUIDAS", "20"))
LIMITE_DE_ARQUIVOS_ILEGIVEIS = int(os.getenv("IMPORTACAO_LIMITE_ARQUIVOS_ILEGIVEIS", "3"))

# Resultado de `fetch_item_history` além dos códigos HTTP.
STATUS_ERRO_DE_REDE = 0
STATUS_FORMATO_INVALIDO = -1

INSERT_SQL = (
    f"INSERT INTO {HistoricalItemPrice.__tablename__} (item_id, region, timestamp, price, quantity, granularidade) "
    "VALUES %s ON CONFLICT (item_id, region, timestamp) DO NOTHING"
)


class ImportacaoInterrompidaError(Exception):
    """A importação parou no meio; o que já foi gravado na transação fica a critério de quem chamou (FE1 e FE3 mantêm)."""


class FonteIndisponivelError(ImportacaoInterrompidaError):
    """CU10-C1-FE1: a fonte não respondeu, ou esgotou o tempo limite, em várias requisições seguidas."""


class FormatoAlteradoError(ImportacaoInterrompidaError):
    """CU10-C1-FE3: vários arquivos seguidos não puderam ser decodificados; a fonte alterou o formato."""


@dataclass
class BackfillTarget:
    """Dados do item lidos do ORM antes do download, para não tocar a sessão em outra thread nem
    disparar um SELECT por atributo expirado a cada item. `pk` nulo = item ainda não cadastrado (FA2)."""
    pk: Any  # Item.id
    item_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def novo(self) -> bool:
        return self.pk is None

    @property
    def last_etag(self) -> Optional[str]:
        return self.metadata.get('last_etag')

    @property
    def source_region(self) -> Optional[str]:
        return self.metadata.get('source_region')


def get_items_to_process(session: Session) -> List[Item]:
    """
    Retrieves the list of active tracked items from the database.
    """
    return session.query(Item).filter(
        Item.game == 'wow',
        Item.is_active == True
    ).all()


def candidate_urls(
    item_id: int, region_id: str, preferred_source: Optional[str] = None, commodity_id: str = US_COMMODITY_CONNECTED_ID
) -> List[Tuple[str, str]]:
    """CU10-C1 passo 3: URLs do arquivo do item, como (origem, url). A origem que já atendeu o item vem primeiro,
    evitando a requisição que daria 404 (reino local) nos itens de commodity."""
    bucket_id = item_id & 255
    sources = [region_id]
    if region_id != commodity_id:
        sources.append(commodity_id)
    if preferred_source in sources:
        sources.remove(preferred_source)
        sources.insert(0, preferred_source)
    return [(source, f'https://undermine.exchange/data/{source}/{bucket_id}/{item_id}.bin') for source in sources]


class MonitorDaFonte:
    """
    CU10-C1-FE1 / FE3: acompanha as respostas da fonte e sinaliza a interrupção da importação quando ela cai (falhas
    seguidas) ou muda de formato (arquivos ilegíveis seguidos). As tarefas verificam `motivo` antes de cada item.
    """

    def __init__(self, limite_de_falhas: Optional[int] = None, limite_de_ilegiveis: Optional[int] = None):
        self.limite_de_falhas = limite_de_falhas or LIMITE_DE_FALHAS_SEGUIDAS
        self.limite_de_ilegiveis = limite_de_ilegiveis or LIMITE_DE_ARQUIVOS_ILEGIVEIS
        self.falhas_seguidas = 0
        self.ilegiveis_seguidos = 0
        self.motivo: Optional[str] = None  # FALHA_FONTE ou FALHA_FORMATO
        self.ultimo_erro: Optional[str] = None

    def registrar(self, status: int, erro: Optional[str]) -> None:
        if status in (200, 304, 404):  # a fonte respondeu e o arquivo (quando existe) foi lido
            self.falhas_seguidas = 0
            self.ilegiveis_seguidos = 0
            return
        self.ultimo_erro = erro
        if status == STATUS_FORMATO_INVALIDO:
            self.falhas_seguidas = 0
            self.ilegiveis_seguidos += 1
            if self.ilegiveis_seguidos >= self.limite_de_ilegiveis and self.motivo is None:
                self.motivo = FALHA_FORMATO
            return
        self.falhas_seguidas += 1
        if self.falhas_seguidas >= self.limite_de_falhas and self.motivo is None:
            self.motivo = FALHA_FONTE


async def fetch_item_history(
    session: aiohttp.ClientSession,
    region_id: str,
    target: BackfillTarget,
    *,
    limitador: Optional[LimitadorDeIntervalo] = None,
    commodity_id: str = US_COMMODITY_CONNECTED_ID,
) -> Tuple[int, Any, Optional[str], Optional[str], Optional[str]]:
    """Fetch item history, returning (status_code, parsed_data, new_etag, error_msg, source).
    CU10-C1-FA3: cada requisição espera o intervalo mínimo da fonte (RN23) antes de começar."""

    headers = {
        'User-Agent': 'GoblinLedger/1.0 (Backfill Bot)',
        'Accept-Encoding': 'gzip, deflate, br'
    }

    last_etag = target.last_etag
    if last_etag:
        headers['If-None-Match'] = last_etag

    for source, url in candidate_urls(target.item_id, region_id, target.source_region, commodity_id):
        if limitador is not None:
            await limitador.aguardar()
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 304:
                    return 304, None, last_etag, None, source

                if response.status == 200:
                    new_etag = response.headers.get('ETag')
                    data = await response.read()
                    try:
                        parsed_data = decompress_and_parse(data)
                    except Exception as e:  # CU10-C1-FE3: o arquivo não segue mais o formato conhecido
                        return STATUS_FORMATO_INVALIDO, None, last_etag, f"Arquivo ilegível ({url}): {e!r}", None
                    return 200, parsed_data, new_etag, None, source

                if response.status == 429:
                    return 429, None, last_etag, "Rate Limit (429)", None

                if response.status == 404:
                    continue # Try the next URL (commodity fallback)

                return response.status, None, last_etag, f"HTTP {response.status}", None

        except Exception as e:  # CU10-C1-FE1: rede fora do ar ou tempo limite esgotado
            return STATUS_ERRO_DE_REDE, None, last_etag, f"{type(e).__name__}: {e}", None

    # If every URL failed with 404
    return 404, None, last_etag, "HTTP 404", None


async def worker(
    target: BackfillTarget,
    region_id: str,
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    results: list,
    monitor: MonitorDaFonte,
    limitador: Optional[LimitadorDeIntervalo],
    commodity_id: str,
):
    """Worker task to process a single item."""
    async with semaphore:
        if monitor.motivo is not None:
            return  # importação interrompida (FE1 / FE3): o item não é consultado

        status, data, new_etag, error, source = await fetch_item_history(
            session, region_id, target, limitador=limitador, commodity_id=commodity_id
        )
        monitor.registrar(status, error)

        results.append({
            'target': target,
            'status': status,
            'data': data,
            'new_etag': new_etag,
            'error': error,
            'source': source
        })

        if status == 200:
            logger.debug(f"Downloaded new data for item {target.item_id}")
        elif status == 304:
            logger.debug(f"Item {target.item_id} not modified (304)")
        elif status == 429:
            logger.warning(f"Rate limited on item {target.item_id}")
        else:
            logger.warning(f"Error fetching item {target.item_id}: {error}")


def load_last_seen(session: Session, region_id: str) -> Dict[int, datetime]:
    """CU10-C1 passo 8: data (UTC) do último ponto da Undermine já gravado de cada item na região. Os pontos do ciclo
    da Blizzard (CU09) ficam de fora: são mais novos e esconderiam o histórico ainda não importado."""
    rows = (
        session.query(HistoricalItemPrice.item_id, func.max(HistoricalItemPrice.timestamp))
        .filter(HistoricalItemPrice.region == region_id, HistoricalItemPrice.origem == ORIGEM_UNDERMINE)
        .group_by(HistoricalItemPrice.item_id)
        .all()
    )
    return {item_id: last for item_id, last in rows}


def _insert_rows(db_session: Session, rows: List[tuple]) -> int:
    """CU10-C1 passo 9: grava as linhas em páginas, ignorando as já existentes. Devolve quantas foram inseridas."""
    if not rows:
        return 0
    cursor = db_session.connection().connection.cursor()
    try:
        inserted = 0
        for start in range(0, len(rows), INSERT_PAGE_SIZE):
            page = rows[start:start + INSERT_PAGE_SIZE]
            execute_values(cursor, INSERT_SQL, page, page_size=len(page))
            inserted += cursor.rowcount
        return inserted
    finally:
        cursor.close()


class ChunkWriter:
    """
    CU10-C1 passos 5 a 9: converte e grava cada lote de itens baixados. Tudo é gravado na transação aberta da
    sessão, que só é confirmada no fim (pelo serviço); se qualquer lote falhar, a importação inteira é desfeita
    (CU10-C1-FE2). Os contadores alimentam o resumo da importação (passo 10).
    """

    def __init__(
        self,
        db_session: Session,
        region_id: str,
        last_seen: Dict[int, datetime],
        *,
        incremental: bool = True,
        on_progress: Optional[Callable[["ChunkWriter"], None]] = None,
    ):
        self.db_session = db_session
        self.region_id = region_id
        self.last_seen = last_seen
        self.incremental = incremental
        self.on_progress = on_progress
        self.items_processed = 0
        self.items_created = 0  # FA2
        self.items_without_data = 0
        self.items_failed = 0
        self.records_inserted = 0
        self.records_discarded = 0
        self.records_duplicated = 0
        self.write_seconds = 0.0

    def __call__(self, results: list) -> None:
        started = time.monotonic()
        rows: List[tuple] = []
        items_to_update = []
        items_to_create = []
        discarded = 0
        skipped = 0
        latest_valid = datetime.now(timezone.utc).replace(tzinfo=None) + FUTURE_TOLERANCE

        for r in results:
            target: BackfillTarget = r['target']
            self.items_processed += 1

            if r['status'] == 404:
                self.items_without_data += 1
            elif r['status'] not in (200, 304):
                self.items_failed += 1

            if r['status'] == 200 and r['data']:
                last = self.last_seen.get(target.item_id) if self.incremental else None
                cutoff = last - INCREMENTAL_LOOKBACK if last is not None else None

                # Combine snapshots (horários) and daily (diários) into one list of points
                points = (
                    [(p, GRANULARIDADE_HORARIA) for p in r['data'].get('snapshots', [])]
                    + [(p, GRANULARIDADE_DIARIA) for p in r['data'].get('daily', [])]
                )
                for p, granularidade in points:
                    try:
                        # Convert timestamp from ms to datetime
                        timestamp = datetime.fromtimestamp(p['snapshot'] / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                    except (ValueError, OverflowError, OSError):
                        discarded += 1
                        continue
                    # CU10-C1 passo 7: no Linux uma data absurda converte sem erro e não pode chegar ao banco
                    # (nem virar o "último ponto" do item, que alimenta o filtro incremental). Preço ou
                    # quantidade negativos também são registros inconsistentes.
                    if not MIN_VALID_TIMESTAMP <= timestamp <= latest_valid or p['price'] < 0 or p['quantity'] < 0:
                        discarded += 1
                        continue
                    if cutoff is not None and timestamp <= cutoff:
                        skipped += 1  # já gravado numa importação anterior
                        continue
                    rows.append((target.item_id, self.region_id, timestamp, p['price'], p['quantity'], granularidade))

                # Update item's ETag and remember which source served it
                new_meta = dict(target.metadata)
                new_meta['last_etag'] = r['new_etag']
                new_meta['source_region'] = r['source']
                if target.novo:
                    items_to_create.append((target.item_id, new_meta))  # CU10-C1-FA2
                else:
                    items_to_update.append({'id': target.pk, 'metadata_info': new_meta})

        if items_to_create:
            self.items_created += self._cadastrar_itens(items_to_create)
        inserted = _insert_rows(self.db_session, rows)
        self.records_inserted += inserted
        self.records_duplicated += skipped + (len(rows) - inserted)
        if items_to_update:
            self.db_session.execute(update(Item), items_to_update)

        self.records_discarded += discarded
        if discarded:
            logger.warning(f"Chunk had {discarded} price points with an invalid date; discarded (CU10-C1 step 7).")
        self.write_seconds += time.monotonic() - started
        logger.info(f"Chunk saved: {len(results)} items, {len(rows)} price points sent ({self.records_inserted} inserted so far).")
        if self.on_progress is not None:
            self.on_progress(self)

    def _cadastrar_itens(self, novos: List[Tuple[int, Dict[str, Any]]]) -> int:
        """CU10-C1-FA2: cadastra o item que ainda não existe com o identificador e um nome provisório; o nome e o ícone
        vêm depois, do populate_item_details. Devolve quantos foram de fato criados."""
        linhas = [
            {"game": "wow", "external_item_id": str(item_id), "name": f"Item {item_id}", "metadata_info": {**meta, "source": "importacao"}}
            for item_id, meta in novos
        ]
        resultado = self.db_session.execute(
            insert(Item).values(linhas).on_conflict_do_nothing(index_elements=["game", "external_item_id"])
        )
        return resultado.rowcount


async def run_backfill_async(
    targets: List[BackfillTarget],
    region_id: str,
    on_chunk,
    *,
    limitador: Optional[LimitadorDeIntervalo] = None,
    monitor: Optional[MonitorDaFonte] = None,
    commodity_id: str = US_COMMODITY_CONNECTED_ID,
) -> float:
    """Baixa os itens em lotes e entrega cada lote a `on_chunk` (executado numa thread, enquanto o lote seguinte
    é baixado). Devolve o tempo gasto no download e na decodificação. Se a fonte cair ou mudar de formato, o lote em
    andamento ainda é gravado e a importação termina com FonteIndisponivelError / FormatoAlteradoError."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    loop = asyncio.get_running_loop()
    monitor = monitor or MonitorDaFonte()
    download_seconds = 0.0
    pending_write = None

    async with aiohttp.ClientSession() as session:
        for start in range(0, len(targets), CHUNK_SIZE):
            results: list = []
            started = time.monotonic()
            await asyncio.gather(*[
                worker(target, region_id, semaphore, session, results, monitor, limitador, commodity_id)
                for target in targets[start:start + CHUNK_SIZE]
            ])
            download_seconds += time.monotonic() - started

            if pending_write is not None:
                await pending_write  # falha na gravação do lote anterior interrompe a importação
            pending_write = loop.run_in_executor(None, on_chunk, results)
            if monitor.motivo is not None:
                break

        if pending_write is not None:
            await pending_write

    if monitor.motivo == FALHA_FONTE:
        raise FonteIndisponivelError(monitor.ultimo_erro or "sem resposta da fonte")
    if monitor.motivo == FALHA_FORMATO:
        raise FormatoAlteradoError(monitor.ultimo_erro or "arquivo ilegível")

    return download_seconds


def importar(
    targets: List[BackfillTarget],
    region_id: str,
    writer: ChunkWriter,
    *,
    limitador: Optional[LimitadorDeIntervalo] = None,
    commodity_id: str = US_COMMODITY_CONNECTED_ID,
) -> float:
    """CU10-C1 passos 3 a 9 para os itens pedidos. Não confirma a transação: quem chama decide (confirma na conclusão
    e nas interrupções FE1/FE3; desfaz na falha de banco, FE2). Devolve o tempo de download e decodificação."""
    monitor = MonitorDaFonte()
    return asyncio.run(run_backfill_async(
        targets, region_id, writer, limitador=limitador, monitor=monitor, commodity_id=commodity_id
    ))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Importa o histórico de preços da Undermine Exchange (CU10-C1).")
    parser.add_argument("--regiao", type=str, default="US", help="Região (US ou EU).")
    parser.add_argument("--connected-id", type=str, default="3209", help="Connected Realm ID (default: 3209 = Azralon). Commodities fallback to the region's commodities id automatically.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of items to import (useful for quick presentations)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    from src.repositories.database import get_session, init_db
    from src.scraper.models import DISPARO_ADMIN
    from src.services.erros import RegiaoOuItemInvalidoError
    from src.services.importacao_historico import ImportacaoHistoricoService

    load_dotenv()
    init_db()

    session = get_session()
    try:
        servico = ImportacaoHistoricoService(session)
        ids = None
        if args.limit:
            ids = [int(item.external_item_id) for item in get_items_to_process(session)[:args.limit]]
            logger.info(f"Limiting import to {args.limit} items due to --limit argument")
        try:
            pedido = servico.validar(args.regiao, int(args.connected_id), ids)
        except RegiaoOuItemInvalidoError as e:
            logger.error(e.mensagem)
            sys.exit(1)
        id_execucao = servico.registrar_inicio(pedido, DISPARO_ADMIN)
        servico.executar(id_execucao, pedido, incremental=True)
        logger.info(f"Import finished: {servico.resumo(id_execucao)}")
    finally:
        session.close()
