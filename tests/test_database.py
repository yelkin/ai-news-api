from sqlalchemy import inspect, text
from sqlmodel import SQLModel

from app import database


def test_startup_upgrades_existing_enrichment_columns(session, monkeypatch):
    engine = session.get_bind()
    SQLModel.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE job_postings ("
                "id SERIAL PRIMARY KEY, qualifications JSON NOT NULL)"
            )
        )

    monkeypatch.setattr(database, "engine", engine)
    database.create_db_and_tables()

    columns = {
        column["name"]: column for column in inspect(engine).get_columns("job_postings")
    }
    assert columns["qualifications"]["nullable"] is True
    assert "enriched_at" in columns
    assert "enrichment_error" in columns
