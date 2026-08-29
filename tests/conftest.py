import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

from app.database import get_session
from app.main import app


@pytest.fixture
def session():
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session):
    def get_test_session():
        yield session

    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    client.close()
    app.dependency_overrides.clear()
