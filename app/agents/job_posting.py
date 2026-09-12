"""Standalone qualification phrase extraction; persisted jobs use the shared catalog."""

from app.embeddings import posting_text
from app.qualifications import extract_labels, get_qualification_provider
from app.schemas.models import JobPosting


def enrich_job_posting(job_posting: JobPosting) -> JobPosting:
    enriched = JobPosting.model_validate(job_posting.model_dump())
    enriched.qualifications = extract_labels(
        posting_text(job_posting.title, job_posting.description),
        "job",
        get_qualification_provider(),
    )
    return enriched
