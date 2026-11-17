from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json

import pytest
import requests

from app.schemas.application import ApplicationCreate
from app.schemas.opportunity import CANONICAL_CATEGORIES, OpportunityInput
from app.services import india_sources as sources
from app.repositories import documents


def future(days=10):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture
def unstop():
    return dict(
        id=123,
        title="Software Internship",
        type="jobs",
        subtype="internships",
        regn_open=1,
        region="online",
        seo_url="https://unstop.com/internships/software-123",
        details="<p>Work with the engineering team.</p>",
        organisation={"name": "Example Employer"},
        locations=[{"city": "Bengaluru", "state": "Karnataka", "country": "India"}],
        jobDetail={"type": "in_office", "currency": "fa-rupee"},
        end_date=future(20),
        regnRequirements={"end_regn_dt": future()},
    )


def test_unstop_location_work_type_deadline_and_contract(unstop):
    row = sources._unstop_row(unstop)
    assert row["category"] == "internship"
    assert row["location"] == "Bengaluru, Karnataka, India"
    assert row["organization"] == "Example Employer"
    assert row["opportunity_mode"] == "offline"  # region describes online applications
    assert row["deadline"] == sources._date(unstop["regnRequirements"]["end_regn_dt"]).isoformat()
    assert row["requirements"]["confirmed"] is False
    ApplicationCreate(opportunity_id=row["id"])
    OpportunityInput.model_validate(
        {k: v for k, v in row.items() if k not in {"id", "fingerprint", "verification_status"}}
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"regn_open": 0},
        {"regnRequirements": {"end_regn_dt": future(-1)}},
        {"regnRequirements": {"start_regn_dt": future(1)}},
        {"seo_url": "https://evil.example/steal"},
        {"locations": [{"city": "Berlin", "country": "Germany"}], "details": "Indian company"},
    ],
)
def test_unstop_rejects_closed_future_foreign_and_untrusted(unstop, changes):
    assert sources._unstop_row(dict(unstop, **changes)) is None


def test_country_object_and_remote_india_market(unstop):
    row = sources._unstop_row(
        dict(
            unstop,
            locations=[],
            address_with_country_logo={
                "city": "Mumbai",
                "state": "Maharashtra",
                "country": {"name": "India"},
            },
        )
    )
    assert row["location"] == "Mumbai, Maharashtra, India"
    remote = sources._unstop_row(
        dict(unstop, locations=[], jobDetail={"type": "wfh", "currency": "INR"})
    )
    assert remote["location"] == "Remote, India"
    assert remote["opportunity_mode"] == "online"
    assert remote["provenance"]["india_evidence"] == "india_market_remote_currency"
    assert remote["requirements"]["confirmed"] is False
    assert (
        sources._unstop_row(
            dict(unstop, locations=[], jobDetail={"type": "wfh", "currency": "USD"})
        )
        is None
    )


@pytest.mark.parametrize(
    "kind,subtype,title,category",
    [
        ("jobs", "jobs", "Analyst", "job"),
        ("jobs", "internships", "Intern", "internship"),
        ("scholarships", "national", "Science Scholarship", "scholarship"),
        ("hackathons", "online_coding_challenge", "Buildathon", "hackathon"),
        ("competitions", "online_coding_challenge", "Coding contest", "coding_competition"),
        ("competitions", "innovation_challenge", "Design Tomorrow", "innovation_challenge"),
        ("competitions", "general_competition", "Startup Pitch Challenge", "startup_challenge"),
        ("competitions", "case_competition", "Grant Thornton Case Study", None),
    ],
)
def test_categories_do_not_follow_keywords_in_query(kind, subtype, title, category):
    assert sources._unstop_category({"type": kind, "subtype": subtype, "title": title}) == category


def rss_item(title, published, description="", url="https://www.indgovtjobs.in/opening"):
    return f"<item><title>{title}</title><link>{url}</link><pubDate>{format_datetime(published)}</pubDate><description><![CDATA[{description}]]></description></item>"


