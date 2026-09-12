"""Run schema migrations explicitly, independently of application startup."""

import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from app.schemas import models, skill_fit  # noqa: F401

load_dotenv()
config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=SQLModel.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=os.environ["DATABASE_URL"],
        target_metadata=SQLModel.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    engine = create_engine(os.environ["DATABASE_URL"], poolclass=pool.NullPool)
    with engine.connect() as connection:
        migrate(connection)
    engine.dispose()
