from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, cast, or_, text
from sqlmodel import Session, select

load_dotenv()

from app.database import get_session  # noqa: E402
from app.embeddings import (  # noqa: E402
    EmbeddingProvider,
    embed_missing_jobs,
    get_embedding_provider,
)
from app.pipeline import ingest_jobs  # noqa: E402
from app.qualifications import get_qualification_provider  # noqa: E402
from app.schemas.models import (  # noqa: E402
    EmbeddingSummary,
    HealthResponse,
    JobPosting,
    JobPostingRead,
    ScrapeSummary,
    SearchRequest,
    SearchResponse,
)
from app.search import (
    AnswerProvider,
    SearchProviderError,
    get_answer_provider,
    search_jobs,
)  # noqa: E402
from app.skill_fit import enrich_canonical_job  # noqa: E402
from app.skill_fit_routes import router as skill_fit_router  # noqa: E402

app = FastAPI(title="AI News Jobs API", version="0.1.0")
STATIC_DIRECTORY = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
app.include_router(skill_fit_router)


@app.get("/", response_class=FileResponse, include_in_schema=False)
def search_page() -> FileResponse:
    """As a job seeker, I can open a simple page to find relevant job postings."""
    return FileResponse(STATIC_DIRECTORY / "index.html")


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


@app.get("/jobs", response_model=list[JobPostingRead])
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


@app.post("/jobs/embed", response_model=EmbeddingSummary)
def embed_jobs(
    max_jobs: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> EmbeddingSummary:
    """As a user, I can generate missing job embeddings in bulk, optionally limiting work."""
    return embed_missing_jobs(session, provider, max_jobs)


@app.post("/jobs/search", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    session: Session = Depends(get_session),
    embed: EmbeddingProvider = Depends(get_embedding_provider),
    answer: AnswerProvider = Depends(get_answer_provider),
) -> SearchResponse:
    """As a user, I can search jobs in natural language and read a grounded answer."""
    try:
        return search_jobs(session, request, embed, answer)
    except SearchProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/jobs/{job_id}", response_model=JobPostingRead)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobPosting:
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


@app.post("/jobs/{job_id}/enrich", response_model=JobPostingRead)
def enrich_job(
    job_id: int,
    force: bool = False,
    session: Session = Depends(get_session),
    provider=Depends(get_qualification_provider),
) -> JobPosting:
    """As a user, I extract canonical job qualifications lazily or force a refresh."""
    if session.get(JobPosting, job_id) is None:
        raise HTTPException(404, "Job posting not found")
    try:
        if not enrich_canonical_job(session, job_id, provider, force):
            raise HTTPException(409, "Job changed during extraction; retry.")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Job enrichment failed") from error
    session.expire_all()
    return session.get(JobPosting, job_id)
