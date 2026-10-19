"""CU11 – Treinar Modelo: versões do modelo preditivo global, execuções de treinamento, situação da projeção de cada
item e predições diárias (RN13). Nenhuma destas tabelas consta no MR do TC; a `predicao_diaria` corresponde à entidade
`Predicao` do MR, com o preço em Cobre (RN01) no lugar de `preco_predito VARCHAR(45)` e sem intervalo de confiança nem
tendência (o modelo prevê só a mediana dos próximos 7 dias)."""
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer,
                        SmallInteger, String, Text, UniqueConstraint, text)

from src.repositories.database import Base

# execucao_treinamento.tipo / disparo / status / etapa_da_falha
TIPO_INICIAL = "INICIAL"  # CU11-C1
TIPO_RETREINAMENTO = "RETREINAMENTO"  # CU11-C2
TIPOS_DE_EXECUCAO = (TIPO_INICIAL, TIPO_RETREINAMENTO)
DISPARO_ADMIN = "ADMIN"
DISPARO_AGENDADO = "AGENDADO"
DISPAROS = (DISPARO_ADMIN, DISPARO_AGENDADO)
STATUS_AGUARDANDO = "AGUARDANDO"  # na fila: o serviço `modelo` ainda não o pegou
STATUS_EXECUTANDO = "EXECUTANDO"
STATUS_SUCESSO = "SUCESSO"
STATUS_FALHA = "FALHA"
STATUS_DE_EXECUCAO = (STATUS_AGUARDANDO, STATUS_EXECUTANDO, STATUS_SUCESSO, STATUS_FALHA)
STATUS_EM_ANDAMENTO = (STATUS_AGUARDANDO, STATUS_EXECUTANDO)  # CU11-C1-FA2
ETAPA_SELECAO = "SELECAO"  # CU11-C1-FA1: nenhum item apto ao treinamento
ETAPA_TREINO = "TREINO"  # CU11-C1-FE1: o treinamento não convergiu ou faltou recurso
ETAPA_BANCO = "BANCO"  # CU11-C1-FE2: falha de leitura ou gravação no banco
ETAPA_INTERNA = "INTERNA"  # erro inesperado ou execução interrompida (o processo parou)
ETAPAS_DE_FALHA = (ETAPA_SELECAO, ETAPA_TREINO, ETAPA_BANCO, ETAPA_INTERNA)

# projecao_item.situacao / motivo (RN10, RN13, RN27)
SITUACAO_LIBERADA = "LIBERADA"
SITUACAO_BLOQUEADA = "BLOQUEADA"
SITUACAO_IGNORADA = "IGNORADA"  # CU11-C1-FA3 (RF08: 'Liberada', 'Bloqueada' ou 'Ignorada')
SITUACOES = (SITUACAO_LIBERADA, SITUACAO_BLOQUEADA, SITUACAO_IGNORADA)
MOTIVO_ACIMA_DO_LIMIAR = "acima do limiar"  # CU11-C1-FA4 (RN10)
MOTIVO_NAO_SUPERA_INGENUO = "não supera o ingênuo"  # CU11-C1-FA4 (RN10)
MOTIVO_AVALIACAO_INSUFICIENTE = "avaliação insuficiente"  # CU11-C1-FA5 (RN10)
MOTIVO_DEIXOU_DE_SER_ELEGIVEL = "deixou de ser elegível"  # CU11-C2-FA1
MOTIVO_DEGRADACAO = "degradação"  # CU11-C3-FA3 (RN13)
MOTIVO_SERIE_INSUFICIENTE = "série insuficiente"  # CU11-C1-FA3
# CU11-C2 passo 7 (RN26): o modelo novo substitui o vigente ou é descartado (FA2).
DECISAO_SUBSTITUIDO = "SUBSTITUIDO"
DECISAO_MANTIDO = "MANTIDO"
DECISOES = (DECISAO_SUBSTITUIDO, DECISAO_MANTIDO)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