def test_rss_excludes_old_and_expired_and_extracts_location(monkeypatch):
    now = datetime.now(timezone.utc)
    deadline = (now + timedelta(days=10)).strftime("%d-%m-%Y")
    payload = (
        "<rss><channel>"
        + "".join(
            [
                rss_item(
                    "IOCL Apprentice Recruitment | Last Date " + deadline,
                    now,
                    "<table><tr><td>Job Location</td><td>Himachal Pradesh</td></tr></table>",
                ),
                rss_item("Old Apprentice Recruitment", now - timedelta(days=100)),
                rss_item("Closed Apprentice Recruitment | Last Date 01-01-2000", now),
                rss_item("New Apprentice Recruitment", now, url="https://evil.example/advert"),
            ]
        )
        + "</channel></rss>"
    )
    monkeypatch.setattr(sources, "_fetch", lambda url: payload.encode())
    rows = sources._load_rss("apprenticeships")
    assert len(rows) == 1
    assert rows[0]["category"] == "apprenticeship"
    assert rows[0]["location"] == "Himachal Pradesh, India"
    assert rows[0]["deadline"] == (now + timedelta(days=10)).date().isoformat()


@pytest.mark.parametrize("heading", ["<h2>Eligibility</h2>", "<p><strong>Eligibility</strong></p>"])
def test_india_eligibility_section_and_deadlines(monkeypatch, heading):
    deadline = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%B %d, %Y")

    def post(title, eligible, date=deadline):
        return {
            "title": {"rendered": title},
            "link": "https://opportunitydesk.org/" + title.replace(" ", "-"),
            "excerpt": {"rendered": "<p>Published excerpt</p>"},
            "content": {
                "rendered": f"<p>Deadline: {date}</p>{heading}<ul><li>{eligible}</li></ul><p><strong>Application</strong></p><p>India mentioned in unrelated text.</p>"
            },
        }

    payload = [
        post("Research Fellowship", "Open to nationals of India and Nepal."),
        post("Climate Grant", "Open to any country."),
        post("Africa Fellowship", "Kenya and Uganda only."),
        post("Closed Grant", "India eligible", "January 1, 2000"),
        post("Excluded Grant", "Worldwide except India"),
    ]
    monkeypatch.setattr(sources, "_fetch", lambda url: json.dumps(payload).encode())
    rows = sources._load_opportunity_desk()
    assert [row["category"] for row in rows] == ["fellowship", "grant"]
    assert rows[0]["location"] == "International; applicants from India may apply"


def test_official_scheme_is_catalog_not_confirmed_application(monkeypatch):
    html = (
        "<html><title>DPIIT Recognition</title><body><h1>Startup Recognition</h1>"
        + ("Programme information. " * 100)
        + "</body></html>"
    )
    monkeypatch.setattr(sources, "_fetch", lambda url: html.encode())
    row = sources._load_scheme("recognition")[0]
    assert row["category"] == "government_scheme"
    assert row["deadline"] is None
    assert row["category_metadata"]["application_status"].startswith("Programme catalog")
    assert row["requirements"]["confirmed"] is False


def test_cache_single_fetch_isolation_deep_copy_and_stale_limit(monkeypatch):
    monkeypatch.setattr(sources, "_cache", {})
    monkeypatch.setattr(sources, "_keys", lambda category: ["one", "broken"])
    clock = [100000.0]
    monkeypatch.setattr(sources.time, "monotonic", lambda: clock[0])
    calls = []

    def load(key):
        calls.append(key)
        if key == "broken":
            raise requests.Timeout()
        return [
            sources._record(
                "grant", "Science Grant", "https://example.org/science", "Test", "Excerpt"
            )
        ]

    monkeypatch.setattr(sources, "_load", load)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(sources.listings, ["grant", "grant"]))
    assert calls.count("one") == calls.count("broken") == 1
    results[0][0]["category_metadata"]["country"] = "modified"
    assert sources.listings("grant")[0]["category_metadata"]["country"] == "India"
    clock[0] += sources.CACHE_SECONDS + 1
    monkeypatch.setattr(sources, "_load", lambda key: (_ for _ in ()).throw(requests.Timeout()))
    assert len(sources.listings("grant")) == 1
    clock[0] += sources.STALE_SECONDS
    assert sources.listings("grant") == []


