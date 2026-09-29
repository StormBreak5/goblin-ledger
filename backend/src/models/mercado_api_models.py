from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IngestaoRequest(BaseModel):
    """CU09-C4 passo 1: o Admin informa a região (US/EU) e, opcionalmente, um reino conectado dessa região."""
    regiao: str = ""
    reino: Optional[int] = Field(default=None, description="Id do reino conectado; sem ele, coleta todos os mercados da região.")


class ResultadoMercadoResponse(BaseModel):
    mercado: str
    status: str = Field(description="SUCESSO, FALHA ou CANCELADO (intervalo mínimo não atingido).")
    leiloes_coletados: int = 0
    leiloes_descartados: int = 0
    itens_atualizados: int = 0
    itens_anomalos: int = 0
    itens_cadastrados: int = 0
    proxima_permitida: Optional[datetime] = Field(default=None, description="CU09-C4-FA1: quando uma nova coleta será permitida.")
    etapa_da_falha: Optional[str] = Field(default=None, description="CU09-C4-FE1: COLETA, SANITIZACAO ou CONSOLIDACAO.")
    erro: Optional[str] = None


class ResumoIngestaoResponse(BaseModel):
    """CU09-C4 passo 4: resumo do ciclo, por mercado e no total."""
    mercados: list[ResultadoMercadoResponse]
    leiloes_coletados: int
    leiloes_descartados: int
    itens_atualizados: int


class EstadoMercadoResponse(BaseModel):
    """RN09 / RN14: frescor dos dados e sinalização "Dados Desatualizados" de cada mercado."""
    mercado: str
    ultima_atualizacao_em: Optional[datetime]
    desatualizado: bool
    ultima_falha_em: Optional[datetime]
