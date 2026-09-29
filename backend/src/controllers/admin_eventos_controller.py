from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query

from src.controllers.deps import (
    exigir_admin,
    extrair_token,
    get_abridor_de_sessao,
    get_baixador_de_pagina,
    get_fabrica_de_cliente_blizzard,
    get_relogio,
    traduzir_erros,
)
from src.models.evento import EventoJogo
from src.models.historico_api_models import (
    EventoManualRequest,
    EventoResponse,
    ExtracaoEventosRequest,
    ListaDeEventosResponse,
    ResumoExtracaoResponse,
)
from src.services import mensagens
from src.services.evento_service import EventoService, ResumoDaExtracao
from src.services.eventos.datas import formatar_data_br

router = APIRouter(tags=["events"])


def _evento(evento: EventoJogo) -> EventoResponse:
    return EventoResponse(
        id_evento=evento.id_evento, tipo=evento.tipo, nome=evento.nome, versao=evento.versao,
        data_inicio=formatar_data_br(evento.data_inicio), data_fim=formatar_data_br(evento.data_fim),
        regiao=evento.regiao, origem=evento.origem, fonte=evento.fonte,
    )


def _resumo(resumo: ResumoDaExtracao) -> ResumoExtracaoResponse:
    return ResumoExtracaoResponse(
        fonte=resumo.fonte, eventos_encontrados=resumo.encontrados, eventos_registrados=len(resumo.registrados),
        eventos_ignorados=resumo.ignorados, eventos=[_evento(evento) for evento in resumo.registrados],
    )


@router.post("/admin/events/extract", response_model=ResumoExtracaoResponse)
def extrair_eventos(
    dados: ExtracaoEventosRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
    baixar_pagina: Callable[[str], str] = Depends(get_baixador_de_pagina),
    fabrica_de_cliente: Callable = Depends(get_fabrica_de_cliente_blizzard),
):
    """
    CU10-C2 passos 1 a 6: o Admin escolhe a fonte (e, nas páginas de referência, o endereço); o sistema extrai os eventos,
    registra os novos e apresenta a relação. FA1: os que já constam são ignorados. FE1: 502 com o texto do cenário.
    """
    with traduzir_erros(mensagens.FALHA_NO_REGISTRO_DE_EVENTOS), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resumo(EventoService(db, relogio, baixar_pagina, fabrica_de_cliente).extrair(dados.fonte, dados.url))


@router.post("/admin/events", response_model=ResumoExtracaoResponse)
def cadastrar_evento_manual(
    dados: EventoManualRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU10-C2-FA2: cadastro manual de um evento (nome, versão, tipo e data em DD/MM/AAAA), validado antes de registrar."""
    with traduzir_erros(mensagens.FALHA_NO_REGISTRO_DE_EVENTOS), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        return _resumo(
            EventoService(db, relogio).cadastrar_manual(
                dados.nome, dados.versao, dados.tipo, dados.data_inicio, dados.data_fim, dados.regiao
            )
        )


@router.get("/admin/events", response_model=ListaDeEventosResponse)
def listar_eventos(
    tipo: Optional[str] = None,
    regiao: Optional[str] = None,
    limite: int = Query(default=100, ge=1, le=500),
    deslocamento: int = Query(default=0, ge=0),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """Os eventos registrados na base histórica, do mais recente para o mais antigo."""
    with traduzir_erros(mensagens.FALHA_NO_REGISTRO_DE_EVENTOS), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        total, eventos = EventoService(db, relogio).listar(tipo, regiao, limite, deslocamento)
        return ListaDeEventosResponse(total=total, eventos=[_evento(evento) for evento in eventos])
