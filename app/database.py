import os
from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE job_postings ALTER COLUMN qualifications DROP NOT NULL")
        )
        connection.execute(
            text(
                "ALTER TABLE job_postings "
                "ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP WITHOUT TIME ZONE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE job_postings "
                "ADD COLUMN IF NOT EXISTS enrichment_error VARCHAR"
            )
        )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
