"""Title-filtered, canonical qualification preparation and exact fit ranking."""

import base64
import json
from fractions import Fraction
from itertools import groupby

from sqlalchemy import delete, func, literal, or_, update
from sqlalchemy.orm import load_only
from sqlmodel import select

from app.embedding_config import EMBEDDING_VERSION
from app.embeddings import normalize_vectors, posting_text, validate_vectors
from app.qualifications import (
    QUALIFICATION_VERSION,
    canonical_id,
    extract_labels,
    resolve_labels,
)
from app.schemas.models import JobPosting, JobPostingRead, utc_now
from app.schemas.skill_fit import (
    FitResponse,
    FitResult,
    JobQualification,
    PrepareResponse,
    Qualification,
)


def literal_pattern(value):
    return (
        "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


def title_filter(titles):
    return or_(*(title_match(t) for t in titles))


def title_match(title):
    """Match title extensions and minor spelling errors without broadening by tags."""
    value = title.strip()
    lowered = func.lower(JobPosting.title)
    query = literal(value.casefold())
    return or_(
        JobPosting.title.ilike(literal_pattern(value), escape="\\"),
        # word_similarity compares the query to the best continuous title span.
        query.op("<%", is_comparison=True)(lowered),
        query.op("%", is_comparison=True)(lowered),
    )


def source_snapshot(job):
    return {
        key: getattr(job, key)
        for key in (
            "title",
            "description",
            "company",
            "location",
            "remote",
            "tags",
            "source_url",
        )
    }


def source_predicate(job_id, snapshot):
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    clauses = [JobPosting.id == job_id]
    for key, value in snapshot.items():
        if key == "tags":
            clauses.append(cast(JobPosting.tags, JSONB) == value)
        else:
            clauses.append(getattr(JobPosting, key) == value)
    return clauses


def enrich_canonical_job(session, job_id, provider, force=False):
    job = session.get(JobPosting, job_id)
    if job is None:
        raise ValueError("Job not found")
    if not force and job.qualification_version == QUALIFICATION_VERSION:
        session.rollback()
        return True
    snapshot = source_snapshot(job)
    session.rollback()
    try:
        labels = extract_labels(
            posting_text(snapshot["title"], snapshot["description"]), "job", provider
        )
        resolved = resolve_labels(session, labels or [], provider)
        # The update takes the row lock before replacing links, serializing with ingestion.
        result = session.execute(
            update(JobPosting)
            .where(*source_predicate(job_id, snapshot))
            .values(
                qualifications=[q.canonical_name for q, _ in resolved],
                qualification_version=QUALIFICATION_VERSION,
                enriched_at=utc_now(),
                enrichment_error=None,
                updated_at=utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        if not result.rowcount:
            session.rollback()
            return False
        session.execute(
            delete(JobQualification).where(JobQualification.job_id == job_id)
        )
        for q, evidence in resolved:
            resolved_id = canonical_id(session, q.id)
            from sqlalchemy.dialects.postgresql import insert

            session.execute(
                insert(JobQualification)
                .values(
                    job_id=job_id, qualification_id=resolved_id, evidence_label=evidence
                )
                .on_conflict_do_nothing()
            )
        session.commit()
        return True
    except Exception:
        session.rollback()
        session.execute(
            update(JobPosting)
            .where(*source_predicate(job_id, snapshot))
            .values(
                enrichment_error="Qualification extraction failed; retry preparation."
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        raise


def encode_cursor(last, upper, titles):
    return base64.urlsafe_b64encode(
        json.dumps({"last": last, "upper": upper, "titles": titles}).encode()
    ).decode()


def decode_cursor(cursor, titles):
    try:
        data = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        last, upper = data["last"], data["upper"]
        if (
            type(last) is not int
            or type(upper) is not int
            or not 0 <= last <= upper <= 2**31 - 1
            or data["titles"] != titles
        ):
            raise ValueError()
        return last, upper
    except Exception as error:
        raise ValueError("Invalid preparation cursor for these titles") from error


def prepare_jobs(session, request, provider, embed):
    """As a user, I prepare matching stored jobs in resumable batches, even without scraping."""
    if request.cursor:
        last, upper = decode_cursor(request.cursor, request.titles)
    else:
        last, upper = 0, session.exec(select(func.max(JobPosting.id))).one() or 0
    pending = or_(
        JobPosting.qualification_version.is_(None),
        JobPosting.qualification_version != QUALIFICATION_VERSION,
        JobPosting.embedding.is_(None),
        JobPosting.embedding_version.is_(None),
        JobPosting.embedding_version != EMBEDDING_VERSION,
    )

    def selection(after):
        return (
            select(JobPosting.id)
            .where(
                title_filter(request.titles),
                JobPosting.id > after,
                JobPosting.id <= upper,
                pending,
            )
            .order_by(JobPosting.id)
        )

    ids = list(session.exec(selection(last).limit(5)).all())
    session.rollback()
    result = PrepareResponse()
    for job_id in ids:
        result.processed += 1
        last = job_id
        try:
            if not enrich_canonical_job(session, job_id, provider):
                result.skipped += 1
                continue
            job = session.get(JobPosting, job_id)
            if job.embedding is None or job.embedding_version != EMBEDDING_VERSION:
                title, description = job.title, job.description
                session.rollback()
                vectors = normalize_vectors(embed([posting_text(title, description)]))
                validate_vectors(vectors, 1)
                written = session.execute(
                    update(JobPosting)
                    .where(
                        JobPosting.id == job_id,
                        JobPosting.title == title,
                        JobPosting.description == description,
                    )
                    .values(embedding=vectors[0], embedding_version=EMBEDDING_VERSION)
                    .execution_options(synchronize_session=False)
                )
                session.commit()
                if not written.rowcount:
                    result.skipped += 1
                    continue
            else:
                session.rollback()
            result.prepared += 1
        except Exception:
            session.rollback()
            result.failed += 1
            result.errors.append(
                f"Preparation failed for job {job_id}; retry to finish."
            )
    result.complete = session.exec(selection(last).limit(1)).first() is None
    session.rollback()
    if not result.complete:
        result.next_cursor = encode_cursor(last, upper, request.titles)
    return result


def qualification_overlap(required, supplied):
    matched = set(required) & set(supplied)
    return Fraction(len(matched), len(required)) if required else Fraction(0), matched


def fit_jobs(session, request, embed):
    """As a user, I see the strongest qualification matches only within my requested titles."""
    supplied = {canonical_id(session, qid) for qid in request.qualification_ids}
    names = [session.get(Qualification, qid).canonical_name for qid in sorted(supplied)]
    response = FitResponse(state="no_candidates")
    ranked = []
    last = 0
    while True:
        rows = session.exec(
            select(
                JobPosting.id,
                JobPosting.qualification_version,
                JobPosting.enrichment_error,
            )
            .where(title_filter(request.titles), JobPosting.id > last)
            .order_by(JobPosting.id)
            .limit(500)
        ).all()
        if not rows:
            break
        last = rows[-1].id
        ids = [r.id for r in rows if r.qualification_version == QUALIFICATION_VERSION]
        requirements = {qid: {} for qid in ids}
        if ids:
            links = session.exec(
                select(
                    JobQualification.job_id,
                    Qualification.id,
                    Qualification.canonical_name,
                    Qualification.merged_into_id,
                )
                .join(
                    Qualification, Qualification.id == JobQualification.qualification_id
                )
                .where(JobQualification.job_id.in_(ids))
            ).all()
            for job_id, qid, label, merged_into in links:
                requirements[job_id][
                    canonical_id(session, qid) if merged_into else qid
                ] = label
        for row in rows:
            response.counts.candidates += 1
            if row.qualification_version != QUALIFICATION_VERSION:
                if row.enrichment_error:
                    response.counts.failed += 1
                else:
                    response.counts.pending += 1
                continue
            required = requirements[row.id]
            if not required:
                response.counts.empty += 1
                continue
            response.counts.prepared += 1
            score, matched = qualification_overlap(required, supplied)
            if score:
                ranked.append(
                    (
                        score,
                        row.id,
                        [required[q] for q in sorted(matched)],
                        [required[q] for q in sorted(set(required) - matched)],
                    )
                )
    if not ranked:
        session.rollback()
        if response.counts.candidates:
            response.state = (
                "preparation_needed"
                if not response.counts.prepared
                and (response.counts.pending or response.counts.failed)
                else "no_overlap"
            )
        return response
    ranked.sort(key=lambda r: (-r[0], r[1]))
    # Include entire boundary tie group before the final limit.
    cutoff = ranked[min(request.limit, len(ranked)) - 1][0]
    shortlist = [r for r in ranked if r[0] >= cutoff]
    # Materialize only the boundary shortlist's public fields, without vectors.
    public_jobs = {
        job.id: JobPostingRead.model_validate(job)
        for job in session.exec(
            select(JobPosting)
            .where(JobPosting.id.in_([r[1] for r in shortlist]))
            .options(
                load_only(
                    *(getattr(JobPosting, name) for name in JobPostingRead.model_fields)
                )
            )
        ).all()
    }
    session.rollback()
    tie_ids = [
        r[1]
        for _, group in groupby(shortlist, key=lambda r: r[0])
        if len(items := list(group)) > 1
        for r in items
    ]
    similarities = {}
    if tie_ids:
        embedded_ids = list(
            session.exec(
                select(JobPosting.id).where(
                    JobPosting.id.in_(tie_ids),
                    JobPosting.embedding.is_not(None),
                    JobPosting.embedding_version == EMBEDDING_VERSION,
                )
            ).all()
        )
        session.rollback()
    else:
        embedded_ids = []
    if embedded_ids:
        try:
            vector = normalize_vectors(embed([", ".join(names)]))
            validate_vectors(vector, 1)
            similarities = dict(
                session.exec(
                    select(
                        JobPosting.id,
                        -JobPosting.embedding.max_inner_product(vector[0]),
                    ).where(
                        JobPosting.id.in_(embedded_ids),
                        JobPosting.embedding.is_not(None),
                        JobPosting.embedding_version == EMBEDDING_VERSION,
                    )
                ).all()
            )
        except Exception:
            response.semantic_tiebreak_available = False
        finally:
            session.rollback()
    shortlist.sort(key=lambda r: (-r[0], -similarities.get(r[1], -2), r[1]))
    for score, job_id, matched, unmatched in shortlist[: request.limit]:
        job = public_jobs[job_id]
        if job is not None:
            response.results.append(
                FitResult(
                    job=job, coverage=float(score), matched=matched, unmatched=unmatched
                )
            )
    response.state = "matched"
    session.rollback()
    return response
