"""HTTP boundary for the resume-to-jobs workflow."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.embeddings import get_embedding_provider
from app.qualifications import (
    extract_labels,
    get_qualification_provider,
    resolve_labels,
)
from app.schemas.models import JobPosting
from app.schemas.skill_fit import (
    FitRequest,
    FitResponse,
    PrepareRequest,
    PrepareResponse,
    Qualification,
    QualificationRead,
    QualificationResponse,
    ResolveRequest,
    ResumeRequest,
)
from app.skill_fit import fit_jobs, literal_pattern, prepare_jobs, title_match

router = APIRouter()


@router.get("/jobs/titles", response_model=list[str])
def titles(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=10, ge=1, le=20),
    session: Session = Depends(get_session),
):
    # Case-insensitive distinct suggestions, retaining a representative display spelling.
    title = func.min(JobPosting.title)
    return list(
        session.exec(
            select(title)
            .where(title_match(q.strip()))
            .group_by(func.lower(JobPosting.title))
            .order_by(func.lower(title), title)
            .limit(limit)
        ).all()
    )


@router.get("/qualifications", response_model=list[QualificationRead])
def qualifications(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=10, ge=1, le=20),
    session: Session = Depends(get_session),
):
    return list(
        session.exec(
            select(Qualification)
            .where(
                Qualification.merged_into_id.is_(None),
                Qualification.canonical_name.ilike(
                    literal_pattern(q.strip()), escape="\\"
                ),
            )
            .order_by(Qualification.normalized_name, Qualification.id)
            .limit(limit)
        ).all()
    )


@router.post("/resume/qualifications", response_model=QualificationResponse)
def resume(
    request: ResumeRequest,
    session: Session = Depends(get_session),
    provider=Depends(get_qualification_provider),
):
    """As a user, I extract and review resume skills without saving my resume."""
    try:
        labels = extract_labels(request.text, "resume", provider)
        return QualificationResponse(
            qualifications=[q for q, _ in resolve_labels(session, labels, provider)]
        )
    except Exception as error:
        session.rollback()
        raise HTTPException(
            502, "Resume qualification extraction failed. Please retry."
        ) from error


@router.post("/qualifications/resolve", response_model=QualificationResponse)
def resolve(
    request: ResolveRequest,
    session: Session = Depends(get_session),
    provider=Depends(get_qualification_provider),
):
    try:
        return QualificationResponse(
            qualifications=[
                q for q, _ in resolve_labels(session, request.labels, provider)
            ]
        )
    except Exception as error:
        session.rollback()
        raise HTTPException(
            502, "Qualification resolution failed. Please retry."
        ) from error


@router.post("/jobs/prepare", response_model=PrepareResponse)
def prepare(
    request: PrepareRequest,
    session: Session = Depends(get_session),
    provider=Depends(get_qualification_provider),
    embed=Depends(get_embedding_provider),
):
    try:
        return prepare_jobs(session, request, provider, embed)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/jobs/fit", response_model=FitResponse)
def fit(
    request: FitRequest,
    session: Session = Depends(get_session),
    embed=Depends(get_embedding_provider),
):
    try:
        return fit_jobs(session, request, embed)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
