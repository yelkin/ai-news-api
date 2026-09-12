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
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
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


def test_skill_fit_migration_backfills_existing_posting_and_indexes(session):
    """As an existing user, migration preserves postings and builds searchable content."""
    session.rollback()
    config = Config("alembic.ini")
    with session.get_bind().begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0002")
        connection.execute(
            text("""INSERT INTO job_postings
            (platform,source_job_id,title,company,description,remote,tags,qualifications,retrieved_at,created_at,updated_at)
            VALUES ('test','saved','SRE','Example','<p>Python &amp; Linux</p><script>secret</script>',false,'["Linux"]','["Linux"]',now(),now(),now())""")
        )
        command.upgrade(config, "head")
        row = connection.execute(
            text(
                "SELECT content, metadata, qualifications, qualification_version, fts @@ plainto_tsquery('simple','Linux') AS searchable FROM job_postings"
            )
        ).one()
        assert row.content == "SRE Python & Linux"
        assert row.metadata["tags"] == ["Linux"]
        assert row.qualifications == ["Linux"] and row.qualification_version is None
        assert row.searchable
        indexes = dict(
            connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='job_postings'"
                )
            ).all()
        )
        assert "vector_ip_ops" in indexes["ix_jobs_embedding_ip"]
        assert "USING hnsw" in indexes["ix_jobs_embedding_ip"]
        assert "USING gin" in indexes["ix_jobs_metadata"]
        assert "USING gin" in indexes["ix_jobs_fts"]


def test_title_similarity_migration_enables_trigram_matching(session):
    session.rollback()
    config = Config("alembic.ini")
    with session.get_bind().begin() as connection:
        config.attributes["connection"] = connection
        assert (
            connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname='pg_trgm'")
            )
            == "pg_trgm"
        )
        indexes = dict(
            connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='job_postings'"
                )
            ).all()
        )
        assert "gin_trgm_ops" in indexes["ix_jobs_title_trgm"]
