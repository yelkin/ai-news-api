"""External integration coverage for the primary resume-to-job-fit journey."""

import json
import os
from pathlib import Path

import pytest

from app.schemas.models import JobPosting

FIXTURES = Path(__file__).parent / "fixtures"
RESUME = """Core competencies:
- Python
- Linux
- Kubernetes
"""


@pytest.mark.external_integration
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for the real OpenAI integration test",
)
def test_job_seeker_finds_best_resume_match_for_similar_titles(client, session):
    """As a job seeker, I rank similar-title jobs against my resume competencies."""
    # Test data replaces ingestion; HTTP, PostgreSQL, and OpenAI remain real.
    # OpenAI API reference: https://developers.openai.com/api/docs
    postings = json.loads((FIXTURES / "job_postings.json").read_text())
    session.add_all([JobPosting.model_validate(posting) for posting in postings])
    session.commit()

    titles = client.get("/jobs/titles", params={"q": "Site Reliability Engineer"})
    assert titles.status_code == 200, titles.text
    assert titles.json() == [
        "Senior Site Reliability Engineer",
        "Site Reliability Engineer",
    ]

    resume = client.post("/resume/qualifications", json={"text": RESUME})
    assert resume.status_code == 200, resume.text
    qualification_ids = [item["id"] for item in resume.json()["qualifications"]]
    assert qualification_ids

    requested_titles = ["Site Reliability Engineer"]
    preparation = client.post("/jobs/prepare", json={"titles": requested_titles})
    assert preparation.status_code == 200, preparation.text
    assert preparation.json()["complete"] is True
    assert preparation.json()["prepared"] == 2
    assert preparation.json()["failed"] == 0

    fit = client.post(
        "/jobs/fit",
        json={
            "titles": requested_titles,
            "qualification_ids": qualification_ids,
        },
    )
    assert fit.status_code == 200, fit.text
    results = fit.json()["results"]
    assert [result["job"]["source_job_id"] for result in results] == [
        "site-reliability-engineer",
        "senior-site-reliability-engineer",
    ]
    assert results[0]["coverage"] > results[1]["coverage"]
    assert fit.json()["counts"]["candidates"] == 2
