import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from app.services import category_sources as sources
from app.schemas.application import ApplicationCreate


@pytest.mark.parametrize("category", sorted(sources.CATEGORIES))
def test_category_listing_details_and_save(client, headers, monkeypatch, category):
    row = sources._record(
        category, "Real source fixture", "https://example.org/opportunity", "Provider"
    )
    ApplicationCreate(opportunity_id=row["id"])
    monkeypatch.setattr(sources, "listings", lambda value: [row] if value == category else [])
    h = headers()
    page = client.get("/api/v1/opportunities", params={"category": category}, headers=h)
    assert page.status_code == 200
    assert page.json()["data"][0]["category"] == category
    assert page.json()["meta"]["live_source"] == "Provider"
    detail = client.get("/api/v1/opportunities/" + row["id"], headers=h)
    assert detail.json()["data"]["id"] == row["id"]
    saved = client.post("/api/v1/applications", json={"opportunity_id": row["id"]}, headers=h)
    assert saved.status_code == 201, saved.text


def test_coding_contests_exclude_completed_and_past(monkeypatch):
    future = datetime.now(timezone.utc).timestamp() + 86400
    rows = [
        dict(id=1, name="Upcoming", phase="BEFORE", startTimeSeconds=future),
        dict(id=2, name="Finished", phase="FINISHED", startTimeSeconds=future),
        dict(id=3, name="Old", phase="BEFORE", startTimeSeconds=1),
    ]
    monkeypatch.setattr(
        sources, "_fetch", lambda url: json.dumps(dict(status="OK", result=rows)).encode()
    )
    assert [r["title"] for r in sources._load("coding_competition")] == ["Upcoming"]


def test_provider_failure_is_cached_and_isolated(monkeypatch):
    monkeypatch.setattr(sources, "_cache", {})
    calls = []

    def unavailable(category):
        calls.append(category)
        raise requests.Timeout()

    monkeypatch.setattr(sources, "_load", unavailable)
    assert sources.listings("grant") == sources.listings("grant") == []
    assert calls == ["grant"]


def test_concurrent_pages_share_one_provider_request(monkeypatch):
    monkeypatch.setattr(sources, "_cache", {})
    calls = []
    monkeypatch.setattr(sources, "_load", lambda category: calls.append(category) or [])
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(sources.listings, ["coding_competition"] * 2))
    assert calls == ["coding_competition"]


def test_innovation_filter_rejects_unrelated_writing_competition(monkeypatch):
    stamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    payload = f"<rss><channel><item><title>Economics Writing Challenge</title><link>https://opportunitydesk.org/example</link><pubDate>{stamp}</pubDate></item></channel></rss>"
    monkeypatch.setattr(sources, "_fetch", lambda url: payload.encode())
    assert sources._rss("innovation_challenge") == []
