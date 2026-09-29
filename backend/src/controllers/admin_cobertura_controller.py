from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query

from src.controllers.deps import exigir_admin, extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.historico_api_models import ItemCoberturaResponse, ResumoCoberturaResponse
from src.services import mensagens
from src.services.cobertura_service import CoberturaService, ResumoDaCobertura

router = APIRouter(tags=["coverage"])


def _resposta(resumo: ResumoDaCobertura) -> ResumoCoberturaResponse:
    return ResumoCoberturaResponse(
        validado_em=resumo.validado_em,
        total=resumo.total,
        aptos=resumo.aptos,
        inaptos=resumo.inaptos,
        pagina=resumo.pagina,
        tamanho_da_pagina=resumo.tamanho_da_pagina,
        itens=[
            ItemCoberturaResponse(
                item_id=item.item_id,
                nome=item.nome,
                situacao=mensagens.APTO_AO_TREINAMENTO if item.apto else mensagens.INAPTO_AO_TREINAMENTO,
                apto=item.apto,
                periodo_continuo_dias=item.periodo_continuo_dias,
                inicio_periodo=item.inicio_periodo,
                fim_periodo=item.fim_periodo,
                dias_com_dados=item.dias_com_dados,
            )
            for item in resumo.itens
        ],
    )


@router.post("/admin/history-coverage", response_model=ResumoCoberturaResponse)
def validar_cobertura(
    tamanho: int = Query(default=50, ge=1, le=500),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """
    CU10-C3: o Admin solicita a validação; o sistema calcula o maior período contínuo de cada item ativo, classifica
    (apto/inapto ao treinamento, RN15) e apresenta a relação. FE1: falha de banco não altera a classificação anterior.
    """
    with traduzir_erros(mensagens.FALHA_NA_VALIDACAO_DA_COBERTURA), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resposta(CoberturaService(db, relogio).validar(1, tamanho))


@router.get("/admin/history-coverage", response_model=ResumoCoberturaResponse)
def consultar_cobertura(
    situacao: Optional[str] = Query(default=None, description="APTO ou INAPTO."),
    pagina: int = Query(default=1, ge=1),
    tamanho: int = Query(default=50, ge=1, le=500),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """A última validação: aptos e inaptos, com o período contínuo de cada item, do maior para o menor."""
    with traduzir_erros(mensagens.FALHA_NA_VALIDACAO_DA_COBERTURA), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resposta(CoberturaService(db, relogio).consultar(situacao, pagina, tamanho))
