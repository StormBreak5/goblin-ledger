import dataclasses
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query

from src.controllers.deps import exigir_admin, extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.treinamento_api_models import ResumoTreinamentoResponse, TreinamentoRequest
from src.services import mensagens
from src.services.treinamento_service import ResumoDoTreinamento, TreinamentoService

router = APIRouter(tags=["model"])


def _resposta(resumo: ResumoDoTreinamento) -> ResumoTreinamentoResponse:
    return ResumoTreinamentoResponse(**dataclasses.asdict(resumo))


@router.post("/admin/model-training", response_model=ResumoTreinamentoResponse, status_code=202)
def solicitar_treinamento(
    dados: TreinamentoRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """
    CU11-C1 passo 1: o Admin solicita o treinamento inicial, informando a região. O pedido entra na fila e é executado
    pelo serviço `modelo` (passos 2 a 12); o resumo é consultado pelo id. Só um treinamento roda por vez (FA2: 409).
    """
    with traduzir_erros(mensagens.FALHA_NO_TREINAMENTO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        servico = TreinamentoService(db, relogio)
        regiao = servico.validar_regiao(dados.regiao)
        return _resposta(servico.resumo(servico.registrar_pedido(regiao)))


@router.get("/admin/model-training/{id_execucao}", response_model=ResumoTreinamentoResponse)
def consultar_treinamento(
    id_execucao: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU11-C1 passo 12: o resumo (ou o andamento) de um treinamento."""
    with traduzir_erros(mensagens.FALHA_NO_TREINAMENTO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resposta(TreinamentoService(db, relogio).resumo(id_execucao))


@router.get("/admin/model-training", response_model=list[ResumoTreinamentoResponse])
def listar_treinamentos(
    limite: int = Query(default=10, ge=1, le=50),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """Os treinamentos mais recentes."""
    with traduzir_erros(mensagens.FALHA_NO_TREINAMENTO), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return [_resposta(resumo) for resumo in TreinamentoService(db, relogio).listar(limite)]
