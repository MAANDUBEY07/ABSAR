"""Small, cached adapter for Arbeitnow's public jobs API.

Listings link back to Arbeitnow as required by its API terms. The feed is
Europe-focused and is not a source for India-wide scholarships or schemes.
"""

from __future__ import annotations

import json
import hashlib
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from app.services.safe_fetch import fetch

API_URL = "https://www.arbeitnow.com/api/job-board-api?page=1"
SOURCE_NAME = "Arbeitnow"
CACHE_SECONDS = 6 * 60 * 60
_lock = threading.Lock()
_cache: tuple[float, list[dict]] | None = None


def _plain_text(value: object, maximum: int = 30_000) -> str:
    text = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:maximum]


def _normalize(item: object, retrieved_at: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = _plain_text(item.get("title"), 300)
    listing_url = item.get("url")
    if not title or not isinstance(listing_url, str):
        return None
    parsed_url = urlsplit(listing_url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in {
        "www.arbeitnow.com",
        "arbeitnow.com",
    }:
        return None

    tags = item.get("tags")
    if not isinstance(tags, list):
        tags = []
    tags = [_plain_text(tag, 100) for tag in tags if isinstance(tag, str)][:30]
    title_tags = " ".join([title, *tags]).casefold()
    category = (
        "internship"
        if re.search(r"\b(intern(ship)?|praktikum|werkstudent|working student)\b", title_tags)
        else "job"
    )
    remote_value = item.get("remote")
    remote = remote_value if isinstance(remote_value, bool) else None
    slug = item.get("slug")
    provider_id = _plain_text(slug, 200) if isinstance(slug, str) else listing_url
    published = item.get("created_at") or item.get("date")

    return {
        "id": "arbeitnow_" + hashlib.sha256(provider_id.encode()).hexdigest()[:32],
        "title": title,
        "category": category,
        "opportunity_mode": "online" if remote is True else None,
        "category_metadata": {"provider": SOURCE_NAME, "tags": tags},
        "description": _plain_text(item.get("description")),
        "organization": _plain_text(item.get("company_name"), 300) or None,
        "application_url": listing_url,
        "source_url": listing_url,
        "source_attribution": SOURCE_NAME,
        "retrieved_at": retrieved_at,
        "provenance": {
            "provider": SOURCE_NAME,
            "provider_id": provider_id,
            "published_at": published,
        },
        "location": _plain_text(item.get("location"), 500) or None,
        "remote": remote,
        "domain": ", ".join(tags[:5]) or None,
        "requirements": {"confirmed": False},
        "fingerprint": f"arbeitnow:{provider_id}",
        "verification_status": "UNKNOWN",
    }


def listings() -> list[dict]:
    """Return a bounded snapshot, refreshing from the provider at most every six hours."""
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < CACHE_SECONDS:
        return [dict(row) for row in _cache[1]]

    with _lock:
        now = time.monotonic()
        if _cache and now - _cache[0] < CACHE_SECONDS:
            return [dict(row) for row in _cache[1]]
        payload = json.loads(fetch(API_URL, max_bytes=8 * 1024 * 1024))
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("Jobs provider returned an unsupported response")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        normalized = [
            row for item in rows[:300] if (row := _normalize(item, retrieved_at)) is not None
        ]
        _cache = (time.monotonic(), normalized)
        return [dict(row) for row in normalized]


def get_listing(record_id: str) -> dict | None:
    return next((row for row in listings() if row["id"] == record_id), None)