class ModeloPreditivo(Base):
    """CU11-C1 passo 11 / RF08: uma versão do modelo global, com as datas de corte (RN25) e as métricas no período de
    teste. Os artefatos (pesos, constantes de normalização e escala do alvo) ficam em `caminho_artefatos`; para prever
    com uma versão, usam-se sempre as constantes dela. Só uma versão é a vigente em cada região (RN26)."""
    __tablename__ = "modelo_preditivo"

    versao = Column(Integer, primary_key=True, autoincrement=True)
    regiao = Column(String(2), nullable=False)
    treinado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    id_execucao = Column(Integer, nullable=True)
    data_inicio = Column(Date, nullable=False)
    corte_validacao = Column(Date, nullable=False)
    corte_teste = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    itens_elegiveis = Column(Integer, nullable=False)
    itens_treino = Column(Integer, nullable=False)
    itens_avaliados = Column(Integer, nullable=False)
    amostras_treino = Column(Integer, nullable=False)
    amostras_validacao = Column(Integer, nullable=False)
    amostras_teste = Column(Integer, nullable=False)
    epocas = Column(Integer, nullable=False)
    melhor_epoca = Column(Integer, nullable=False)
    segundos_por_epoca = Column(Float, nullable=False)
    duracao_segundos = Column(Float, nullable=False)
    mediana_mdape = Column(Float, nullable=True)
    mediana_mdape_ingenuo = Column(Float, nullable=True)
    mediana_mape = Column(Float, nullable=True)
    mediana_mape_ingenuo = Column(Float, nullable=True)
    mediana_rmse_cobre = Column(Float, nullable=True)
    mediana_rmse_ingenuo_cobre = Column(Float, nullable=True)
    itens_supera_ingenuo = Column(Integer, nullable=True)
    caminho_artefatos = Column(String(255), nullable=False)
    assinatura_normalizacao = Column(String(64), nullable=False)
    vigente = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    substituido_em = Column(DateTime(timezone=True), nullable=True)
    # CU11-C2-FA2: o modelo novo que não superou o vigente fica registrado, com as métricas e os artefatos.
    descartado = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    __table_args__ = (
        Index("uq_modelo_preditivo_vigente_por_regiao", "regiao", unique=True, postgresql_where=text("vigente")),
    )


class ExecucaoTreinamento(Base):
    """CU11-C1 (e C2): pedido de treinamento e o seu resumo (passo 12). A API registra o pedido (`AGUARDANDO`) e o
    serviço `modelo` o executa; só um treinamento roda por vez (FA2)."""
    __tablename__ = "execucao_treinamento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(15), nullable=False)
    disparo = Column(String(10), nullable=False)
    regiao = Column(String(2), nullable=False)
    status = Column(String(10), nullable=False)
    solicitado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    iniciado_em = Column(DateTime(timezone=True), nullable=True)
    concluido_em = Column(DateTime(timezone=True), nullable=True)
    andamento = Column(String(255), nullable=True)
    versao = Column(Integer, ForeignKey("modelo_preditivo.versao"), nullable=True)
    itens_elegiveis = Column(Integer, nullable=True)
    itens_treino = Column(Integer, nullable=True)
    itens_liberados = Column(Integer, nullable=True)
    itens_bloqueados = Column(Integer, nullable=True)
    bloqueados_acima_do_limiar = Column(Integer, nullable=True)
    bloqueados_nao_supera_ingenuo = Column(Integer, nullable=True)
    bloqueados_avaliacao_insuficiente = Column(Integer, nullable=True)
    itens_ignorados = Column(Integer, nullable=True)
    liberados_fora_do_treino = Column(Integer, nullable=True)
    # Liberados sem nenhuma amostra no período de treinamento: integram o conjunto de treinamento (RN15), mas foram
    # lançados depois do fim desse período e não ajustaram os pesos (migração 0008).
    liberados_sem_amostra_de_treino = Column(Integer, nullable=True)
    ultimo_dia = Column(Date, nullable=True)  # RN25: último dia encerrado da série usada
    # CU11-C2 (migração 0009): a comparação com o vigente no mesmo período de teste (RN26) e o FA1.
    versao_anterior = Column(Integer, ForeignKey("modelo_preditivo.versao"), nullable=True)
    decisao = Column(String(12), nullable=True)
    mdape_novo = Column(Float, nullable=True)
    mdape_vigente = Column(Float, nullable=True)
    itens_comparados = Column(Integer, nullable=True)
    deixaram_de_ser_elegiveis = Column(Integer, nullable=True)
    liberados_que_deixaram_de_ser_elegiveis = Column(Integer, nullable=True)
    avisos = Column(Text, nullable=True)
    etapa_da_falha = Column(String(10), nullable=True)
    erro = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_DE_EXECUCAO)})", name="ck_execucao_treinamento_tipo"),
        CheckConstraint(f"disparo IN ({_lista_sql(DISPAROS)})", name="ck_execucao_treinamento_disparo"),
        CheckConstraint(f"status IN ({_lista_sql(STATUS_DE_EXECUCAO)})", name="ck_execucao_treinamento_status"),
        CheckConstraint(f"etapa_da_falha IN ({_lista_sql(ETAPAS_DE_FALHA)})", name="ck_execucao_treinamento_etapa"),
        CheckConstraint(f"decisao IN ({_lista_sql(DECISOES)})", name="ck_execucao_treinamento_decisao"),
        Index("ix_execucao_treinamento_status", "status"),
    )


