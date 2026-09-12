"""Canonical qualifications and job retrieval infrastructure."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_postings", sa.Column("content", sa.Text()))
    op.add_column(
        "job_postings",
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("job_postings", sa.Column("qualification_version", sa.String()))
    # Frozen HTML cleanup for migration backfill; do not depend on runtime models.
    from html.parser import HTMLParser

    class Cleaner(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts, self.hidden = [], 0

        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style"}:
                self.hidden += 1
            self.parts.append(" ")

        def handle_endtag(self, tag):
            if tag in {"script", "style"}:
                self.hidden = max(0, self.hidden - 1)
            self.parts.append(" ")

        def handle_data(self, data):
            if not self.hidden:
                self.parts.append(data)

    bind = op.get_bind()
    last = 0
    while True:
        rows = bind.execute(
            sa.text(
                "SELECT id, title, description FROM job_postings WHERE id > :last ORDER BY id LIMIT 500"
            ),
            {"last": last},
        ).all()
        if not rows:
            break
        for row in rows:
            parser = Cleaner()
            parser.feed(row.title + " " + row.description)
            parser.close()
            bind.execute(
                sa.text(
                    "UPDATE job_postings SET content=:content, metadata=jsonb_build_object('platform',platform,'company',company,'location',location,'remote',remote,'tags',tags) WHERE id=:id"
                ),
                {"content": " ".join("".join(parser.parts).split()), "id": row.id},
            )
        last = rows[-1].id
    op.execute(
        "ALTER TABLE job_postings ADD COLUMN fts tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, coalesce(content, ''))) STORED"
    )
    op.execute("CREATE INDEX ix_jobs_fts ON job_postings USING gin (fts)")
    op.execute("CREATE INDEX ix_jobs_metadata ON job_postings USING gin (metadata)")
    op.execute(
        "CREATE INDEX ix_jobs_embedding_ip ON job_postings USING hnsw (embedding vector_ip_ops)"
    )
    op.create_table(
        "qualifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False, unique=True),
        sa.Column("merged_into_id", sa.Integer(), sa.ForeignKey("qualifications.id")),
    )
    op.create_table(
        "job_qualifications",
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("job_postings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "qualification_id",
            sa.Integer(),
            sa.ForeignKey("qualifications.id"),
            primary_key=True,
        ),
        sa.Column("evidence_label", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("job_qualifications")
    op.drop_table("qualifications")
    for index in ("ix_jobs_embedding_ip", "ix_jobs_metadata", "ix_jobs_fts"):
        op.drop_index(index, table_name="job_postings")
    for column in ("fts", "qualification_version", "metadata", "content"):
        op.drop_column("job_postings", column)
