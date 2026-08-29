from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.schemas.models import JobPosting


URL = "https://www.arbeitnow.com/api/job-board-api"

RETRY_POLICY = Retry(
    total=6,
    connect=6,
    read=6,
    status=6,
    backoff_factor=2,
    status_forcelist={429, 500, 502, 503, 504},
    allowed_methods={"GET"},
    respect_retry_after_header=True,
    raise_on_status=False,
)
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=RETRY_POLICY))
SESSION.mount("http://", HTTPAdapter(max_retries=RETRY_POLICY))


def _map_job(job: dict[str, Any]) -> JobPosting:
    source_url = job.get("url")
    source_job_id = str(job.get("slug") or job.get("id") or source_url or "")
    if not source_job_id:
        raise ValueError("Arbeitnow job has no stable identifier")

    return JobPosting(
        platform="Arbeitnow",
        source_job_id=source_job_id,
        source_url=source_url,
        company=job.get("company_name", ""),
        title=job.get("title", ""),
        description=job.get("description", ""),
        location=job.get("location"),
        remote=bool(job.get("remote", False)),
        tags=job.get("tags") or [],
    )


def scrape(
    max_pages: int | None = None,
) -> list[JobPosting]:
    postings: list[JobPosting] = []
    page = 1

    while max_pages is None or page <= max_pages:
        response = SESSION.get(
            URL,
            params={"page": page},
            headers={"Accept": "application/json", "User-Agent": "ai-news-api/0.1"},
            timeout=30,
        )
        response.raise_for_status()
        print(f"Arbeitnow request URL: {response.url}", flush=True)
        payload = response.json()
        jobs = payload.get("data", [])

        postings.extend(_map_job(job) for job in jobs)

        links = payload.get("links") or {}
        if not jobs or not links.get("next"):
            break
        page += 1

    return postings
