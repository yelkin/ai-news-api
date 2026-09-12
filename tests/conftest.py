import os

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

load_dotenv()

from app.database import get_session
from app.main import app


@pytest.fixture
def session():
    test_url = make_url(os.environ["TEST_DATABASE_URL"])
    development_url = make_url(os.environ["DATABASE_URL"])
    if (
        not test_url.database
        or not test_url.database.endswith("_test")
        or test_url == development_url
    ):
        raise RuntimeError(
            "Tests require a separate database with a name ending in _test"
        )
    engine = create_engine(test_url, pool_pre_ping=True)
    config = Config("alembic.ini")
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS job_qualifications"))
            connection.execute(text("DROP TABLE IF EXISTS qualifications"))
            connection.execute(text("DROP TABLE IF EXISTS job_postings"))
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(engine) as session:
            yield session
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS job_qualifications"))
            connection.execute(text("DROP TABLE IF EXISTS qualifications"))
            connection.execute(text("DROP TABLE IF EXISTS job_postings"))
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()


@pytest.fixture
def client(session):
    def get_test_session():
        yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
