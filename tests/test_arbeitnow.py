from app.scrapers import arbeitnow


class FakeResponse:
    def __init__(self, payload, page):
        self.payload = payload
        self.url = f"https://www.arbeitnow.com/api/job-board-api?page={page}"

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_scrape_maps_matches_and_follows_pagination(monkeypatch, capsys):
    pages = [
        {
            "data": [
                {
                    "slug": "sre-one",
                    "url": "https://example.com/sre-one",
                    "company_name": "Example",
                    "title": "Site Reliability Engineer",
                    "description": "Keep services reliable.",
                    "location": "Berlin",
                    "remote": True,
                    "tags": ["Python"],
                },
                {"slug": "other", "title": "Designer", "tags": []},
            ],
            "links": {"next": "page-2"},
        },
        {
            "data": [
                {
                    "slug": "sre-two",
                    "company_name": "Second",
                    "title": "Site Reliability Engineer II",
                    "description": "Operate systems.",
                    "tags": ["SRE"],
                }
            ],
            "links": {"next": None},
        },
    ]

    def fake_get(*args, **kwargs):
        page = kwargs["params"]["page"]
        return FakeResponse(pages[page - 1], page)

    monkeypatch.setattr(arbeitnow.SESSION, "get", fake_get)

    jobs = arbeitnow.scrape()

    assert [job.source_job_id for job in jobs] == ["sre-one", "other", "sre-two"]
    assert jobs[0].remote is True
    assert jobs[0].source_url == "https://example.com/sre-one"
    assert "job-board-api?page=1" in capsys.readouterr().out


def test_scrape_honors_page_limit(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        page = kwargs["params"]["page"]
        calls.append(page)
        return FakeResponse(
            {"data": [{"slug": "other", "title": "Other"}], "links": {"next": "yes"}},
            page,
        )

    monkeypatch.setattr(arbeitnow.SESSION, "get", fake_get)

    assert [job.source_job_id for job in arbeitnow.scrape(max_pages=2)] == [
        "other",
        "other",
    ]
    assert calls == [1, 2]


def test_http_session_retries_rate_limits_with_backoff():
    retries = arbeitnow.SESSION.get_adapter(arbeitnow.URL).max_retries

    assert retries.total == 6
    assert retries.backoff_factor == 2
    assert 429 in retries.status_forcelist
    assert retries.respect_retry_after_header is True
