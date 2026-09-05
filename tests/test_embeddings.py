import pytest
from sqlmodel import Session, select

from app import embeddings
from app.main import app
from app.schemas.models import JobPosting


def vector(index=0):
    values = [0.0] * 1536
    values[index] = 1.0
    return values


def add_postings(session, count, *, description="Python required"):
    jobs = [
        JobPosting(
            platform="test",
            source_job_id=str(i),
            company="Example",
            title=f"Engineer {i}",
            description=description,
        )
        for i in range(count)
    ]
    session.add_all(jobs)
    session.commit()
    return [job.id for job in jobs]


def provider_override(provider):
    app.dependency_overrides[embeddings.get_embedding_provider] = lambda: provider


def test_bulk_embeds_missing_jobs_and_honors_limit(client, session):
    """As a user, I can embed missing jobs in bulk and limit the work per request."""
    ids = add_postings(session, 4)
    cached = session.get(JobPosting, ids[0])
    cached.embedding = vector(1)
    cached.embedding_version = embeddings.EMBEDDING_VERSION
    session.commit()
    calls = []

    def provider(texts):
        calls.append(texts)
        return [vector() for _ in texts]

    provider_override(provider)
    response = client.post("/jobs/embed?max_jobs=2")
    assert response.status_code == 200
    assert response.json() == {
        "selected": 2,
        "embedded": 2,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }
    assert len(calls) == 1 and len(calls[0]) == 2
    assert "Engineer 1" in calls[0][0] and "Python required" in calls[0][0]
    session.expire_all()
    assert list(session.get(JobPosting, ids[0]).embedding) == vector(1)
    assert session.get(JobPosting, ids[3]).embedding is None
    assert client.post("/jobs/embed").json()["embedded"] == 1
    assert client.post("/jobs/embed").json()["selected"] == 0
    assert len(calls) == 2
    for job in client.get("/jobs").json():
        assert "embedding" not in job and "embedding_version" not in job
    assert client.post("/jobs/embed?max_jobs=0").status_code == 422


def test_bulk_batches_failures_are_retryable(client, session):
    add_postings(session, 5, description=" word" * 7900)
    calls = []

    def provider(texts):
        calls.append(texts)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable")
        return [vector() for _ in texts]

    provider_override(provider)
    result = client.post("/jobs/embed").json()
    assert [len(batch) for batch in calls] == [2, 2, 1]
    assert (result["selected"], result["embedded"], result["failed"]) == (5, 3, 2)
    assert result["errors"]
    assert client.post("/jobs/embed").json()["embedded"] == 2


def test_bulk_rejects_stale_source(client, session):
    job_id = add_postings(session, 1)[0]

    def provider(texts):
        with Session(session.get_bind()) as concurrent:
            job = concurrent.get(JobPosting, job_id)
            job.description = "Changed during embedding"
            concurrent.add(job)
            concurrent.commit()
        return [vector()]

    provider_override(provider)
    result = client.post("/jobs/embed").json()
    assert result["skipped"] == 1 and result["embedded"] == 0
    session.expire_all()
    assert session.get(JobPosting, job_id).embedding is None


def test_input_normalization_and_limits():
    text = embeddings.posting_text(
        "Python Engineer", "<p>Build &amp; deploy</p><script>ignore me</script>"
    )
    assert "Title: Python Engineer" in text
    assert "Build & deploy" in text and "ignore me" not in text and "<p>" not in text
    huge = embeddings.posting_text("Python Engineer", " word" * 20000)
    assert len(embeddings.tokenize(huge)) <= embeddings.MAX_INPUT_TOKENS
    assert "Python Engineer" in huge
    assert embeddings.tokenize("<|endoftext|>")


@pytest.mark.parametrize("bad", [[1.0], [0.0] * 1536, [float("nan")] * 1536])
def test_invalid_vectors_are_not_stored(client, session, bad):
    add_postings(session, 1)
    provider_override(lambda texts: [bad])
    result = client.post("/jobs/embed").json()
    assert result["failed"] == 1
    assert session.exec(select(JobPosting)).one().embedding is None


def test_provider_output_is_mapped_by_index():
    from types import SimpleNamespace

    result = embeddings.ordered_vectors(
        [
            SimpleNamespace(index=1, embedding=vector(1)),
            SimpleNamespace(index=0, embedding=vector(0)),
        ],
        2,
    )
    assert result == [vector(0), vector(1)]
    with pytest.raises(ValueError, match="indexes"):
        embeddings.ordered_vectors([SimpleNamespace(index=1, embedding=vector())], 1)


def test_bulk_reads_multiple_pages_and_replaces_incompatible_vectors(client, session):
    ids = add_postings(session, 66)
    old = session.get(JobPosting, ids[0])
    old.embedding = vector(1)
    old.embedding_version = "old-version"
    session.commit()
    calls = []

    def provider(texts):
        calls.append(len(texts))
        return [vector() for _ in texts]

    provider_override(provider)
    result = client.post("/jobs/embed").json()
    assert result["embedded"] == 66
    assert calls == [64, 2]
    session.expire_all()
    assert (
        session.get(JobPosting, ids[0]).embedding_version
        == embeddings.EMBEDDING_VERSION
    )
