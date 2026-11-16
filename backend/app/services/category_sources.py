"""Category-specific public APIs and syndicated feeds, with bounded caching."""

import hashlib
import html
import json
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlsplit

import requests
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

CATEGORIES = {
    "government_scheme",
    "fellowship",
    "apprenticeship",
    "hackathon",
    "coding_competition",
    "innovation_challenge",
    "startup_challenge",
    "grant",
}
TERMS = {
    "fellowship": "fellowship",
    "apprenticeship": "apprenticeship",
    "innovation_challenge": "challenge",
    "startup_challenge": "startup",
    "grant": "grant",
}
PATTERNS = {
    "fellowship": r"\bfellowships?\b",
    "apprenticeship": r"\bapprenticeships?\b",
    "innovation_challenge": r"\b(impact|innovation|technology|climate|design)\b.*\b(challenge|competition|prize)\b",
    "startup_challenge": r"\b(pitch|startup|start-up|entrepreneur).*(competition|challenge|award|prize)\b",
    "grant": r"\b(grants?|fund|funding)\b",
}
_cache = {}
_locks = {category: threading.Lock() for category in CATEGORIES}


def _fetch(url):
    # URLs are constructed exclusively from the fixed provider registry below.
    start = time.monotonic()
    with requests.get(url, timeout=(2, 5), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Provider did not return a successful feed")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 3 * 1024 * 1024 or time.monotonic() - start > 7:
                raise ValueError("Provider response exceeds retrieval budget")
        return bytes(data)


def _text(value, maximum=30000):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()[
        :maximum
    ]


def _record(category, title, url, source, description="", **extra):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Provider returned an invalid listing URL")
    title = _text(title, 300)
    return dict(
        id=f"live_{category}__" + hashlib.sha256(url.encode()).hexdigest()[:24],
        title=title,
        category=category,
        description=_text(description),
        organization=source,
        source_url=url,
        application_url=url,
        source_attribution=source,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        category_metadata={"application_status": "Check the original source"},
        requirements={"confirmed": False},
        verification_status="UNKNOWN",
        fingerprint=hashlib.sha256(url.encode()).hexdigest(),
        **extra,
    )


def _rss(category):
    host = "www.opportunitiesforafricans.com"
    source = "Opportunities for Africans"
    url = f"https://{host}/?" + urlencode({"s": TERMS[category], "feed": "rss2"})
    if category == "grant":
        host, source = "opportunitydesk.org", "Opportunity Desk"
        url = "https://opportunitydesk.org/category/grants/feed/"
    elif category == "innovation_challenge":
        host, source = "opportunitydesk.org", "Opportunity Desk"
        url = "https://opportunitydesk.org/feed/"
    root = ElementTree.fromstring(_fetch(url))
    result = []
    for item in root.findall(".//item")[:30]:
        title, link = item.findtext("title") or "", item.findtext("link") or ""
        if not re.search(PATTERNS[category], title, re.I):
            continue
        if urlsplit(link).hostname not in {host, host.removeprefix("www.")}:
            continue
        if re.match(r"\d+\s+(grants|scholarships|opportunities)", title, re.I):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if (datetime.now(timezone.utc) - published).days > 90:
            continue
        # Syndicate the provider's RSS excerpt only; do not copy the full article.
        result.append(_record(category, title, link, source, item.findtext("description")))
    return result


def _load(category):
    if category in TERMS:
        return _rss(category)
    if category == "coding_competition":
        payload = json.loads(_fetch("https://codeforces.com/api/contest.list"))
        if payload.get("status") != "OK":
            raise ValueError("Contest provider unavailable")
        return [
            _record(
                category,
                row["name"],
                f"https://codeforces.com/contest/{row['id']}",
                "Codeforces",
                "Programming contest. Review the source for registration, rules and eligibility.",
                opportunity_mode="online",
                remote=True,
                deadline=datetime.fromtimestamp(row["startTimeSeconds"], timezone.utc)
                .date()
                .isoformat(),
            )
            for row in payload["result"]
            if row.get("phase") == "BEFORE" and row.get("startTimeSeconds", 0) > time.time()
        ][:100]
    if category == "hackathon":
        payload = json.loads(_fetch("https://devpost.com/api/hackathons?page=1&status[]=open"))
        return [
            _record(
                category,
                row["title"],
                row["url"],
                "Devpost",
                "Submission period: " + row.get("submission_period_dates", "Check source"),
                location=row.get("displayed_location", {}).get("location"),
                opportunity_mode=(
                    "online"
                    if row.get("displayed_location", {}).get("location", "").casefold() == "online"
                    else None
                ),
            )
            for row in payload["hackathons"]
            if row.get("open_state") == "open"
            and urlsplit(row["url"]).hostname.endswith(".devpost.com")
        ][:100]
    if category == "government_scheme":
        from app.services.scraper import OpportunityScraperService

        rows = OpportunityScraperService().scrape_source(
            "nsp_portal",
            html_override=_fetch("https://scholarships.gov.in/All-Scholarships").decode("utf-8"),
        )
        return [
            _record(
                category,
                row.title,
                row.application_url or row.source_url,
                "National Scholarship Portal",
                row.description,
                provenance={"original_category": row.category},
                # The official portal contains several schemes on one page.
            )
            | {
                "id": "live_government_scheme__"
                + hashlib.sha256(row.title.encode()).hexdigest()[:24],
                "fingerprint": hashlib.sha256(row.title.encode()).hexdigest(),
            }
            for row in rows
        ]
    return []


def listings(category):
    if category not in CATEGORIES:
        return []
    with _locks[category]:
        entry = _cache.get(category)
        if entry and time.monotonic() < entry[0]:
            return [dict(row) for row in entry[1]]
        try:
            rows = _load(category)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            ElementTree.ParseError,
            DefusedXmlException,
        ):
            _cache[category] = (time.monotonic() + 60, entry[1] if entry else [])
            return [dict(row) for row in entry[1]] if entry else []
        _cache[category] = (time.monotonic() + 21600, rows)
        return [dict(row) for row in rows]


def get_listing(record_id):
    category = record_id.removeprefix("live_").split("__", 1)[0]
    return next((row for row in listings(category) if row["id"] == record_id), None)
