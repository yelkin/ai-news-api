"""As a job seeker, I rank title-filtered jobs using shared canonical skills."""

from app.main import app
from app.qualifications import QUALIFICATION_VERSION, get_qualification_provider
from app.schemas.models import JobPosting
from app.schemas.skill_fit import JobQualification, Qualification


def test_title_filter_precedes_qualification_ranking(client, session):
    skills = [
        Qualification(canonical_name=name, normalized_name=name.lower())
        for name in ["Python", "Linux", "Kubernetes", "Java"]
    ]
    session.add_all(skills)
    session.commit()
    ids = [s.id for s in skills]
    for source, title, requirements in [
        ("best", "SRE", ids[:3]),
        ("other", "SRE", ids[2:]),
        ("excluded", "Marketing", ids[:3]),
    ]:
        job = JobPosting(
            platform="test",
            source_job_id=source,
            company="Example",
            title=title,
            description=title,
            qualifications=[],
            qualification_version=QUALIFICATION_VERSION,
        )
        session.add(job)
        session.flush()
        for skill in requirements:
            session.add(
                JobQualification(
                    job_id=job.id, qualification_id=skill, evidence_label="evidence"
                )
            )
    session.commit()
    response = client.post(
        "/jobs/fit", json={"titles": ["SRE"], "qualification_ids": ids[:3]}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert [r["job"]["source_job_id"] for r in data["results"]] == ["best", "other"]
    assert data["results"][0]["coverage"] == 1
    assert data["results"][1]["coverage"] == 0.5
    assert data["counts"]["candidates"] == 2


def test_resume_and_job_synonyms_share_catalog(client, session):
    def provider(kind, payload):
        if kind == "extract":
            return {
                "qualifications": [
                    "k8s" if payload["document_kind"] == "resume" else "Kubernetes"
                ]
            }
        candidates = payload["candidates"]
        return {
            "choices": [
                {
                    "label": payload["labels"][0],
                    "qualification_id": candidates[0]["id"] if candidates else None,
                    "canonical_name": "Kubernetes",
                }
            ]
        }

    app.dependency_overrides[get_qualification_provider] = lambda: provider
    first = client.post(
        "/resume/qualifications", json={"text": "I operate k8s clusters."}
    )
    second = client.post(
        "/resume/qualifications", json={"text": "I operate Kubernetes."}
    )
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    assert first.json()["qualifications"][0]["canonical_name"] == "Kubernetes"
    from sqlmodel import select

    job_id = add_job(session)
    assert client.post(f"/jobs/{job_id}/enrich").status_code == 200
    link = session.exec(
        select(JobQualification).where(JobQualification.job_id == job_id)
    ).one()
    assert link.qualification_id == first.json()["qualifications"][0]["id"]
    assert client.post("/resume/qualifications", json={"text": " "}).status_code == 422
    assert (
        client.post("/resume/qualifications", json={"text": "a" * 65537}).status_code
        == 422
    )


def simple_provider(kind, payload):
    if kind == "extract":
        return {"qualifications": ["Python", "Kubernetes"]}
    options = {q["canonical_name"].lower(): q["id"] for q in payload["candidates"]}
    return {
        "choices": [
            {
                "label": label,
                "qualification_id": options.get(label.lower()),
                "canonical_name": label,
            }
            for label in payload["labels"]
        ]
    }


def install_providers(embed=None, extract=simple_provider):
    from app.embeddings import get_embedding_provider

    app.dependency_overrides[get_qualification_provider] = lambda: extract
    app.dependency_overrides[get_embedding_provider] = lambda: (
        embed or (lambda texts: [[2.0] + [0.0] * 1535 for _ in texts])
    )


def add_job(session, source="one", title="SRE"):
    job = JobPosting(
        platform="test",
        source_job_id=source,
        title=title,
        company="Example",
        description="Python and Kubernetes required",
    )
    session.add(job)
    session.commit()
    return job.id


def test_prepare_batches_are_title_filtered_and_resumable(client, session):
    from sqlmodel import select

    install_providers()
    ids = [add_job(session, str(i)) for i in range(7)]
    excluded = add_job(session, "unrelated", "Marketing")
    first = client.post("/jobs/prepare", json={"titles": ["SRE"]})
    assert first.status_code == 200, first.text
    assert first.json()["processed"] == 5
    assert not first.json()["complete"]
    cursor = first.json()["next_cursor"]
    # New arrivals do not extend an in-progress run.
    arrival = add_job(session, "arrival")
    second = client.post(
        "/jobs/prepare", json={"titles": ["SRE"], "cursor": cursor}
    ).json()
    assert second["processed"] == 2 and second["complete"]
    session.expire_all()
    assert session.get(JobPosting, excluded).qualification_version is None
    assert session.get(JobPosting, arrival).qualification_version is None
    assert session.get(JobPosting, ids[0]).embedding[0] == 1.0
    assert (
        client.post("/jobs/prepare", json={"titles": ["SRE"]}).json()["processed"] == 1
    )
    assert (
        client.post("/jobs/prepare", json={"titles": ["SRE"]}).json()["processed"] == 0
    )
    assert len(session.exec(select(Qualification)).all()) == 2
    assert (
        client.post(
            "/jobs/prepare", json={"titles": ["Other"], "cursor": cursor}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/jobs/prepare", json={"titles": ["SRE"], "cursor": "bad"}
        ).status_code
        == 422
    )


def test_partial_embedding_failure_preserves_rankable_qualifications(client, session):

    def fail(texts):
        raise RuntimeError("unavailable")

    install_providers(embed=fail)
    job_id = add_job(session)
    result = client.post("/jobs/prepare", json={"titles": ["SRE"]}).json()
    assert result["failed"] == 1 and result["complete"]
    skill = client.get("/qualifications?q=Python").json()[0]["id"]
    response = client.post(
        "/jobs/fit", json={"titles": ["SRE"], "qualification_ids": [skill]}
    ).json()
    assert response["results"][0]["job"]["id"] == job_id
    assert response["results"][0]["coverage"] == 0.5
    install_providers(
        extract=lambda *args: (_ for _ in ()).throw(
            AssertionError("cached extraction must not repeat")
        )
    )
    assert (
        client.post("/jobs/prepare", json={"titles": ["SRE"]}).json()["prepared"] == 1
    )


def test_extraction_rejects_results_for_concurrently_changed_source(client, session):
    from sqlmodel import Session, select

    job_id = add_job(session)

    def provider(kind, payload):
        if kind == "extract":
            with Session(session.get_bind()) as concurrent:
                job = concurrent.get(JobPosting, job_id)
                job.description = "Go now required"
                concurrent.add(job)
                concurrent.commit()
        return simple_provider(kind, payload)

    install_providers(extract=provider)
    response = client.post(f"/jobs/{job_id}/enrich")
    assert response.status_code == 409
    session.expire_all()
    assert session.get(JobPosting, job_id).qualifications is None
    assert not session.exec(select(JobQualification)).all()


def test_ingestion_invalidates_links_and_synchronizes_metadata(
    client, session, monkeypatch
):
    from sqlalchemy import text
    from sqlmodel import select

    from app import pipeline

    install_providers()
    job_id = add_job(session)
    assert client.post(f"/jobs/{job_id}/enrich").status_code == 200
    changed = JobPosting(
        platform="test",
        source_job_id="one",
        title="SRE",
        company="New company",
        description="<p>Go &amp; Rust</p><script>hidden</script>",
    )
    monkeypatch.setattr(pipeline, "scrape", lambda **kwargs: [changed])
    assert pipeline.ingest_jobs(session).updated == 1
    session.expire_all()
    job = session.get(JobPosting, job_id)
    assert job.qualification_version is None
    assert job.content == "SRE Go & Rust"
    assert job.search_metadata["company"] == "New company"
    assert not session.exec(select(JobQualification)).all()
    assert session.execute(
        text(
            "SELECT fts @@ plainto_tsquery('simple','Rust') FROM job_postings WHERE id=:id"
        ),
        {"id": job_id},
    ).scalar()


def test_catalog_merge_preserves_old_ids_and_deduplicates_job_links(client, session):
    from sqlmodel import select

    from app.qualifications import canonical_id, merge_qualifications

    install_providers()
    job_id = add_job(session)
    client.post(f"/jobs/{job_id}/enrich")
    first, second = session.exec(select(Qualification).order_by(Qualification.id)).all()
    old, target = first.id, second.id
    merge_qualifications(session, old, target)
    session.expire_all()
    assert canonical_id(session, old) == target
    assert len(session.exec(select(JobQualification)).all()) == 1
    response = client.post(
        "/jobs/fit", json={"titles": ["SRE"], "qualification_ids": [old, target]}
    ).json()
    assert response["results"][0]["coverage"] == 1
    assert len(client.get("/qualifications").json()) == 1
    import pytest

    with pytest.raises(ValueError):
        merge_qualifications(session, target, old)
    session.rollback()


def test_invented_ids_and_malformed_extraction_are_rejected(client, session):
    from sqlmodel import select

    install_providers(
        extract=lambda kind, payload: (
            {"qualifications": ["Python"]}
            if kind == "extract"
            else {
                "choices": [
                    {
                        "label": "Python",
                        "qualification_id": 999,
                        "canonical_name": "Python",
                    }
                ]
            }
        )
    )
    assert (
        client.post("/resume/qualifications", json={"text": "Python"}).status_code
        == 502
    )
    assert not session.exec(select(Qualification)).all()
    assert (
        client.post(
            "/jobs/fit", json={"titles": ["SRE"], "qualification_ids": [999]}
        ).status_code
        == 422
    )
    install_providers(extract=lambda *args: {"qualifications": [" "]})
    assert (
        client.post("/resume/qualifications", json={"text": "Python"}).status_code
        == 502
    )


def test_empty_pending_failed_and_no_overlap_are_distinct(client, session):

    skill = Qualification(canonical_name="Java", normalized_name="java")
    session.add(skill)
    session.commit()
    request = {"titles": ["SRE"], "qualification_ids": [skill.id]}
    assert client.post("/jobs/fit", json=request).json()["state"] == "no_candidates"
    job_id = add_job(session)
    pending = client.post("/jobs/fit", json=request).json()
    assert (
        pending["state"] == "preparation_needed" and pending["counts"]["pending"] == 1
    )
    install_providers(
        extract=lambda *args: (_ for _ in ()).throw(
            RuntimeError("private resume contents")
        )
    )
    assert client.post(f"/jobs/{job_id}/enrich").status_code == 502
    failed = client.post("/jobs/fit", json=request).json()
    assert failed["counts"]["failed"] == 1
    install_providers(extract=lambda *args: {"qualifications": []})
    assert client.post(f"/jobs/{job_id}/enrich").status_code == 200
    empty = client.post("/jobs/fit", json=request).json()
    assert empty["counts"]["empty"] == 1 and not empty["results"]
    assert client.post(
        "/resume/qualifications", json={"text": "No skills here"}
    ).json() == {"qualifications": []}
    install_providers()
    assert client.post(f"/jobs/{job_id}/enrich?force=true").status_code == 200
    assert client.post("/jobs/fit", json=request).json()["state"] == "no_overlap"


def test_autocomplete_literal_wildcards_and_case_insensitive_distinct(client, session):
    add_job(session, "one", "SRE")
    add_job(session, "two", "sre")
    add_job(session, "three", "100% SRE")
    assert len(client.get("/jobs/titles?q=sre").json()) == 2
    assert client.get("/jobs/titles?q=%25").json() == ["100% SRE"]
    assert client.get("/jobs/titles?limit=0").status_code == 422
    assert client.get("/jobs/titles?q=" + "a" * 201).status_code == 422


def test_title_matching_accepts_extensions_and_small_typos(client, session):
    for source, title in [
        ("senior", "Senior Site Reliability Engineer"),
        ("suffix", "Site Reliability Engineer (m/w/d)"),
        ("unrelated", "Product Marketing Manager"),
    ]:
        add_job(session, source, title)
    response = client.get("/jobs/titles?q=Site Reliablity Engineer")
    assert response.status_code == 200
    assert response.json() == [
        "Senior Site Reliability Engineer",
        "Site Reliability Engineer (m/w/d)",
    ]
    # The same predicate drives preparation and fit, not just autocomplete.
    install_providers()
    prepared = client.post(
        "/jobs/prepare", json={"titles": ["Site Reliablity Engineer"]}
    ).json()
    assert prepared["processed"] == 2


def test_normalized_vectors_and_semantic_tie_break(client, session):
    from sqlmodel import select

    from app.embeddings import normalize_vectors

    install_providers()
    first, second = add_job(session, "first"), add_job(session, "second")
    client.post("/jobs/prepare", json={"titles": ["SRE"]})
    a, b = session.get(JobPosting, first), session.get(JobPosting, second)
    a.embedding, b.embedding = [0.0, 1.0] + [0.0] * 1534, [1.0] + [0.0] * 1535
    session.add_all([a, b])
    session.commit()
    skill = (
        session.exec(
            select(Qualification).where(Qualification.canonical_name == "Python")
        )
        .one()
        .id
    )
    request = {"titles": ["SRE"], "qualification_ids": [skill], "limit": 1}
    assert (
        client.post("/jobs/fit", json=request).json()["results"][0]["job"]["id"]
        == second
    )
    install_providers(
        embed=lambda *args: (_ for _ in ()).throw(RuntimeError("offline"))
    )
    fallback = client.post("/jobs/fit", json=request).json()
    assert not fallback["semantic_tiebreak_available"]
    assert fallback["results"][0]["job"]["id"] == first
    assert normalize_vectors([[3.0, 4.0] + [0.0] * 1534])[0][:2] == [0.6, 0.8]


def test_concurrent_catalog_creation_reuses_one_id(session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlmodel import Session, select

    from app.qualifications import resolve_labels

    barrier = Barrier(2)

    def create():
        def provider(kind, payload):
            barrier.wait(timeout=10)
            return simple_provider(kind, payload)

        with Session(session.get_bind()) as separate:
            return resolve_labels(separate, ["Python"], provider)[0][0].id

    session.rollback()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: create(), range(2)))
    assert ids[0] == ids[1]
    assert len(session.exec(select(Qualification)).all()) == 1
