"""
Migrações do Alembic (src/migrations): o esquema que elas criam deve ser o dos modelos, e a baseline deve
funcionar tanto em banco novo quanto em um banco criado antes pelo `create_all`.
"""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from src.models.cobertura import AptidaoTreinamento  # noqa: F401
from src.models.evento import EventoJogo, ExtracaoEvento  # noqa: F401
from src.models.item import Item
from src.models.item_price import ItemPrice
from src.models.usuario import Sessao, TentativaLogin, TokenRecuperacao, Usuario
from src.repositories.database import Base, run_migrations
from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog

TABELAS_ANTIGAS = [Item.__table__, ItemPrice.__table__, HistoricalItemPrice.__table__, ScraperExecutionLog.__table__]
TODAS_AS_TABELAS = {
    "items", "item_prices", "historical_item_prices", "scraper_execution_logs",
    "usuario", "sessao", "token_recuperacao", "tentativa_login",
    "reino", "leilao", "ciclo_ingestao", "estado_mercado",
    "evento_jogo", "extracao_evento", "aptidao_treinamento",
}


def test_esquema_das_migracoes_corresponde_aos_modelos(pg_engine):
    with pg_engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao, opts={"compare_type": True}), Base.metadata)

    assert diferencas == []


def test_migracao_baseline_roda_sobre_banco_que_ja_tem_as_tabelas(banco_vazio):
    Base.metadata.create_all(banco_vazio, tables=TABELAS_ANTIGAS)  # como o banco criado antes do Alembic
    with banco_vazio.begin() as conexao:
        # O banco antigo não tem a chave única de item_prices (0006) nem as colunas acrescentadas pelas migrações 0003 e 0004.
        conexao.execute(text("ALTER TABLE item_prices DROP CONSTRAINT uq_item_prices_item_region_created"))
        conexao.execute(
            text("ALTER TABLE historical_item_prices DROP COLUMN origem, DROP COLUMN anomalia, DROP COLUMN granularidade")
        )
        conexao.execute(
            text(
                "ALTER TABLE scraper_execution_logs DROP COLUMN triggered_by, DROP COLUMN region, "
                "DROP COLUMN items_requested, DROP COLUMN items_created, DROP COLUMN items_without_data, DROP COLUMN items_failed, "
                "DROP COLUMN records_discarded, DROP COLUMN records_duplicated, DROP COLUMN failure_stage"
            )
        )
        conexao.execute(text("INSERT INTO historical_item_prices (item_id, region, timestamp, price) VALUES (1, '3209', now(), 5)"))

    run_migrations(banco_vazio)
    run_migrations(banco_vazio)  # rodar de novo não faz nada

    with banco_vazio.connect() as conexao:
        assert set(inspect(conexao).get_table_names()) - {"alembic_version"} == TODAS_AS_TABELAS
        assert conexao.execute(text("SELECT count(*) FROM historical_item_prices")).scalar() == 1  # dados preservados
        assert conexao.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0006"
        # linhas antigas ganham os valores padrão das colunas novas, sem reescrever a tabela
        assert conexao.execute(text("SELECT origem, anomalia, granularidade FROM historical_item_prices")).one() == (
            "UNDERMINE", False, "DIARIA",
        )
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


def test_cu10_migracao_4_marca_os_pontos_da_blizzard_como_horarios_rn16(banco_vazio):
    """A coluna `granularidade` (RN16) nasce `DIARIA` para o histórico da Undermine e `HORARIA` para o ciclo da Blizzard."""
    from alembic import command
    from alembic.config import Config
    from src.repositories.database import MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", MIGRATIONS_DIR)
    with banco_vazio.begin() as conexao:
        config.attributes["connection"] = conexao
        command.upgrade(config, "0003")
        conexao.execute(text(
            "INSERT INTO historical_item_prices (item_id, region, timestamp, price, origem) VALUES "
            "(1, '3209', '2026-09-01 00:00', 5, 'UNDERMINE'), (1, '3209', '2026-09-28 12:00', 6, 'BLIZZARD')"
        ))
        command.upgrade(config, "0004")

    with banco_vazio.connect() as conexao:
        linhas = conexao.execute(text("SELECT origem, granularidade FROM historical_item_prices ORDER BY timestamp")).all()
    assert [tuple(linha) for linha in linhas] == [("UNDERMINE", "DIARIA"), ("BLIZZARD", "HORARIA")]


