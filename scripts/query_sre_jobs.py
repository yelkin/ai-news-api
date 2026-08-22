#!/usr/bin/env python3
"""Query public job APIs for Site Reliability Engineer positions."""

from __future__ import annotations

import json
from typing import Any

import requests

from app.scrapers.arbeitnow import scrape as scrape_arbeitnow


SEARCH_TERM = "Site Reliability Engineer"
HN_API_URL = "https://hacker-news.firebaseio.com/v0"
GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards"
GREENHOUSE_BOARD_TOKENS: list[str] = []


def get_json(url: str) -> tuple[int, Any]:
    try:
        response = requests.get(
            url,
            headers={"Accept": "application/json", "User-Agent": "ai-news-api/0.1"},
            timeout=30,
        )
    except requests.RequestException as error:
        return 0, {"error": str(error)}

    try:
        body = response.json()
    except requests.JSONDecodeError:
        body = {"error": response.text}

    return response.status_code, body


def print_response(source: str, url: str, status: int, body: Any) -> None:
    print(f"\n=== {source} ===")
    print(f"GET {url}")
    print(f"HTTP status: {status}")
    print(json.dumps(body, indent=2, ensure_ascii=False))


def query_hacker_news() -> None:
    index_url = f"{HN_API_URL}/jobstories.json"
    status, body = get_json(index_url)
    print_response("Hacker News Jobs index", index_url, status, body)
    if status != 200 or not isinstance(body, list):
        return

    for item_id in body:
        item_url = f"{HN_API_URL}/item/{item_id}.json"
        item_status, item = get_json(item_url)
        searchable = ""
        if isinstance(item, dict):
            searchable = f"{item.get('title', '')} {item.get('text', '')}"
        if SEARCH_TERM.casefold() in searchable.casefold():
            print_response("Hacker News Jobs match", item_url, item_status, item)


def query_greenhouse() -> None:
    if not GREENHOUSE_BOARD_TOKENS:
        print("\n=== Greenhouse ===")
        print("Skipped: add employer board tokens to GREENHOUSE_BOARD_TOKENS.")
        return

    for token in GREENHOUSE_BOARD_TOKENS:
        token = requests.utils.quote(token, safe="")
        url = f"{GREENHOUSE_API_URL}/{token}/jobs?content=true"
        status, body = get_json(url)
        if status == 200 and isinstance(body, dict):
            jobs = body.get("jobs", [])
            body = {
                **body,
                "jobs": [
                    job
                    for job in jobs
                    if SEARCH_TERM.casefold() in str(job.get("title", "")).casefold()
                ],
            }
        print_response(f"Greenhouse ({token})", url, status, body)


# %%
print(scrape_arbeitnow().model_dump_json(indent=2))
query_hacker_news()
query_greenhouse()

