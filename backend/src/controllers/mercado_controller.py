from typing import Callable, Optional

from fastapi import APIRouter, Depends

from src.controllers.deps import (
    exigir_admin,
    extrair_token,
    get_abridor_de_sessao,
    get_fabrica_de_cliente_blizzard,
    get_relogio,
    traduzir_erros,
)
from src.models.mercado import ORIGEM_MANUAL
from src.models.mercado_api_models import (
    EstadoMercadoResponse,
    IngestaoRequest,
    ResultadoMercadoResponse,
    ResumoIngestaoResponse,
)
from src.repositories.mercado_repository import MercadoRepository
from src.services import mensagens, validacao
from src.services.erros import RegiaoInvalidaError
from src.services.ingestao_config import TIPO_LEILOES, Mercado, carregar_mercados
from src.services.ingestao_service import IngestaoService

router = APIRouter(tags=["market"])


def _mercados_da_ingestao(regiao: str, reino: Optional[int]) -> list[Mercado]:
    """CU09-C4 passo 1: o reino informado ou, sem ele, todos os mercados monitorados da região."""
    if reino is not None:
        return [Mercado(TIPO_LEILOES, regiao, reino, f"{regiao} reino {reino}")]
    return [mercado for mercado in carregar_mercados() if mercado.regiao == regiao]


@router.post("/admin/ingestion", response_model=ResumoIngestaoResponse)
def executar_ingestao_manual(
    dados: IngestaoRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
    fabrica_de_cliente: Callable = Depends(get_fabrica_de_cliente_blizzard),
):
    """
    CU09-C4: o Admin dispara a coleta, a sanitização e a consolidação (C1 a C3) da região ou do reino informado.
    O intervalo mínimo de 60 minutos vale também aqui (FA1: o resultado traz o horário em que a coleta é permitida);
    falhas de uma etapa vêm no resultado do mercado, com a etapa e o erro (FE1). Um mercado que falha ou é
    cancelado não impede os demais.
    """
    with traduzir_erros(mensagens.FALHA_NA_INGESTAO_MANUAL), abrir_sessao() as db:
        exigir_admin(db, token, relogio)
        regiao = validacao.normalizar_regiao(dados.regiao)
        mercados = _mercados_da_ingestao(regiao, dados.reino) if regiao else []
        if not mercados:
            raise RegiaoInvalidaError()

        servico = IngestaoService(db, fabrica_de_cliente(), relogio)
        resultados = [servico.executar(mercado, ORIGEM_MANUAL) for mercado in mercados]

    return ResumoIngestaoResponse(
        mercados=[
            ResultadoMercadoResponse(
                mercado=resultado.endpoint,
                status=resultado.status,
                leiloes_coletados=resultado.leiloes_coletados,
                leiloes_descartados=resultado.leiloes_descartados,
                itens_atualizados=resultado.itens_atualizados,
                itens_anomalos=resultado.itens_anomalos,
                itens_cadastrados=resultado.itens_cadastrados,
                proxima_permitida=resultado.proxima_permitida,
                etapa_da_falha=resultado.etapa_da_falha,
                erro=resultado.erro,
            )
            for resultado in resultados
        ],
        leiloes_coletados=sum(resultado.leiloes_coletados for resultado in resultados),
        leiloes_descartados=sum(resultado.leiloes_descartados for resultado in resultados),
        itens_atualizados=sum(resultado.itens_atualizados for resultado in resultados),
    )


@router.get("/market/status", response_model=list[EstadoMercadoResponse])
def estado_dos_mercados(abrir_sessao: Callable = Depends(get_abridor_de_sessao)):
    """RN09 / RN14: quando cada mercado foi atualizado pela última vez e se está sinalizado como "Dados Desatualizados"."""
    with traduzir_erros(mensagens.FALHA_NO_ESTADO_DO_MERCADO), abrir_sessao() as db:
        return [
            EstadoMercadoResponse(
                mercado=estado.mercado,
                ultima_atualizacao_em=estado.ultima_atualizacao_em,
                desatualizado=estado.desatualizado,
                ultima_falha_em=estado.ultima_falha_em,
            )
            for estado in MercadoRepository(db).estados()
        ]
