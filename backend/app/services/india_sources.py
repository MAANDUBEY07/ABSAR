"""Keyless India opportunity sources, isolated and cached per upstream request.

Unstop and Opportunity Desk expose public JSON. Indian Government Jobs and
Scholarships.net.in syndicate RSS. Official Startup India pages supply programme
catalog entries, explicitly distinguished from confirmed open registrations.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import re
import threading
import time
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
import requests

from app.schemas.opportunity import CANONICAL_CATEGORIES
from app.services.location_filter import STATE_CITIES, normalize, contains

logger = logging.getLogger(__name__)
CACHE_SECONDS = 1800
STALE_SECONDS = 21600
RETRY_SECONDS = 60
MAX_BYTES = 3 * 1024 * 1024
USER_AGENT = "AVSAR/1.0 (opportunity discovery)"
UNSTOP = "https://unstop.com/api/public/opportunity/search-result"
ICSSR_CALL = "https://www.icssr.org/index.php/announcements/2nd-call-applications-icssrs-senior-fellowship-2026"
OD = "https://opportunitydesk.org/wp-json/wp/v2/posts?" + urlencode(
    {"search": "India", "per_page": 30, "_fields": "id,date,link,title,excerpt,content"}
)
RSS = {
    "scholarships": ("https://www.scholarships.net.in/feed", "Scholarships.net.in"),
    "apprenticeships": (
        "https://www.indgovtjobs.in/feeds/posts/default?alt=rss",
        "Indian Government Jobs",
    ),
}
# These are ongoing official programme pages, not fabricated application windows.
SCHEMES = {
    "recognition": (
        "https://www.startupindia.gov.in/content/sih/en/startup-scheme.html",
        "DPIIT Startup Recognition and Benefits",
    ),
    "credit": (
        "https://www.startupindia.gov.in/content/sih/en/credit-guarantee-scheme-for-startups.html",
        "Credit Guarantee Scheme for Startups",
    ),
}
QUERIES = {
    "job": {"opportunity": "jobs"},
    "internship": {"opportunity": "internships"},
    "scholarship": {"opportunity": "scholarships"},
    "hackathon": {"opportunity": "hackathons"},
    "coding_competition": {"opportunity": "competitions", "searchTerm": "coding"},
    "innovation_challenge": {"opportunity": "competitions", "searchTerm": "innovation"},
    "startup_challenge": {"opportunity": "competitions", "searchTerm": "startup"},
}
ALLOWED_HOSTS = {
    "unstop.com",
    "opportunitydesk.org",
    "www.scholarships.net.in",
    "www.indgovtjobs.in",
    "www.startupindia.gov.in",
    "www.icssr.org",
}
_cache = {}
_locks = {}
_registry_lock = threading.Lock()


def _fetch(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Unsupported India provider URL")
    started = time.monotonic()
    with requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=(2, 5),
        stream=True,
        allow_redirects=False,
    ) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Provider did not return a successful response")
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > MAX_BYTES or time.monotonic() - started > 8:
                raise ValueError("Provider exceeded retrieval budget")
        return bytes(body)


def _text(value, maximum=2000):
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)[:maximum]


def _url(value, host):
    if not isinstance(value, str):
        return None
    url = urljoin(f"https://{host}/", value)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password:
        return None
    return url.split("#", 1)[0].split("?", 1)[0]


def _date(value):
    if not value:
        return None
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    value = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", value)
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _deadline(text):
    match = re.search(
        r"(?:deadline|last date(?: to apply)?|apply by)\s*[:\-]?\s*"
        r"(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|"
        r"[A-Za-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})",
        text,
        re.I,
    )
    return _date(match.group(1)) if match else None


def _record(
    category, title, url, provider, description, *, location="India", deadline=None, **fields
):
    from app.services.category_sources import _record as make_record

    organization = fields.pop("organization", provider)
    return make_record(
        category,
        title,
        url,
        provider,
        description,
        location=location,
        deadline=deadline.isoformat() if deadline else None,
        **fields,
    ) | {
        "organization": organization,
        "category_metadata": {
            "country": "India",
            "eligibility_status": "Check the original source",
            "application_status": "Check the original source",
        },
    }


def _unstop_category(item):
    title = _text(item.get("title"), 300).casefold()
    kind, subtype = item.get("type"), item.get("subtype")
    if re.search(r"\bapprentice(?:ship)?\b", title):
        return "apprenticeship"
    if kind == "jobs":
        return "internship" if subtype == "internships" else "job"
    if kind == "scholarships":
        return "fellowship" if re.search(r"\bfellowships?\b", title) else "scholarship"
    if kind == "hackathons":
        return "hackathon"
    if kind == "competitions":
        if re.search(r"\b(start-?up|entrepreneur|pitch)\b", title):
            return "startup_challenge"
        if subtype == "innovation_challenge" or re.search(r"\binnovation\b", title):
            return "innovation_challenge"
        if subtype == "online_coding_challenge" or re.search(
            r"\b(coding|programming|competitive code)\b", title
        ):
            return "coding_competition"
    return None


def _unstop_row(item):
    if not isinstance(item, dict) or item.get("regn_open") not in (1, True, "1"):
        return None
    category = _unstop_category(item)
    title = _text(item.get("title"), 300)
    url = _url(item.get("seo_url") or item.get("public_url"), "unstop.com")
    registration = item.get("regnRequirements") or {}
    end = registration.get("end_regn_dt") or item.get("end_date")
    deadline = _date(end)
    today = datetime.now(timezone.utc).date()
    if not category or not title or not url or (deadline and deadline < today):
        return None
    # Registration has its own deadline; the event date can be much later.
    if end:
        try:
            instant = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            if instant.tzinfo and instant < datetime.now(timezone.utc):
                return None
        except ValueError:
            pass
    start = registration.get("start_regn_dt")
    if start:
        try:
            instant = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            if instant.tzinfo and instant > datetime.now(timezone.utc):
                return None
        except ValueError:
            pass

    places = list(item.get("locations") or [])
    address = item.get("address_with_country_logo")
    if isinstance(address, dict):
        places.append(address)
    indian_places, countries = [], set()
    for place in places:
        if not isinstance(place, dict):
            continue
        country = place.get("country") or ""
        country = country.get("name", "") if isinstance(country, dict) else str(country)
        if country:
            countries.add(country.casefold())
        if country.casefold() == "india":
            indian_places.append(
                ", ".join(
                    dict.fromkeys(
                        _text(place.get(k), 100)
                        for k in ("city", "state", "country")
                        if isinstance(place.get(k), str) and place.get(k)
                    )
                )
                if isinstance(place.get("country"), str)
                else ", ".join(
                    filter(
                        None,
                        [_text(place.get("city"), 100), _text(place.get("state"), 100), "India"],
                    )
                )
            )
    job = item.get("jobDetail") or {}
    # For employment the job's work type outranks the registration region:
    # Unstop uses region=online for applying to many in-office jobs.
    work_type = job.get("type") if item.get("type") == "jobs" else item.get("region")
    mode = {
        "wfh": "online",
        "online": "online",
        "in_office": "offline",
        "on_field": "offline",
        "offline": "offline",
        "hybrid": "hybrid",
    }.get(work_type)
    description = _text(item.get("details"), 2000)
    evidence = "structured_location"
    if not indian_places:
        # Do not relabel a foreign-only posting as an Indian opportunity.
        if countries:
            return None
        location_terms = normalize(
            " ".join(str(x) for x in job.get("locations", []) if isinstance(x, str))
        )
        known = any(
            contains(location_terms, normalize(name))
            for state, cities in STATE_CITIES.items()
            for group in [state, *cities]
            for name in group.split("|")
        )
        if known:
            indian_places = [_text(location_terms, 400) + ", India"]
            evidence = "indian_city"
        elif mode == "online" and job.get("currency") in {"fa-rupee", "INR"}:
            # India-market remote listing. Individual citizenship/residency
            # eligibility remains unconfirmed and is never inferred from currency.
            indian_places = ["Remote, India"]
            evidence = "india_market_remote_currency"
        elif re.search(r"\b(?:india|indian)\b", description, re.I):
            indian_places = ["India"]
            evidence = "source_description"
        else:
            return None
    organization = item.get("organisation") or {}
    record = _record(
        category,
        title,
        url,
        "Unstop",
        description,
        organization=_text(organization.get("name"), 300) or "Unstop",
        location="; ".join(indian_places),
        deadline=deadline,
        opportunity_mode=mode,
        remote=True if mode == "online" else None,
        provenance={
            "provider": "Unstop",
            "provider_id": str(item.get("id")),
            "india_evidence": evidence,
            "registration_deadline": end,
        },
    )
    return record


def _load_unstop(category):
    query = {**QUERIES[category], "oppstatus": "open", "per_page": 50, "page": 1}
    payload = json.loads(_fetch(UNSTOP + "?" + urlencode(query)))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Unsupported Unstop response")
    rows = []
    for item in data["data"][:50]:
        try:
            row = _unstop_row(item)
        except (AttributeError, TypeError, ValueError):
            # One malformed listing must not suppress the rest of the feed.
            continue
        if row:
            rows.append(row)
    return rows


def _rss_category(title):
    if re.search(r"\bapprentice(?:s|ship)?\b", title, re.I):
        return "apprenticeship"
    if re.search(r"\bfellowships?\b", title, re.I):
        return "fellowship"
    if re.search(r"\bscholarships?\b", title, re.I):
        return "scholarship"
    if re.search(r"\b(recruitment|vacanc(?:y|ies))\b", title, re.I):
        return "job"
    return None


def _load_rss(key):
    url, provider = RSS[key]
    root = ElementTree.fromstring(_fetch(url))
    rows = []
    for item in root.findall(".//item")[:40]:
        title = _text(item.findtext("title"), 300)
        link = _url(item.findtext("link"), urlsplit(url).hostname)
        category = _rss_category(title)
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - published
            if age > timedelta(days=60) or age < -timedelta(days=1):
                continue
        except (TypeError, ValueError):
            continue
        raw_body = item.findtext("description") or ""
        body = _text(raw_body, 20000)
        deadline = _deadline(title + " " + body)
        if not category or not link or (deadline and deadline < datetime.now(timezone.utc).date()):
            continue
        # RSS excerpts are syndicated; do not copy the publisher's full article.
        excerpt = body[:600]
        location = "India"
        for table_row in BeautifulSoup(raw_body, "html.parser").select("tr"):
            cells = table_row.find_all(["th", "td"], recursive=False)
            if len(cells) >= 2 and normalize(cells[0].get_text()) in {
                "job location",
                "work location",
                "location",
            }:
                place = _text(cells[1].get_text(" ", strip=True), 400)
                if place:
                    location = place if "india" in place.casefold() else place + ", India"
                break
        row = _record(
            category,
            title,
            link,
            provider,
            excerpt,
            deadline=deadline,
            location=location,
            provenance={"provider": provider, "published_at": published.isoformat()},
        )
        rows.append(row)
    return rows


def _eligibility_text(soup):
    parts = []

    def is_heading(tag):
        return getattr(tag, "name", "") in {"h2", "h3", "h4"} or (
            getattr(tag, "name", "") == "p"
            and tag.find("strong")
            and len(tag.get_text(" ", strip=True)) < 100
        )

    for heading in soup.find_all(["h2", "h3", "h4", "p"]):
        if not is_heading(heading) or not re.search(
            r"eligib|who can apply|eligible countries", heading.get_text(), re.I
        ):
            continue
        for sibling in heading.next_siblings:
            if is_heading(sibling):
                break
            if hasattr(sibling, "get_text"):
                parts.append(sibling.get_text(" ", strip=True))
    return " ".join(parts)


def _load_opportunity_desk():
    payload = json.loads(_fetch(OD))
    if not isinstance(payload, list):
        raise ValueError("Unsupported Opportunity Desk response")
    rows = []
    for item in payload[:30]:
        if not isinstance(item, dict):
            continue
        title = _text((item.get("title") or {}).get("rendered"), 300)
        category = (
            "fellowship"
            if re.search(r"\bfellows?(?:hip)?s?\b", title, re.I)
            else (
                "grant"
                if re.search(r"\b(grants?|funding|fund|request for proposals)\b", title, re.I)
                else None
            )
        )
        if not category or re.match(r"\d+\s", title):
            continue
        link = _url(item.get("link"), "opportunitydesk.org")
        soup = BeautifulSoup((item.get("content") or {}).get("rendered", ""), "html.parser")
        eligibility = _eligibility_text(soup)
        # An India keyword in an author bio or unrelated story isn't evidence.
        if not re.search(
            r"\b(?:India|Indian|all nationalities|any nationality|any country|worldwide|countries across Asia and the Pacific)\b",
            eligibility,
            re.I,
        ):
            continue
        if re.search(r"(?:excluding|except|not open to)\s+India", eligibility, re.I):
            continue
        deadline = _deadline(soup.get_text(" ", strip=True))
        if not link or not deadline or deadline < datetime.now(timezone.utc).date():
            continue
        rows.append(
            _record(
                category,
                title,
                link,
                "Opportunity Desk",
                _text((item.get("excerpt") or {}).get("rendered"), 600),
                location="International; applicants from India may apply",
                deadline=deadline,
                provenance={
                    "provider": "Opportunity Desk",
                    "india_eligibility_evidence": eligibility[:1200],
                },
            )
        )
    return rows


def _load_scheme(key):
    url, title = SCHEMES[key]
    soup = BeautifulSoup(_fetch(url), "html.parser")
    text = soup.get_text(" ", strip=True)
    expected = "recognition" if key == "recognition" else "credit guarantee"
    if expected not in text.casefold() or len(text) < 1000:
        raise ValueError("Official scheme page is unavailable")
    description = soup.find("meta", attrs={"name": "description"})
    excerpt = _text(description.get("content") if description else "", 600)
    row = _record(
        "government_scheme",
        title,
        url,
        "Startup India / DPIIT",
        (
            excerpt
            + " Official programme information. Review the source for current application availability and eligibility."
        ).strip(),
        provenance={"provider": "Startup India / DPIIT", "entry_type": "official_programme"},
    )
    row["category_metadata"]["application_status"] = (
        "Programme catalog; check application availability"
    )
    return [row]


def _load_icssr():
    soup = BeautifulSoup(_fetch(ICSSR_CALL), "html.parser")
    title = next(
        (h for h in soup.find_all(["h1", "h2", "h3"]) if "fellowship" in h.get_text().casefold()),
        None,
    )
    text = soup.get_text(" ", strip=True)
    match = re.search(
        r"(?:last date for online submission of application is|Close of online submission of applications)\s*(\d{2}\.\d{2}\.\d{4})",
        text,
        re.I,
    )
    deadline = _date(match.group(1)) if match else None
    if not title or not deadline or deadline < datetime.now(timezone.utc).date():
        return []
    title = _text(title.get_text(), 300)
    if "fellowship" not in title.casefold() or "Indian scholars" not in text:
        return []
    return [
        _record(
            "fellowship",
            title,
            ICSSR_CALL,
            "ICSSR / Ministry of Education",
            "ICSSR invites applications from Indian scholars under its Senior Fellowship Scheme. Review the official guidelines, affiliation requirements and application procedure before applying.",
            deadline=deadline,
            provenance={
                "provider": "ICSSR",
                "entry_type": "official_call",
                "india_evidence": "Indian scholars",
            },
        )
    ]


def _keys(category):
    if category and category not in CANONICAL_CATEGORIES:
        return []
    keys = ["unstop:" + c for c in QUERIES if not category or c == category]
    # Some provider types normalize into another canonical category; detail
    # lookups must use the same query that discovered them on All categories.
    if category == "fellowship":
        keys.append("unstop:scholarship")
    if category == "apprenticeship":
        keys.extend(["unstop:job", "unstop:internship"])
    if not category or category in {"job", "apprenticeship"}:
        keys.append("rss:apprenticeships")
    if not category or category == "scholarship":
        keys.append("rss:scholarships")
    if not category or category in {"fellowship", "grant"}:
        keys.append("opportunity_desk")
    if not category or category == "fellowship":
        keys.append("icssr")
    if not category or category == "government_scheme":
        keys.extend("scheme:" + key for key in SCHEMES)
    return keys


def _load(key):
    if key == "icssr":
        return _load_icssr()
    if key.startswith("unstop:"):
        return _load_unstop(key.split(":", 1)[1])
    if key.startswith("rss:"):
        return _load_rss(key.split(":", 1)[1])
    if key.startswith("scheme:"):
        return _load_scheme(key.split(":", 1)[1])
    return _load_opportunity_desk()


def _snapshot(key):
    with _registry_lock:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        now = time.monotonic()
        entry = _cache.get(key)
        if entry and now < entry["retry_at"]:
            return entry["rows"] if now - entry["fetched_at"] < STALE_SECONDS else []
        try:
            rows = _load(key)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            ElementTree.ParseError,
            DefusedXmlException,
        ) as exc:
            logger.warning("India opportunity source %s failed: %s", key, type(exc).__name__)
            entry = dict(
                entry or {"rows": [], "fetched_at": now - STALE_SECONDS},
                retry_at=now + RETRY_SECONDS,
                available=False,
            )
            _cache[key] = entry
            return entry["rows"] if now - entry["fetched_at"] < STALE_SECONDS else []
        _cache[key] = {
            "rows": rows,
            "fetched_at": now,
            "retry_at": now + CACHE_SECONDS,
            "available": True,
        }
        return rows


def listings(category=None):
    keys = _keys(category)
    if not keys:
        return []
    with ThreadPoolExecutor(max_workers=min(4, len(keys))) as pool:
        batches = list(pool.map(_snapshot, keys))
    today = datetime.now(timezone.utc).date()
    unique = {}
    # Round-robin sources: page one of All categories must not be all jobs.
    for index in range(max((len(batch) for batch in batches), default=0)):
        for batch in batches:
            if index >= len(batch):
                continue
            row = batch[index]
            deadline = _date(row.get("deadline"))
            registration_end = (row.get("provenance") or {}).get("registration_deadline")
            if registration_end:
                try:
                    end = datetime.fromisoformat(str(registration_end).replace("Z", "+00:00"))
                    if end.tzinfo and end < datetime.now(timezone.utc):
                        continue
                except ValueError:
                    pass
            if (not category or row["category"] == category) and (
                not deadline or deadline >= today
            ):
                unique.setdefault(row["id"], row)
    return deepcopy(list(unique.values()))


def get_listing(record_id):
    category = record_id.removeprefix("live_").split("__", 1)[0]
    return next((row for row in listings(category) if row["id"] == record_id), None)


def source_status(category=None):
    return {
        key: {
            "available": _cache[key]["available"],
            "stale": not _cache[key]["available"],
        }
        for key in _keys(category)
        if key in _cache
    }
