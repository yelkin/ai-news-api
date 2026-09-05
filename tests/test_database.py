from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


def test_migrations_support_vectors_and_repeated_upgrades(session):
    """As a developer, I can migrate a database and store job embeddings."""
    engine = session.get_bind()
    session.rollback()
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert (
            connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            )
            == "vector"
        )
        assert "embedding" in {
            c["name"] for c in inspect(connection).get_columns("job_postings")
        }
        command.downgrade(config, "0001")
        assert "embedding" not in {
            c["name"] for c in inspect(connection).get_columns("job_postings")
        }
        command.upgrade(config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        )


def test_initial_migration_carries_over_legacy_initialization(session):
    """As a developer, I can move an existing initialized schema under Alembic."""
    session.rollback()
    config = Config("alembic.ini")
    with session.get_bind().begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(text("ALTER TABLE job_postings DROP COLUMN enriched_at"))
        connection.execute(
            text("ALTER TABLE job_postings DROP COLUMN enrichment_error")
        )
        connection.execute(
            text("ALTER TABLE job_postings ALTER COLUMN qualifications SET NOT NULL")
        )
        command.upgrade(config, "head")
        columns = {
            c["name"]: c for c in inspect(connection).get_columns("job_postings")
        }
        assert columns["qualifications"]["nullable"]
        assert {"enriched_at", "enrichment_error", "embedding"} <= columns.keys()
