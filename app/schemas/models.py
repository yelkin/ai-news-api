from datetime import datetime, timezone

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


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


class JobPosting(JobPostingFields, table=True):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("platform", "source_job_id", name="uq_job_source"),
    )

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    enriched_at: datetime | None = None
    enrichment_error: str | None = None


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
