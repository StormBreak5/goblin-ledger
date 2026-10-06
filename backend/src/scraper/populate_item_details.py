"""
Completa os itens pela API de dados do jogo da Blizzard (`/data/wow/item/{id}` e `/data/wow/media/item/{id}`): nome e
ícone dos itens cadastrados com nome provisório (CU09-C3-FA1, CU10-C1-FA2) e os atributos fixos que o modelo preditivo
usa (variáveis 6, 7 e 15 a 17 do quadro de variáveis e filtro da RN07), gravados em `items.metadata_info`.

Para preencher de uma vez todos os itens existentes: `python -m src.scraper.populate_item_details` (a partir de backend/).
"""
import os
import sys
import logging
import asyncio
import aiohttp
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.repositories.database import init_db, get_session
from src.services.api_client import BlizzardApiClient
from src.models.item import Item, mesclar_metadata
from sqlalchemy.orm import Session
from sqlalchemy import String, bindparam, func, or_, update
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

# Limite da API da Blizzard: 100 requisições por segundo e 36.000 por hora. Com 10 itens ao mesmo tempo e a pausa de
# 0,1 s por item, o preenchimento fica bem abaixo dos dois (o ícone só é pedido para quem ainda não tem).
MAX_CONCURRENT_REQUESTS = 10
PAUSA_ENTRE_ITENS_SEGUNDOS = 0.1
TAMANHO_DO_LOTE = 1000

# Chaves gravadas em items.metadata_info (os nomes são os que estudos/lstm/io_dados.py lê).
ATRIBUTOS_ATUALIZADOS_EM = "atributos_atualizados_em"
ATRIBUTOS_INDISPONIVEIS = "atributos_indisponiveis"
CHAVE_DA_CLASSE = "item_class_id"

STATUS_ERRO_DE_REDE = 0

_ITENS = Item.__table__
GRAVAR_DETALHES = (
    update(_ITENS)
    .where(_ITENS.c.id == bindparam("b_id"))
    .values(
        name=bindparam("b_name"),
        icon_url=func.coalesce(bindparam("b_icon", type_=String), _ITENS.c.icon_url),
        metadata_info=mesclar_metadata(_ITENS.c.metadata_info, bindparam("b_meta", type_=JSONB)),
    )
)


@dataclass(frozen=True)
class ItemAPreencher:
    """O que a rotina precisa do item, lido antes das consultas (sem objetos do ORM, que expiram a cada commit)."""
    pk: Any
    item_id: int
    name: str
    icon_url: Optional[str]


@dataclass
class DetalhesDoItem:
    """Resposta da API para um item. `status` é o do endpoint do item (0 = falha de rede); os demais campos só vêm no 200."""
    status: int
    name: Optional[str] = None
    icon_url: Optional[str] = None
    atributos: Optional[Dict[str, Any]] = None


@dataclass
class ResumoDoPreenchimento:
    selecionados: int = 0
    gravados: int = 0
    indisponiveis: int = 0
    com_erro: int = 0


