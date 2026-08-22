import requests

from app.schemas.models import JobPosting


URL = "https://www.arbeitnow.com/api/job-board-api"
SEARCH_TERM = "Site Reliability Engineer"


def scrape() -> JobPosting:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    for job in response.json().get("data", []):
        if SEARCH_TERM.casefold() in job.get("title", "").casefold():
            return JobPosting(
                platform="Arbeitnow",
                company=job.get("company_name", ""),
                title=job.get("title", ""),
                description=job.get("description", ""),
                tags=job.get("tags", []),
            )

    raise LookupError(f"No Arbeitnow job found for {SEARCH_TERM!r}")