class ProjecaoItem(Base):
    """RF08 / RN10: situação atual da projeção de cada item elegível (`LIBERADA` ou `BLOQUEADA`, com o motivo) ou
    `IGNORADA` (CU11-C1-FA3), com as métricas do item no período de teste da versão que o avaliou. `item_id` é o
    identificador do item no WoW e `serie` a região da série histórica (historical_item_prices.region)."""
    __tablename__ = "projecao_item"

    serie = Column(String(50), primary_key=True)
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    regiao = Column(String(2), nullable=False)
    versao = Column(Integer, ForeignKey("modelo_preditivo.versao"), nullable=False)
    integra_treino = Column(Boolean, nullable=False)
    dias_avaliados = Column(Integer, nullable=True)
    alvos_avaliados = Column(Integer, nullable=True)
    mdape = Column(Float, nullable=True)
    mdape_ingenuo = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)
    mape_ingenuo = Column(Float, nullable=True)
    rmse_cobre = Column(Float, nullable=True)
    rmse_ingenuo_cobre = Column(Float, nullable=True)
    erro_relativo_ingenuo = Column(Float, nullable=True)
    situacao = Column(String(10), nullable=False)
    motivo = Column(String(40), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)

    __table_args__ = (
        CheckConstraint(f"situacao IN ({_lista_sql(SITUACOES)})", name="ck_projecao_item_situacao"),
        Index("ix_projecao_item_situacao", "situacao"),
    )


class PredicaoDiaria(Base):
    """CU11-C3 / RN13: predição de um item para um dia do horizonte e, depois, o valor real e o erro. Preço real e erro
    nulos correspondem a "N/D" (C3-FA2). Preços em Cobre (RN01)."""
    __tablename__ = "predicao_diaria"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    data_previsao = Column(Date, nullable=False)
    serie = Column(String(50), nullable=False)
    item_id = Column(Integer, nullable=False)
    versao = Column(Integer, ForeignKey("modelo_preditivo.versao"), nullable=False)
    h = Column(SmallInteger, nullable=False)
    data_prevista = Column(Date, nullable=False)
    preco_previsto = Column(BigInteger, nullable=False)
    preco_real = Column(BigInteger, nullable=True)
    erro_pct = Column(Float, nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)

    __table_args__ = (
        UniqueConstraint("item_id", "serie", "versao", "data_previsao", "h", name="uq_predicao_diaria"),
        CheckConstraint("h BETWEEN 1 AND 7", name="ck_predicao_diaria_h"),
        Index("ix_predicao_diaria_data_prevista", "data_prevista"),
    )
