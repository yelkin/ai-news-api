from app.schemas.models import JobPosting


def add_jobs(session):
    session.add(
        JobPosting(
            platform="Arbeitnow",
            source_job_id="one",
            company="Example GmbH",
            title="Site Reliability Engineer",
            description="Operate distributed systems",
            tags=["Python", "SRE"],
        )
    )
    session.add(
        JobPosting(
            platform="Arbeitnow",
            source_job_id="two",
            company="Other",
            title="Platform Engineer",
            description="Description",
            tags=["Go"],
        )
    )
    session.commit()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_filters_and_gets_jobs(client, session):
    add_jobs(session)

    response = client.get("/jobs", params={"company": "example", "tag": "python"})
    assert response.status_code == 200
    assert [job["source_job_id"] for job in response.json()] == ["one"]

    job_id = response.json()[0]["id"]
    assert client.get(f"/jobs/{job_id}").status_code == 200
    assert client.get("/jobs/9999").status_code == 404

    response = client.get("/jobs", params={"search": "distributed", "limit": 1})
    assert [job["source_job_id"] for job in response.json()] == ["one"]


def test_scrape_endpoint_returns_summary(client, monkeypatch, capsys):
    from app import main

    monkeypatch.setattr(
        main,
        "ingest_jobs",
        lambda session, max_pages: {
            "matched": 1,
            "inserted": 1,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "errors": [],
        },
    )

    response = client.post("/jobs/scrape", params={"max_pages": 1})
    assert response.status_code == 200
    assert response.json()["inserted"] == 1
    assert "http://testserver/jobs/scrape?max_pages=1" in capsys.readouterr().out


def test_enrichment_is_lazy_cached_and_forceable(client, session, monkeypatch):
    from app import main

    add_jobs(session)
    job_id = client.get("/jobs").json()[0]["id"]
    calls = []

    def enrich(job):
        calls.append(job.id)
        job.qualifications = ["Kubernetes"]
        return job

    monkeypatch.setattr(main, "enrich_job_posting", enrich)

    first = client.post(f"/jobs/{job_id}/enrich")
    cached = client.post(f"/jobs/{job_id}/enrich")
    forced = client.post(f"/jobs/{job_id}/enrich", params={"force": True})

    assert first.status_code == 200
    assert first.json()["qualifications"] == ["Kubernetes"]
    assert cached.status_code == 200
    assert forced.status_code == 200
    assert calls == [job_id, job_id]


def test_enrichment_failure_is_persisted(client, session, monkeypatch):
    from app import main

    add_jobs(session)
    job_id = client.get("/jobs").json()[0]["id"]

    def fail(job):
        raise ValueError("model unavailable")

    monkeypatch.setattr(main, "enrich_job_posting", fail)
    response = client.post(f"/jobs/{job_id}/enrich")

    assert response.status_code == 502
    session.expire_all()
    assert session.get(JobPosting, job_id).enrichment_error == "model unavailable"
