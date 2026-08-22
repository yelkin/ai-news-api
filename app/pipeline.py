from app.agents.job_posting import enrich_job_posting
from app.schemas.models import JobPosting
from app.scrapers.arbeitnow import scrape


def run_pipeline() -> JobPosting:
    job_posting = scrape()
    return enrich_job_posting(job_posting)
