"""Store text-embedding-3-small vectors for semantic job search."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("job_postings", sa.Column("embedding", Vector(1536), nullable=True))
    op.add_column(
        "job_postings", sa.Column("embedding_version", sa.String(), nullable=True)
    )


def downgrade():
    op.drop_column("job_postings", "embedding_version")
    op.drop_column("job_postings", "embedding")
