"""CU11 (RF08, RF12): modelo preditivo global.

Tabelas novas, desenhadas para os três cenários do CU11:
- `modelo_preditivo`: versões do modelo, com as datas de corte (RN25) e as métricas no período de teste; uma vigente por
  região (RN26);
- `execucao_treinamento`: pedidos de treinamento e o resumo de cada um (C1 passo 12, C1-FA2);
- `projecao_item`: situação atual da projeção de cada item elegível (RN10) ou o motivo de ter sido ignorado (C1-FA3);
- `predicao_diaria`: predições diárias e o erro observado (C3, RN13).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _lista(*valores: str) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.create_table(
        "modelo_preditivo",
        sa.Column("versao", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.Column("treinado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id_execucao", sa.Integer(), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("corte_validacao", sa.Date(), nullable=False),
        sa.Column("corte_teste", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        sa.Column("itens_elegiveis", sa.Integer(), nullable=False),
        sa.Column("itens_treino", sa.Integer(), nullable=False),
        sa.Column("itens_avaliados", sa.Integer(), nullable=False),
        sa.Column("amostras_treino", sa.Integer(), nullable=False),
        sa.Column("amostras_validacao", sa.Integer(), nullable=False),
        sa.Column("amostras_teste", sa.Integer(), nullable=False),
        sa.Column("epocas", sa.Integer(), nullable=False),
        sa.Column("melhor_epoca", sa.Integer(), nullable=False),
        sa.Column("segundos_por_epoca", sa.Float(), nullable=False),
        sa.Column("duracao_segundos", sa.Float(), nullable=False),
        sa.Column("mediana_mdape", sa.Float(), nullable=True),
        sa.Column("mediana_mdape_ingenuo", sa.Float(), nullable=True),
        sa.Column("mediana_mape", sa.Float(), nullable=True),
        sa.Column("mediana_mape_ingenuo", sa.Float(), nullable=True),
        sa.Column("mediana_rmse_cobre", sa.Float(), nullable=True),
        sa.Column("mediana_rmse_ingenuo_cobre", sa.Float(), nullable=True),
        sa.Column("itens_supera_ingenuo", sa.Integer(), nullable=True),
        sa.Column("caminho_artefatos", sa.String(length=255), nullable=False),
        sa.Column("assinatura_normalizacao", sa.String(length=64), nullable=False),
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("substituido_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("versao"),
    )
    op.create_index("uq_modelo_preditivo_vigente_por_regiao", "modelo_preditivo", ["regiao"], unique=True,
                    postgresql_where=sa.text("vigente"))

    op.create_table(
        "execucao_treinamento",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tipo", sa.String(length=15), nullable=False),
        sa.Column("disparo", sa.String(length=10), nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("solicitado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("andamento", sa.String(length=255), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=True),
        sa.Column("itens_elegiveis", sa.Integer(), nullable=True),
        sa.Column("itens_treino", sa.Integer(), nullable=True),
        sa.Column("itens_liberados", sa.Integer(), nullable=True),
        sa.Column("itens_bloqueados", sa.Integer(), nullable=True),
        sa.Column("bloqueados_acima_do_limiar", sa.Integer(), nullable=True),
        sa.Column("bloqueados_nao_supera_ingenuo", sa.Integer(), nullable=True),
        sa.Column("bloqueados_avaliacao_insuficiente", sa.Integer(), nullable=True),
        sa.Column("itens_ignorados", sa.Integer(), nullable=True),
        sa.Column("liberados_fora_do_treino", sa.Integer(), nullable=True),
        sa.Column("avisos", sa.Text(), nullable=True),
        sa.Column("etapa_da_falha", sa.String(length=10), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.CheckConstraint(f"tipo IN ({_lista('INICIAL', 'RETREINAMENTO')})", name="ck_execucao_treinamento_tipo"),
        sa.CheckConstraint(f"disparo IN ({_lista('ADMIN', 'AGENDADO')})", name="ck_execucao_treinamento_disparo"),
        sa.CheckConstraint(f"status IN ({_lista('AGUARDANDO', 'EXECUTANDO', 'SUCESSO', 'FALHA')})",
                           name="ck_execucao_treinamento_status"),
        sa.CheckConstraint(f"etapa_da_falha IN ({_lista('SELECAO', 'TREINO', 'BANCO', 'INTERNA')})",
                           name="ck_execucao_treinamento_etapa"),
        sa.ForeignKeyConstraint(["versao"], ["modelo_preditivo.versao"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execucao_treinamento_status", "execucao_treinamento", ["status"])

    op.create_table(
        "projecao_item",
        sa.Column("serie", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("integra_treino", sa.Boolean(), nullable=False),
        sa.Column("dias_avaliados", sa.Integer(), nullable=True),
        sa.Column("alvos_avaliados", sa.Integer(), nullable=True),
        sa.Column("mdape", sa.Float(), nullable=True),
        sa.Column("mdape_ingenuo", sa.Float(), nullable=True),
        sa.Column("mape", sa.Float(), nullable=True),
        sa.Column("mape_ingenuo", sa.Float(), nullable=True),
        sa.Column("rmse_cobre", sa.Float(), nullable=True),
        sa.Column("rmse_ingenuo_cobre", sa.Float(), nullable=True),
        sa.Column("erro_relativo_ingenuo", sa.Float(), nullable=True),
        sa.Column("situacao", sa.String(length=10), nullable=False),
        sa.Column("motivo", sa.String(length=40), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"situacao IN ({_lista('LIBERADA', 'BLOQUEADA', 'IGNORADO')})", name="ck_projecao_item_situacao"),
        sa.ForeignKeyConstraint(["versao"], ["modelo_preditivo.versao"]),
        sa.PrimaryKeyConstraint("serie", "item_id"),
    )
    op.create_index("ix_projecao_item_situacao", "projecao_item", ["situacao"])

    op.create_table(
        "predicao_diaria",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("data_previsao", sa.Date(), nullable=False),
        sa.Column("serie", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("h", sa.SmallInteger(), nullable=False),
        sa.Column("data_prevista", sa.Date(), nullable=False),
        sa.Column("preco_previsto", sa.BigInteger(), nullable=False),
        sa.Column("preco_real", sa.BigInteger(), nullable=True),
        sa.Column("erro_pct", sa.Float(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("h BETWEEN 1 AND 7", name="ck_predicao_diaria_h"),
        sa.ForeignKeyConstraint(["versao"], ["modelo_preditivo.versao"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "serie", "versao", "data_previsao", "h", name="uq_predicao_diaria"),
    )
    op.create_index("ix_predicao_diaria_data_prevista", "predicao_diaria", ["data_prevista"])


def downgrade() -> None:
    op.drop_index("ix_predicao_diaria_data_prevista", table_name="predicao_diaria")
    op.drop_table("predicao_diaria")
    op.drop_index("ix_projecao_item_situacao", table_name="projecao_item")
    op.drop_table("projecao_item")
    op.drop_index("ix_execucao_treinamento_status", table_name="execucao_treinamento")
    op.drop_table("execucao_treinamento")
    op.drop_index("uq_modelo_preditivo_vigente_por_regiao", table_name="modelo_preditivo")
    op.drop_table("modelo_preditivo")
