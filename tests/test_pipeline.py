from sqlmodel import select

from app import pipeline
from app.schemas.models import JobPosting, utc_now


def posting(title="Site Reliability Engineer"):
    return JobPosting(
        platform="Arbeitnow",
        source_job_id="source-1",
        company="Example",
        title=title,
        description="Python and Kubernetes required.",
        tags=["Python"],
    )


def test_ingestion_inserts_updates_and_reports_unchanged(monkeypatch, session):
    current = posting()
    monkeypatch.setattr(pipeline, "scrape", lambda *args, **kwargs: [current])

    first = pipeline.ingest_jobs(session)
    second = pipeline.ingest_jobs(session)
    current = posting("Senior Site Reliability Engineer")
    third = pipeline.ingest_jobs(session)
    stored = session.exec(select(JobPosting)).all()

    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)
    assert (third.inserted, third.updated, third.unchanged) == (0, 1, 0)
    assert len(stored) == 1
    assert stored[0].title == "Senior Site Reliability Engineer"


def test_ingestion_preserves_or_invalidates_cached_enrichment(monkeypatch, session):
    stored = posting()
    stored.qualifications = ["Python"]
    stored.enriched_at = utc_now()
    session.add(stored)
    session.commit()

    unchanged = posting()
    monkeypatch.setattr(pipeline, "scrape", lambda *args, **kwargs: [unchanged])
    pipeline.ingest_jobs(session)
    session.refresh(stored)
    assert stored.qualifications == ["Python"]

    changed = posting()
    changed.description = "Go required."
    monkeypatch.setattr(pipeline, "scrape", lambda *args, **kwargs: [changed])
    pipeline.ingest_jobs(session)
    session.refresh(stored)
    assert stored.qualifications is None
    assert stored.enriched_at is None
