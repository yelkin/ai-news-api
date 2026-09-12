"""Enable tolerant partial title matching."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_jobs_title_trgm ON job_postings USING gin (title gin_trgm_ops)"
    )


def downgrade():
    op.drop_index("ix_jobs_title_trgm", table_name="job_postings")
