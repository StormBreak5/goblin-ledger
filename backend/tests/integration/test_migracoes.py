"""
Migrações do Alembic (src/migrations): o esquema que elas criam deve ser o dos modelos, e a baseline deve
funcionar tanto em banco novo quanto em um banco criado antes pelo `create_all`.
"""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from src.models.item import Item
from src.models.item_price import ItemPrice
from src.models.usuario import Sessao, TentativaLogin, TokenRecuperacao, Usuario
from src.repositories.database import Base, run_migrations
from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog

TABELAS_ANTIGAS = [Item.__table__, ItemPrice.__table__, HistoricalItemPrice.__table__, ScraperExecutionLog.__table__]
TODAS_AS_TABELAS = {
    "items", "item_prices", "historical_item_prices", "scraper_execution_logs",
    "usuario", "sessao", "token_recuperacao", "tentativa_login",
}


def test_esquema_das_migracoes_corresponde_aos_modelos(pg_engine):
    with pg_engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao, opts={"compare_type": True}), Base.metadata)

    assert diferencas == []


def test_migracao_baseline_roda_sobre_banco_que_ja_tem_as_tabelas(banco_vazio):
    Base.metadata.create_all(banco_vazio, tables=TABELAS_ANTIGAS)  # como o banco criado antes do Alembic
    with banco_vazio.begin() as conexao:
        conexao.execute(text("INSERT INTO historical_item_prices (item_id, region, timestamp, price) VALUES (1, '3209', now(), 5)"))

    run_migrations(banco_vazio)
    run_migrations(banco_vazio)  # rodar de novo não faz nada

    with banco_vazio.connect() as conexao:
        assert set(inspect(conexao).get_table_names()) - {"alembic_version"} == TODAS_AS_TABELAS
        assert conexao.execute(text("SELECT count(*) FROM historical_item_prices")).scalar() == 1  # dados preservados
        assert conexao.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
        assert conexao.execute(text("SELECT count(*) FROM pg_extension WHERE extname = 'unaccent'")).scalar() == 1


def test_migracao_2_remove_dados_do_usuario_em_cascata_rn20(pg_engine, db_session):
    usuario = Usuario(email="a@b.com", senha_hash="x", regiao="US")
    db_session.add(usuario)
    db_session.flush()
    from datetime import datetime, timedelta, timezone
    agora = datetime.now(timezone.utc)
    db_session.add(Sessao(id_usuario=usuario.id_usuario, expira_em=agora + timedelta(hours=1)))
    db_session.add(TokenRecuperacao(id_usuario=usuario.id_usuario, token_hash="h" * 64, expira_em=agora + timedelta(minutes=10)))
    db_session.commit()

    db_session.delete(usuario)
    db_session.commit()

    assert db_session.query(Sessao).count() == 0
    assert db_session.query(TokenRecuperacao).count() == 0
