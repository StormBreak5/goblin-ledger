from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ImportacaoHistoricoRequest(BaseModel):
    """CU10-C1 passo 1: a região, o reino conectado (opcional) e os itens cujo histórico será importado. Os valores
    são conferidos pelo serviço (FA1): o texto do erro é o do cenário, e não o do Pydantic."""
    regiao: str = ""
    reino: Optional[Any] = Field(default=None, description="Id do reino conectado; sem ele, o primeiro reino monitorado da região.")
    itens: Optional[list[Any]] = Field(default=None, description="Ids dos itens no WoW; sem eles, todos os itens ativos.")


class ResumoImportacaoResponse(BaseModel):
    """CU10-C1 passo 10: resumo da importação."""
    id_execucao: int
    status: str = Field(description="EM_ANDAMENTO, CONCLUIDA ou FALHA.")
    disparo: Optional[str] = Field(default=None, description="ADMIN ou RECUPERACAO.")
    regiao: Optional[str] = Field(default=None, description="Reino conectado consultado.")
    itens_solicitados: Optional[int] = None
    itens_processados: int = 0
    itens_cadastrados: int = Field(default=0, description="CU10-C1-FA2: itens que não existiam e foram cadastrados.")
    itens_sem_dados: int = Field(default=0, description="Itens para os quais a fonte não tem arquivo.")
    itens_com_erro: int = Field(default=0, description="Itens que a fonte não entregou por falha da rede ou dela.")
    registros_importados: int = 0
    registros_descartados: int = 0
    registros_duplicados: int = 0
    iniciada_em: datetime
    concluida_em: Optional[datetime] = None
    etapa_da_falha: Optional[str] = Field(default=None, description="FONTE (FE1), BANCO (FE2), FORMATO (FE3) ou INTERNA.")
    mensagem: Optional[str] = Field(default=None, description="Texto do fluxo de exceção, quando a importação falhou.")
    erro: Optional[str] = Field(default=None, description="Detalhe técnico registrado em log.")


class EventoManualRequest(BaseModel):
    """CU10-C2-FA2: cadastro manual de um evento. A data vem em DD/MM/AAAA; os campos são conferidos pelo serviço."""
    nome: str = ""
    versao: Optional[str] = None
    tipo: str = ""
    data_inicio: str = ""
    data_fim: Optional[str] = None
    regiao: str = "GLOBAL"


class ExtracaoEventosRequest(BaseModel):
    """CU10-C2 passo 1: a fonte dos eventos e, nas fontes de página (Wikipedia e Warcraft Wiki), o endereço dela."""
    fonte: str = ""
    url: Optional[str] = None


class EventoResponse(BaseModel):
    id_evento: int
    tipo: str
    nome: str
    versao: Optional[str] = None
    data_inicio: str = Field(description="DD/MM/AAAA")
    data_fim: Optional[str] = Field(default=None, description="DD/MM/AAAA")
    regiao: str
    origem: str
    fonte: Optional[str] = None


class ResumoExtracaoResponse(BaseModel):
    """CU10-C2 passo 6: os eventos registrados e o que foi ignorado por já constar (FA1)."""
    fonte: str
    eventos_encontrados: int
    eventos_registrados: int
    eventos_ignorados: int
    eventos: list[EventoResponse]


class ListaDeEventosResponse(BaseModel):
    total: int
    eventos: list[EventoResponse]


class ItemCoberturaResponse(BaseModel):
    item_id: int
    nome: Optional[str] = None
    situacao: str = Field(description='"Apto ao treinamento" ou "Inapto ao treinamento".')
    apto: bool
    periodo_continuo_dias: int
    inicio_periodo: Optional[date] = None
    fim_periodo: Optional[date] = None
    dias_com_dados: int


class ResumoCoberturaResponse(BaseModel):
    """CU10-C3 passo 6: aptos e inaptos, com o período contínuo de cada item."""
    validado_em: Optional[datetime] = None
    total: int
    aptos: int
    inaptos: int
    itens: list[ItemCoberturaResponse]
    pagina: int = 1
    tamanho_da_pagina: int = 50
