"""Public workflow contracts and shared qualification catalog."""

from typing import Annotated

from pydantic import Field as ValidationField
from pydantic import StringConstraints, field_validator
from sqlmodel import Field, SQLModel

from app.embeddings import tokenize
from app.schemas.models import JobPostingRead

Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class Qualification(SQLModel, table=True):
    __tablename__ = "qualifications"
    id: int | None = Field(default=None, primary_key=True)
    canonical_name: str
    normalized_name: str = Field(unique=True)
    merged_into_id: int | None = Field(default=None, foreign_key="qualifications.id")


class JobQualification(SQLModel, table=True):
    __tablename__ = "job_qualifications"
    job_id: int = Field(
        primary_key=True, foreign_key="job_postings.id", ondelete="CASCADE"
    )
    qualification_id: int = Field(primary_key=True, foreign_key="qualifications.id")
    evidence_label: str


class QualificationRead(SQLModel):
    id: int
    canonical_name: str


class QualificationResponse(SQLModel):
    qualifications: list[QualificationRead]


class ResumeRequest(SQLModel):
    text: str = Field(min_length=1, max_length=65536)

    @field_validator("text")
    @classmethod
    def bounded_text(cls, value):
        if not value.strip():
            raise ValueError("Resume must not be blank")
        if len(value.encode("utf-8")) > 65536 or len(tokenize(value)) > 12000:
            raise ValueError("Resume exceeds 64 KiB or 12000 tokens")
        return value


class ResolveRequest(SQLModel):
    labels: list[Label] = Field(min_length=1, max_length=100)


class TitleRequest(SQLModel):
    titles: list[Label] = Field(min_length=1, max_length=10)

    @field_validator("titles")
    @classmethod
    def distinct_titles(cls, values):
        return sorted(set(v.casefold() for v in values))


class PrepareRequest(TitleRequest):
    cursor: str | None = Field(default=None, max_length=2000)


class PrepareResponse(SQLModel):
    processed: int = 0
    prepared: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    next_cursor: str | None = None
    complete: bool = True


class FitRequest(TitleRequest):
    qualification_ids: list[Annotated[int, ValidationField(strict=True, gt=0)]] = Field(
        min_length=1, max_length=100
    )
    limit: int = Field(default=10, ge=1, le=20)


class FitCounts(SQLModel):
    candidates: int = 0
    prepared: int = 0
    pending: int = 0
    failed: int = 0
    empty: int = 0


class FitResult(SQLModel):
    job: JobPostingRead
    coverage: float
    matched: list[str]
    unmatched: list[str]


class FitResponse(SQLModel):
    results: list[FitResult] = Field(default_factory=list)
    counts: FitCounts = Field(default_factory=FitCounts)
    state: str
    semantic_tiebreak_available: bool = True