def test_country_category_filters_details_and_saving(client, headers, monkeypatch):
    rows = [
        sources._record(
            category,
            "India " + category,
            "https://example.org/" + category,
            "Test India Source",
            "Excerpt",
            location="Bengaluru, Karnataka, India",
        )
        for category in CANONICAL_CATEGORIES
    ]
    monkeypatch.setattr(
        sources,
        "listings",
        lambda category=None: [r for r in rows if not category or r["category"] == category],
    )
    monkeypatch.setattr(
        "app.services.source_intelligence.enrich_opportunity", lambda row, **kwargs: row
    )
    auth = headers()
    documents.put(
        "opportunities",
        "foreign",
        {"id": "foreign", "title": "Foreign", "location": "Berlin, Germany"},
    )
    page = client.get("/api/v1/opportunities", headers=auth, params={"country": "India"})
    assert page.status_code == 200
    assert {row["category"] for row in page.json()["data"]} == set(CANONICAL_CATEGORIES)
    for category in CANONICAL_CATEGORIES:
        filtered = client.get(
            "/api/v1/opportunities",
            headers=auth,
            params={
                "country": "India",
                "category": category,
                "state": "Karnataka",
                "location": "Bangalore",
            },
        )
        assert len(filtered.json()["data"]) == 1
    row = rows[0]
    detail = client.get("/api/v1/opportunities/" + row["id"], headers=auth)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == row["id"]
    saved = client.post("/api/v1/applications", headers=auth, json={"opportunity_id": row["id"]})
    assert saved.status_code == 201, saved.text
    assert saved.json()["data"]["opportunity_id"] == row["id"]


def test_all_category_order_has_multiple_categories_on_first_page(monkeypatch):
    monkeypatch.setattr(sources, "_keys", lambda category: ["jobs", "grants"])
    jobs = [
        sources._record("job", f"Job {n}", f"https://example.org/job{n}", "Test", "Excerpt")
        for n in range(30)
    ]
    grant = sources._record(
        "grant", "Science Grant", "https://example.org/grant", "Test", "Excerpt"
    )
    monkeypatch.setattr(sources, "_snapshot", lambda key: jobs if key == "jobs" else [grant])
    assert [r["category"] for r in sources.listings()[:2]] == ["job", "grant"]


def test_all_eleven_categories_have_a_source():
    assert all(sources._keys(category) for category in CANONICAL_CATEGORIES)


def test_malformed_unstop_listing_does_not_hide_valid_rows(monkeypatch, unstop):
    payload = {"data": {"data": [dict(unstop, regnRequirements="invalid"), unstop]}}
    monkeypatch.setattr(sources, "_fetch", lambda url: json.dumps(payload).encode())
    assert len(sources._load_unstop("internship")) == 1


def test_cached_registration_is_rechecked_at_read_time(monkeypatch):
    row = sources._record(
        "internship",
        "Expired today",
        "https://example.org/today",
        "Test",
        "Excerpt",
        provenance={
            "registration_deadline": (
                datetime.now(timezone.utc) - timedelta(seconds=10)
            ).isoformat()
        },
    )
    monkeypatch.setattr(sources, "_keys", lambda category: ["one"])
    monkeypatch.setattr(sources, "_snapshot", lambda key: [row])
    assert sources.listings() == []


def test_icssr_source_uses_official_call_deadline(monkeypatch):
    deadline = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%d.%m.%Y")
    html = f"<h2>Call for ICSSR Senior Fellowship</h2><p>Indian scholars may apply. The last date for online submission of application is {deadline}.</p>"
    monkeypatch.setattr(sources, "_fetch", lambda url: html.encode())
    row = sources._load_icssr()[0]
    assert row["category"] == "fellowship"
    assert row["location"] == "India"
    assert row["deadline"] == sources._date(deadline).isoformat()
    monkeypatch.setattr(
        sources, "_fetch", lambda url: html.replace(deadline, "01.01.2000").encode()
    )
    assert sources._load_icssr() == []


def test_international_outage_preserves_india_results(client, headers, monkeypatch):
    row = sources._record("job", "Indian job", "https://example.org/job", "Test", "Excerpt")
    monkeypatch.setattr(sources, "listings", lambda category=None: [row])
    monkeypatch.setattr(
        "app.services.arbeitnow.listings", lambda: (_ for _ in ()).throw(ValueError("offline"))
    )
    response = client.get("/api/v1/opportunities", headers=headers())
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == row["id"]


@pytest.mark.parametrize(
    "url", ["http://unstop.com/", "https://evil.example/", "https://user:pass@unstop.com/"]
)
def test_fetch_rejects_untrusted_urls(url):
    with pytest.raises(ValueError):
        sources._fetch(url)
