from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from pydantic import field_validator
from sqlalchemy import JSON, Column, Computed, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlmodel import Field, SQLModel

from app.embedding_config import EMBEDDING_DIMENSIONS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobPostingFields(SQLModel):
    platform: str = Field(index=True)
    source_job_id: str
    source_url: str | None = None
    company: str = Field(index=True)
    title: str = Field(index=True)
    description: str
    location: str | None = None
    remote: bool = False
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    qualifications: list[str] | None = Field(default=None, sa_column=Column(JSON))
    retrieved_at: datetime = Field(default_factory=utc_now)


class JobPostingRead(JobPostingFields):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    enriched_at: datetime | None = None
    enrichment_error: str | None = None


class JobPosting(JobPostingRead, table=True):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("platform", "source_job_id", name="uq_job_source"),
        Index("ix_jobs_fts", "fts", postgresql_using="gin"),
        Index("ix_jobs_metadata", "metadata", postgresql_using="gin"),
        Index(
            "ix_jobs_embedding_ip",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_ip_ops"},
        ),
    )

    content: str | None = Field(default=None, sa_column=Column(Text), exclude=True)
    search_metadata: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"),
        exclude=True,
    )
    fts: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed(
                "to_tsvector('simple'::regconfig, coalesce(content, ''))",
                persisted=True,
            ),
        ),
        exclude=True,
    )
    qualification_version: str | None = Field(default=None, exclude=True)

    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(EMBEDDING_DIMENSIONS)), exclude=True
    )
    embedding_version: str | None = Field(default=None, exclude=True)


class EmbeddingSummary(SQLModel):
    selected: int = 0
    embedded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class JobPostingEnrichment(SQLModel):
    qualifications: list[str]


class ScrapeSummary(SQLModel):
    matched: int
    inserted: int
    updated: int
    unchanged: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class HealthResponse(SQLModel):
    status: str


class SearchRequest(SQLModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    tag: str | None = Field(default=None, max_length=200)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be blank")
        return value


class GroundedAnswer(SQLModel):
    answer: str
    cited_job_ids: list[int]


class SearchResponse(GroundedAnswer):
    jobs: list[JobPostingRead]
