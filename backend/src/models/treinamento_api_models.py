from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TreinamentoRequest(BaseModel):
    """CU11-C1 passo 1: a região do treinamento inicial. O valor é conferido pelo serviço (RN11)."""
    regiao: str = ""


class ModeloResponse(BaseModel):
    """CU11-C1 passo 11: a versão registrada, com as datas de corte (RN25) e as métricas no período de teste."""
    versao: int
    treinado_em: datetime
    vigente: bool
    data_inicio: date
    corte_validacao: date
    corte_teste: date
    data_fim: date
    itens_avaliados: int
    amostras_treino: int
    amostras_validacao: int
    amostras_teste: int
    epocas: int
    melhor_epoca: int
    segundos_por_epoca: float
    duracao_segundos: float
    mediana_mdape: Optional[float] = Field(default=None, description="Mediana, entre os itens, do MdAPE do modelo (RN10).")
    mediana_mdape_ingenuo: Optional[float] = None
    mediana_mape: Optional[float] = None
    mediana_mape_ingenuo: Optional[float] = None
    itens_supera_ingenuo: Optional[int] = Field(default=None, description="Itens com MdAPE menor que o do ingênuo.")


class ResumoTreinamentoResponse(BaseModel):
    """CU11-C1 passo 12: resumo do treinamento (ou o andamento, enquanto ele roda)."""
    id_execucao: int
    tipo: str = Field(description="INICIAL (C1) ou RETREINAMENTO (C2).")
    disparo: str = Field(description="ADMIN ou AGENDADO.")
    regiao: str
    status: str = Field(description="AGUARDANDO, EXECUTANDO, SUCESSO ou FALHA.")
    solicitado_em: datetime
    iniciado_em: Optional[datetime] = None
    concluido_em: Optional[datetime] = None
    andamento: Optional[str] = Field(default=None, description="Etapa atual (e a época, durante o treino).")
    itens_elegiveis: Optional[int] = Field(default=None, description="RN02, RN07 e RN27.")
    itens_treino: Optional[int] = Field(default=None, description="Elegíveis aptos ao treinamento (RN15).")
    itens_liberados: Optional[int] = None
    itens_bloqueados: Optional[int] = None
    bloqueados_acima_do_limiar: Optional[int] = None
    bloqueados_nao_supera_ingenuo: Optional[int] = None
    bloqueados_avaliacao_insuficiente: Optional[int] = Field(default=None, description="CU11-C1-FA5.")
    itens_ignorados: Optional[int] = Field(default=None, description="CU11-C1-FA3.")
    liberados_fora_do_treino: Optional[int] = Field(default=None, description="Liberados que não integram o conjunto de treinamento.")
    liberados_sem_amostra_de_treino: Optional[int] = Field(
        default=None, description="Liberados sem nenhuma amostra no período de treinamento (não ajustaram os pesos).")
    ultimo_dia: Optional[date] = Field(default=None, description="RN25: último dia encerrado da série usada.")
    avisos: Optional[str] = None
    etapa_da_falha: Optional[str] = Field(default=None, description="SELECAO (FA1), TREINO (FE1), BANCO (FE2) ou INTERNA.")
    mensagem: Optional[str] = Field(default=None, description="Texto do cenário, quando o treinamento não foi concluído.")
    erro: Optional[str] = Field(default=None, description="Detalhe técnico registrado em log.")
    modelo: Optional[ModeloResponse] = None
