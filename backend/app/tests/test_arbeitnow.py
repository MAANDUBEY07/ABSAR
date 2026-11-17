import json
import pytest
from app.services import arbeitnow
from app.schemas.application import ApplicationCreate


def test_provider_ids_fit_application_contract():
    row = arbeitnow._normalize(
        {
            "title": "Engineering internship",
            "slug": "long-slug" * 50,
            "url": "https://www.arbeitnow.com/jobs/example",
        },
        "2026-11-16T00:00:00Z",
    )
    assert row["category"] == "internship"
    assert ApplicationCreate(opportunity_id=row["id"])
    assert row["source_attribution"] == "Arbeitnow"
    assert row["requirements"]["confirmed"] is False


def test_untrusted_source_url_is_rejected():
    assert arbeitnow._normalize({"title": "Job", "url": "https://evil.example/jobs"}, "now") is None


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({"tags": ["Hybrid"], "remote": False}, "hybrid"),
        ({"tags": ["On-site"]}, "offline"),
        ({"tags": ["Fully remote"]}, "online"),
        ({"remote": True}, "online"),
        ({"remote": False}, None),
        ({"tags": ["Hybrid", "On-site"]}, None),
        ({"opportunity_mode": "hybrid", "remote": False}, "hybrid"),
        ({"title": "Hybrid Cloud Engineer", "tags": ["Hybrid Cloud"], "remote": False}, None),
    ],
)
def test_live_provider_mode_signals(fields, expected):
    row = arbeitnow._normalize(
        dict(title="Engineer", url="https://www.arbeitnow.com/jobs/engineer", **fields)
        if "title" not in fields
        else dict(url="https://www.arbeitnow.com/jobs/engineer", **fields),
        "2026-11-16T00:00:00Z",
    )
    assert row["opportunity_mode"] == expected


def test_live_listing_can_be_saved(client, headers, monkeypatch):
    row = arbeitnow._normalize(
        {
            "title": "Student internship",
            "slug": "internship" * 40,
            "url": "https://www.arbeitnow.com/jobs/internship",
        },
        "2026-11-16T00:00:00Z",
    )
    monkeypatch.setattr(arbeitnow, "listings", lambda: [row])
    h = headers()
    page = client.get("/api/v1/opportunities", headers=h)
    assert page.status_code == 200
    assert page.json()["data"][0]["id"] == row["id"]
    saved = client.post("/api/v1/applications", headers=h, json={"opportunity_id": row["id"]})
    assert saved.status_code == 201, saved.text
    assert saved.json()["data"]["status"] == "SAVED"


def test_listing_page_does_not_write_each_provider_record(client, headers, monkeypatch):
    from app.repositories import documents

    row = arbeitnow._normalize(
        {
            "title": "Student internship",
            "slug": "read-only",
            "url": "https://www.arbeitnow.com/jobs/read-only",
        },
        "2026-11-16T00:00:00Z",
    )
    monkeypatch.setattr(
        arbeitnow, "listings", lambda: [dict(row, id=f"arbeitnow_{n}") for n in range(20)]
    )

    def unexpected_write(*args, **kwargs):
        pytest.fail("Listing GET must not synchronously persist provider records")

    monkeypatch.setattr(documents, "put", unexpected_write)
    response = client.get("/api/v1/opportunities?limit=20", headers=headers())
    assert response.status_code == 200
    assert len(response.json()["data"]) == 20


def test_provider_outage_keeps_existing_catalog_available(client, headers, monkeypatch):
    def unavailable():
        raise OSError("provider unavailable")

    monkeypatch.setattr(arbeitnow, "listings", unavailable)
    response = client.get("/api/v1/opportunities", headers=headers())
    assert response.status_code == 200
    assert response.json()["meta"]["live_source_available"] is False


def test_feed_cache_and_bounded_large_response(monkeypatch):
    monkeypatch.setattr(arbeitnow, "_cache", None)
    calls = []

    def fetch(url, max_bytes):
        calls.append((url, max_bytes))
        return json.dumps(
            {
                "data": [
                    {
                        "title": "Developer",
                        "slug": "developer",
                        "url": "https://www.arbeitnow.com/jobs/developer",
                    }
                ]
            }
        ).encode()

    monkeypatch.setattr(arbeitnow, "fetch", fetch)
    assert arbeitnow.listings() == arbeitnow.listings()
    assert len(calls) == 1
    assert calls[0][1] == 8 * 1024 * 1024


def test_unsupported_provider_response(monkeypatch):
    monkeypatch.setattr(arbeitnow, "_cache", None)
    monkeypatch.setattr(arbeitnow, "fetch", lambda *args, **kwargs: b'{"error":"unavailable"}')
    with pytest.raises(ValueError):
        arbeitnow.listings()
