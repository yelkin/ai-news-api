from sqlmodel import Session, select

from app.schemas.models import JobPosting, ScrapeSummary, utc_now
from app.scrapers.arbeitnow import scrape


SOURCE_FIELDS = {
    "source_url",
    "company",
    "title",
    "description",
    "location",
    "remote",
    "tags",
}


def ingest_jobs(
    session: Session,
    *,
    max_pages: int | None = None,
) -> ScrapeSummary:
    postings = scrape(max_pages=max_pages)
    inserted = 0
    updated = 0
    unchanged = 0
    errors: list[str] = []

    for posting in postings:
        try:
            existing = session.exec(
                select(JobPosting).where(
                    JobPosting.platform == posting.platform,
                    JobPosting.source_job_id == posting.source_job_id,
                )
            ).one_or_none()

            if existing is None:
                session.add(posting)
                action = "inserted"
            else:
                changed = any(
                    getattr(existing, field) != getattr(posting, field)
                    for field in SOURCE_FIELDS
                )
                values = posting.model_dump(include=SOURCE_FIELDS | {"retrieved_at"})
                existing.sqlmodel_update(values)
                if changed:
                    existing.qualifications = None
                    existing.enriched_at = None
                    existing.enrichment_error = None
                    existing.updated_at = utc_now()
                    action = "updated"
                else:
                    action = "unchanged"
                session.add(existing)

            session.commit()
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                unchanged += 1
        except Exception as error:
            session.rollback()
            errors.append(f"{posting.source_job_id}: {error}")

    return ScrapeSummary(
        matched=len(postings),
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        failed=len(errors),
        errors=errors,
    )