def test_cu10_migracao_5_corrige_a_granularidade_dos_pontos_do_ciclo_horario_rn16(banco_vazio):
    """Os pontos da Blizzard gravados depois da 0004 (com o padrão `DIARIA`) passam a `HORARIA`; o histórico da Undermine
    e a granularidade das linhas diárias não mudam."""
    from alembic import command
    from alembic.config import Config
    from src.repositories.database import MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", MIGRATIONS_DIR)
    with banco_vazio.begin() as conexao:
        config.attributes["connection"] = conexao
        command.upgrade(config, "0004")
        conexao.execute(text(
            "INSERT INTO historical_item_prices (item_id, region, timestamp, price, origem, granularidade) VALUES "
            "(1, '3209', '2026-09-01 00:00', 5, 'UNDERMINE', 'DIARIA'), "
            "(1, '3209', '2026-09-01 13:00', 5, 'UNDERMINE', 'HORARIA'), "
            "(1, '3209', '2026-09-29 20:47', 6, 'BLIZZARD', 'DIARIA'), "  # o defeito: gravado com o padrão
            "(1, '32512', '2026-09-29 20:47', 7, 'BLIZZARD', 'HORARIA')"
        ))
        command.upgrade(config, "0005")

    with banco_vazio.connect() as conexao:
        linhas = conexao.execute(text(
            "SELECT origem, region, granularidade FROM historical_item_prices ORDER BY origem, region, timestamp"
        )).all()
    assert [tuple(linha) for linha in linhas] == [
        ("BLIZZARD", "3209", "HORARIA"), ("BLIZZARD", "32512", "HORARIA"),
        ("UNDERMINE", "3209", "DIARIA"), ("UNDERMINE", "3209", "HORARIA"),
    ]


def test_migracao_6_remove_leituras_repetidas_da_ficha_e_impede_novas(banco_vazio):
    """A Ficha passa a ter um preço por instante: repetidos anteriores ficam com um só (o de menor id) e o banco recusa novos."""
    import pytest
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import IntegrityError
    from src.repositories.database import MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", MIGRATIONS_DIR)
    with banco_vazio.begin() as conexao:
        config.attributes["connection"] = conexao
        command.upgrade(config, "0005")
        conexao.execute(text(
            "INSERT INTO item_prices (id, item_id, price_copper, region, created_at) VALUES "
            "('00000000-0000-0000-0000-000000000001', 122284, 100, 'us', '2026-09-29 22:03:07+00'), "
            "('00000000-0000-0000-0000-000000000002', 122284, 100, 'us', '2026-09-29 22:03:07+00'), "  # a mesma leitura
            "('00000000-0000-0000-0000-000000000003', 122284, 200, 'us', '2026-09-29 22:23:07+00'), "
            "('00000000-0000-0000-0000-000000000004', 122284, 100, 'eu', '2026-09-29 22:03:07+00')"  # outra região
        ))
        command.upgrade(config, "0006")

    with banco_vazio.connect() as conexao:
        ids = [linha[0] for linha in conexao.execute(text("SELECT id::text FROM item_prices ORDER BY id"))]
    assert ids == [f"00000000-0000-0000-0000-00000000000{n}" for n in (1, 3, 4)]

    with pytest.raises(IntegrityError):
        with banco_vazio.begin() as conexao:
            conexao.execute(text(
                "INSERT INTO item_prices (id, item_id, price_copper, region, created_at) VALUES "
                "(gen_random_uuid(), 122284, 300, 'us', '2026-09-29 22:23:07+00')"
            ))
