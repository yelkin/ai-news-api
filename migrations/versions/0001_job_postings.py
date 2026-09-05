"""Move the existing job database initialization into a migration."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            id SERIAL PRIMARY KEY,
            platform VARCHAR NOT NULL,
            source_job_id VARCHAR NOT NULL,
            source_url VARCHAR,
            company VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            location VARCHAR,
            remote BOOLEAN NOT NULL,
            tags JSON,
            qualifications JSON,
            retrieved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            enriched_at TIMESTAMP WITHOUT TIME ZONE,
            enrichment_error VARCHAR,
            CONSTRAINT uq_job_source UNIQUE (platform, source_job_id)
        )
    """)
    for field in ("platform", "company", "title"):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_job_postings_{field} ON job_postings ({field})"
        )
    op.execute("ALTER TABLE job_postings ALTER COLUMN qualifications DROP NOT NULL")
    op.execute(
        "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS enrichment_error VARCHAR"
    )


def downgrade():
    op.drop_table("job_postings")
