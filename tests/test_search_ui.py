from html.parser import HTMLParser

from fastapi.testclient import TestClient

from app.main import app


class PageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_search_page_and_assets_are_available():
    """As a job seeker, I can open the search page without a database connection."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        page = PageElements()
        page.feed(response.text)
        assert any(tag == "form" for tag, attrs in page.elements)
        assert any(
            tag == "input" and attrs.get("name") == "query"
            for tag, attrs in page.elements
        )
        assets = [
            attrs["href"]
            for tag, attrs in page.elements
            if tag == "link" and attrs.get("rel") == "stylesheet"
        ]
        assets += [
            attrs["src"]
            for tag, attrs in page.elements
            if tag == "script" and "src" in attrs
        ]
        assert len(assets) >= 2
        for asset in assets:
            assert client.get(asset).status_code == 200
        assert client.get("/docs").status_code == 200
        assert "/jobs/search" in client.get("/openapi.json").json()["paths"]


def test_search_assets_have_correct_types_and_safe_file_boundaries():
    with TestClient(app) as client:
        for name, content_type in [
            ("styles.css", "text/css"),
            ("search.js", "javascript"),
            ("result-data.js", "javascript"),
        ]:
            response = client.get(f"/static/{name}")
            assert response.status_code == 200
            assert content_type in response.headers["content-type"]
        assert client.get("/static/nonexistent.js").status_code == 404
        assert client.get("/static/%2e%2e/main.py").status_code == 404
