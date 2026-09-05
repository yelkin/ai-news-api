import pytest

from app import embeddings, search
from app.main import app
from app.schemas.models import GroundedAnswer, JobPosting


def vector(index=0):
    result = [0.0] * 1536
    result[index] = 1.0
    return result


def add_job(
    session,
    source_id,
    *,
    direction=0,
    version=embeddings.EMBEDDING_VERSION,
    company="Example",
):
    job = JobPosting(
        platform="test",
        source_job_id=source_id,
        company=company,
        title="Python Engineer",
        description="Build distributed systems",
        tags=["Python"],
        embedding=vector(direction) if direction is not None else None,
        embedding_version=version,
        source_url="https://example.com/jobs/" + source_id,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_semantic_search_ranks_filtered_jobs_and_returns_grounded_answer(
    client, session
):
    """As a user, I can describe a job in my own words and get matching jobs with cited evidence."""
    add_job(session, "filtered-out", company="Other")
    far = add_job(session, "far", direction=1)
    near = add_job(session, "near")
    add_job(session, "not-embedded", direction=None)
    add_job(session, "old-model", version="old")
    captured = []
    app.dependency_overrides[embeddings.get_embedding_provider] = lambda: (
        lambda texts: [vector()]
    )

    def answer(query, sources):
        captured.append((query, sources))
        return GroundedAnswer(
            answer="This role builds distributed systems.", cited_job_ids=[near.id]
        )

    app.dependency_overrides[search.get_answer_provider] = lambda: answer
    response = client.post(
        "/jobs/search",
        json={
            "query": "work on reliable backend services",
            "company": "Example",
            "tag": "python",
            "title": "engineer",
            "limit": 2,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert [job["id"] for job in result["jobs"]] == [near.id, far.id]
    assert result["cited_job_ids"] == [near.id]
    assert captured[0][0] == "work on reliable backend services"
    assert captured[0][1][0]["id"] == near.id
    assert "distributed systems" in captured[0][1][0]["description"]
    assert "embedding" not in str(result) and "embedding" not in str(captured)
    limited = client.post(
        "/jobs/search", json={"query": "backend", "company": "Example", "limit": 1}
    )
    assert [job["id"] for job in limited.json()["jobs"]] == [near.id]


def test_empty_search_does_not_call_providers(client, session):
    add_job(session, "missing", direction=None)

    def fail(*args):
        raise AssertionError("Provider must not be called without candidates")

    app.dependency_overrides[embeddings.get_embedding_provider] = lambda: fail
    app.dependency_overrides[search.get_answer_provider] = lambda: fail
    response = client.post("/jobs/search", json={"query": "Python"})
    assert response.status_code == 200
    assert response.json() == {
        "jobs": [],
        "answer": search.NO_MATCHES,
        "cited_job_ids": [],
    }


@pytest.mark.parametrize("query", ["", "   ", "x" * 2001])
def test_search_rejects_invalid_queries(client, query):
    assert client.post("/jobs/search", json={"query": query}).status_code == 422


@pytest.mark.parametrize("stage", ["embedding", "answer", "citation"])
def test_search_reports_provider_or_grounding_failures(client, session, stage):
    add_job(session, "one")

    def embed(texts):
        if stage == "embedding":
            raise RuntimeError("unavailable")
        return [vector()]

    def answer(query, sources):
        if stage == "answer":
            raise RuntimeError("unavailable")
        return GroundedAnswer(answer="Unsupported citation", cited_job_ids=[999999])

    app.dependency_overrides[embeddings.get_embedding_provider] = lambda: embed
    app.dependency_overrides[search.get_answer_provider] = lambda: answer
    assert client.post("/jobs/search", json={"query": "Python"}).status_code == 502


def test_context_is_bounded_and_preserves_ids():
    import json

    jobs = [
        JobPosting(
            id=i,
            platform="test",
            source_job_id=str(i),
            company="company",
            title=" title" * 1000,
            description=" description" * 20000,
            source_url="https://example.com/" + "path/" * 1000,
        )
        for i in range(1, 21)
    ]
    sources = search.build_context(jobs)
    assert sources and sources[0]["id"] == 1
    assert len(embeddings.tokenize(json.dumps(sources))) <= search.MAX_CONTEXT_TOKENS
    assert all("embedding" not in source for source in sources)
