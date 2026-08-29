from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy import String, cast, or_, text
from sqlmodel import Session, select

load_dotenv()

from app.database import create_db_and_tables, get_session  # noqa: E402
from app.agents.job_posting import enrich_job_posting  # noqa: E402
from app.pipeline import ingest_jobs  # noqa: E402
from app.schemas.models import (  # noqa: E402
    HealthResponse,
    JobPosting,
    ScrapeSummary,
    utc_now,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="AI News Jobs API", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    try:
        session.exec(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return HealthResponse(status="ok")


@app.post("/jobs/scrape", response_model=ScrapeSummary)
def scrape_jobs(
    request: Request,
    max_pages: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
) -> ScrapeSummary:
    print(f"Scrape request URL: {request.url}", flush=True)
    return ingest_jobs(session, max_pages=max_pages)


@app.get("/jobs", response_model=list[JobPosting])
def list_jobs(
    search: str | None = None,
    title: str | None = None,
    company: str | None = None,
    tag: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[JobPosting]:
    statement = select(JobPosting)
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                JobPosting.title.ilike(pattern),
                JobPosting.company.ilike(pattern),
                JobPosting.description.ilike(pattern),
                JobPosting.location.ilike(pattern),
                cast(JobPosting.tags, String).ilike(pattern),
            )
        )
    if title:
        statement = statement.where(JobPosting.title.ilike(f"%{title}%"))
    if company:
        statement = statement.where(JobPosting.company.ilike(f"%{company}%"))
    if tag:
        statement = statement.where(cast(JobPosting.tags, String).ilike(f'%"{tag}"%'))
    statement = statement.order_by(JobPosting.id).offset(offset).limit(limit)
    return list(session.exec(statement).all())


@app.get("/jobs/{job_id}", response_model=JobPosting)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobPosting:
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


@app.post("/jobs/{job_id}/enrich", response_model=JobPosting)
def enrich_job(
    job_id: int,
    force: bool = False,
    session: Session = Depends(get_session),
) -> JobPosting:
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    if job.qualifications is not None and not force:
        return job

    try:
        enriched = enrich_job_posting(job)
        job.qualifications = enriched.qualifications
        job.enriched_at = utc_now()
        job.enrichment_error = None
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)
    except Exception as error:
        session.rollback()
        job = session.get(JobPosting, job_id)
        job.enrichment_error = str(error)
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Job enrichment failed",
        ) from error
    return job