def extrair_atributos(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Atributos fixos do item na resposta de `/data/wow/item/{id}`: classe e subclasse (variáveis 6 e 15), qualidade e
    nível (variável 16, filtro da RN07) e preço de venda ao vendedor (variáveis 7 e 17), que a API já dá em Cobre (RN01).
    O que a resposta não trouxer fica nulo."""
    def _campo(chave: str, subchave: str) -> Any:
        valor = dados.get(chave)
        return valor.get(subchave) if isinstance(valor, dict) else None

    return {
        "item_class_id": _campo("item_class", "id"),
        "item_subclass_id": _campo("item_subclass", "id"),
        "quality": _campo("quality", "type"),
        "level": dados.get("level"),
        "sell_price": dados.get("sell_price"),
    }


async def fetch_item_details(
    session: aiohttp.ClientSession, item_id: int, token: str, region: str = "us", buscar_icone: bool = True
) -> DetalhesDoItem:
    """
    Consulta o item na API da Blizzard: nome e atributos fixos e, se `buscar_icone`, o ícone. Um erro no ícone não
    descarta o que veio do item.
    """
    namespace = f"static-{region}"
    locale = "en_US" if region == "us" else "en_GB"
    headers = {"Authorization": f"Bearer {token}"}

    item_url = f"https://{region}.api.blizzard.com/data/wow/item/{item_id}?namespace={namespace}&locale={locale}"
    media_url = f"https://{region}.api.blizzard.com/data/wow/media/item/{item_id}?namespace={namespace}&locale={locale}"

    try:
        async with session.get(item_url, headers=headers) as resp:
            if resp.status != 200:
                return DetalhesDoItem(status=resp.status)
            data = await resp.json()
    except Exception as e:
        logger.error(f"Error fetching details for item {item_id}: {e}")
        return DetalhesDoItem(status=STATUS_ERRO_DE_REDE)

    # O nome pode vir como um objeto com traduções ou direto dependendo do endpoint/locale
    name = data["name"].get("en_US") if isinstance(data.get("name"), dict) else data.get("name")
    detalhes = DetalhesDoItem(status=200, name=name, atributos=extrair_atributos(data))

    if buscar_icone:
        try:
            async with session.get(media_url, headers=headers) as resp:
                if resp.status == 200:
                    media = await resp.json()
                    for asset in media.get("assets", []):
                        if asset.get("key") == "icon":
                            detalhes.icon_url = asset.get("value")
                            break
        except Exception as e:
            logger.error(f"Error fetching the icon of item {item_id}: {e}")

    return detalhes


async def worker(
    item: ItemAPreencher, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, token: str,
    results: Dict[int, DetalhesDoItem],
) -> None:
    async with semaphore:
        results[item.item_id] = await fetch_item_details(session, item.item_id, token, buscar_icone=item.icon_url is None)
        logger.debug(f"Item {item.item_id}: HTTP {results[item.item_id].status}")
        await asyncio.sleep(PAUSA_ENTRE_ITENS_SEGUNDOS)  # Small delay to avoid hammering the API too hard


async def run_population_async(items: List[ItemAPreencher], token: str) -> Dict[int, DetalhesDoItem]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    results: Dict[int, DetalhesDoItem] = {}

    async with aiohttp.ClientSession() as session:
        tasks = [worker(item, semaphore, session, token, results) for item in items]
        await asyncio.gather(*tasks)

    return results


def selecionar_itens(db_session: Session) -> List[ItemAPreencher]:
    """Itens com nome provisório ("Item {id}"), sem ícone ou ainda sem os atributos fixos. Os que a API já disse não ter
    (404, marcados com `atributos_indisponiveis`) ficam fora: não são consultados de novo a cada execução."""
    metadata = Item.metadata_info
    sem_atributos = ~func.coalesce(metadata.has_key(CHAVE_DA_CLASSE), False)
    indisponivel = func.coalesce(metadata.contains({ATRIBUTOS_INDISPONIVEIS: True}), False)
    linhas = (
        db_session.query(Item.id, Item.external_item_id, Item.name, Item.icon_url)
        .filter(
            Item.game == "wow",
            or_(Item.name.like("Item %"), Item.icon_url.is_(None), sem_atributos),
            ~indisponivel,
        )
        .order_by(Item.external_item_id)
        .all()
    )
    return [
        ItemAPreencher(pk=pk, item_id=int(external_id), name=name, icon_url=icon_url)
        for pk, external_id, name, icon_url in linhas
        if external_id.isdigit()
    ]


def _linhas_a_gravar(
    lote: List[ItemAPreencher], resultados: Dict[int, DetalhesDoItem], agora: str, resumo: ResumoDoPreenchimento
) -> List[Dict[str, Any]]:
    """Mescla os atributos (ou a marca de indisponível, no 404) no metadata_info; o ícone só troca se veio um novo.
    429, 5xx e falha de rede não gravam nada: o item fica para a próxima execução."""
    linhas = []
    for item in lote:
        detalhes = resultados.get(item.item_id, DetalhesDoItem(status=STATUS_ERRO_DE_REDE))
        if detalhes.status == 200:
            meta = {**(detalhes.atributos or {}), ATRIBUTOS_ATUALIZADOS_EM: agora}
            linhas.append({"b_id": item.pk, "b_name": detalhes.name or item.name, "b_icon": detalhes.icon_url, "b_meta": meta})
            resumo.gravados += 1
        elif detalhes.status == 404:
            logger.warning(
                f"Item {item.item_id} não existe na API de dados do jogo (404): marcado com {ATRIBUTOS_INDISPONIVEIS} e "
                "não será consultado de novo."
            )
            meta = {ATRIBUTOS_INDISPONIVEIS: True, ATRIBUTOS_ATUALIZADOS_EM: agora}
            linhas.append({"b_id": item.pk, "b_name": item.name, "b_icon": None, "b_meta": meta})
            resumo.indisponiveis += 1
        else:
            resumo.com_erro += 1
    return linhas


def populate_details(
    db_session: Optional[Session] = None,
    token: Optional[str] = None,
    relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Optional[ResumoDoPreenchimento]:
    """
    Preenche nome, ícone e atributos fixos dos itens selecionados, em lotes, mesclando no `metadata_info` (o ETag e a
    origem do CU10-C1 continuam lá). `db_session` e `token` só são informados pelos testes.
    """
    logger.info("Iniciando população de detalhes dos itens (nomes, ícones e atributos)...")

    if token is None:
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error("Credenciais da Blizzard ausentes. População cancelada.")
            return None

        token = BlizzardApiClient(client_id, client_secret).auth_manager.get_token()

    sessao_propria = db_session is None
    db_session = db_session or get_session()
    resumo = ResumoDoPreenchimento()

    try:
        items_to_update = selecionar_itens(db_session)
        resumo.selecionados = len(items_to_update)
        logger.info(f"Encontrados {len(items_to_update)} itens para atualizar.")

        if not items_to_update:
            return resumo

        total_de_lotes = (len(items_to_update) + TAMANHO_DO_LOTE - 1) // TAMANHO_DO_LOTE
        for numero, inicio in enumerate(range(0, len(items_to_update), TAMANHO_DO_LOTE), start=1):
            lote = items_to_update[inicio:inicio + TAMANHO_DO_LOTE]
            antes = (resumo.gravados, resumo.indisponiveis, resumo.com_erro)

            resultados = asyncio.run(run_population_async(lote, token))
            linhas = _linhas_a_gravar(lote, resultados, relogio().isoformat(), resumo)
            if linhas:
                db_session.execute(GRAVAR_DETALHES, linhas)
                db_session.commit()

            logger.info(
                f"Lote {numero} de {total_de_lotes}: {resumo.gravados - antes[0]} gravados, "
                f"{resumo.indisponiveis - antes[1]} sem dados na API (404), "
                f"{resumo.com_erro - antes[2]} com erro (ficam para a próxima execução)."
            )

        logger.info(
            f"População concluída: {resumo.gravados} itens gravados, {resumo.indisponiveis} sem dados na API, "
            f"{resumo.com_erro} com erro, de {resumo.selecionados} selecionados."
        )
    except Exception as e:
        logger.error(f"Erro ao popular detalhes dos itens: {e}")
        db_session.rollback()
    finally:
        if sessao_propria:
            db_session.close()

    return resumo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    load_dotenv()
    init_db()
    populate_details()
