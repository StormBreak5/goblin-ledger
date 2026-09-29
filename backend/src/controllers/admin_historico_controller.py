import dataclasses
import logging
from typing import Callable, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from src.controllers.deps import (
    exigir_admin,
    extrair_token,
    get_abridor_de_sessao,
    get_preenchedor_de_itens,
    get_relogio,
    traduzir_erros,
)
from src.models.historico_api_models import ImportacaoHistoricoRequest, ResumoImportacaoResponse
from src.scraper.models import DISPARO_ADMIN
from src.services import mensagens
from src.services.importacao_historico import ImportacaoHistoricoService, PedidoDeImportacao, ResumoDaImportacao

logger = logging.getLogger(__name__)

router = APIRouter(tags=["history"])


def _resposta(resumo: ResumoDaImportacao) -> ResumoImportacaoResponse:
    return ResumoImportacaoResponse(**dataclasses.asdict(resumo))


def _executar_em_segundo_plano(
    abrir_sessao: Callable, relogio: Callable, preenchedor: Callable[[], None], id_execucao: int, pedido: PedidoDeImportacao
) -> None:
    """CU10-C1 passos 3 a 10, depois da resposta ao Admin: a importação é longa (milhares de arquivos), então o pedido
    devolve o id da execução e o resumo é consultado por ele."""
    try:
        with abrir_sessao() as db:
            ImportacaoHistoricoService(db, relogio, preencher_itens_novos=preenchedor).executar(id_execucao, pedido)
    except Exception:
        logger.exception("CU10-C1: erro inesperado na importação %s.", id_execucao)


@router.post("/admin/history-import", response_model=ResumoImportacaoResponse, status_code=202)
def solicitar_importacao(
    dados: ImportacaoHistoricoRequest,
    tarefas: BackgroundTasks,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
    preenchedor: Callable[[], None] = Depends(get_preenchedor_de_itens),
):
    """
    CU10-C1 passos 1 e 2: o Admin informa a região e os itens; o sistema valida (FA1: 422 com o texto do cenário) e
    aceita a importação, que segue em segundo plano. Só uma importação roda por vez (409).
    """
    with traduzir_erros(mensagens.FALHA_NA_IMPORTACAO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        servico = ImportacaoHistoricoService(db, relogio)
        pedido = servico.validar(dados.regiao, dados.reino, dados.itens)
        id_execucao = servico.registrar_inicio(pedido, DISPARO_ADMIN)
        resumo = servico.resumo(id_execucao)

    tarefas.add_task(_executar_em_segundo_plano, abrir_sessao, relogio, preenchedor, id_execucao, pedido)
    return _resposta(resumo)


@router.get("/admin/history-import/{id_execucao}", response_model=ResumoImportacaoResponse)
def consultar_importacao(
    id_execucao: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU10-C1 passo 10: o resumo (ou o progresso) de uma importação."""
    with traduzir_erros(mensagens.FALHA_NA_IMPORTACAO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resposta(ImportacaoHistoricoService(db, relogio).resumo(id_execucao))


@router.get("/admin/history-import", response_model=list[ResumoImportacaoResponse])
def listar_importacoes(
    limite: int = Query(default=10, ge=1, le=50),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """As importações mais recentes."""
    with traduzir_erros(mensagens.FALHA_NA_IMPORTACAO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return [_resposta(resumo) for resumo in ImportacaoHistoricoService(db, relogio).listar(limite)]
