"""Detail reads only inspect records with usable source material."""

import pytest

from app.repositories import documents
from app.services import source_intelligence


@pytest.mark.parametrize("description", ["", "Brief description", " " * 40])
def test_minimal_record_reads_do_not_enrich(client, headers, monkeypatch, description):
    def unexpected_enrichment(*args, **kwargs):
        pytest.fail("A record without source material must not be enriched on read")

    monkeypatch.setattr(source_intelligence, "enrich_opportunity", unexpected_enrichment)
    auth = headers()
    created = client.post(
        "/api/v1/opportunities",
        headers=auth,
        json={"title": "Minimal listing", "description": description},
    )
    assert created.status_code == 201
    record = created.json()["data"]
    for _ in range(2):
        response = client.get("/api/v1/opportunities/" + record["id"], headers=auth)
        assert response.status_code == 200
        assert response.json()["data"] == record
    assert documents.get("opportunities", record["id"]) == record


@pytest.mark.parametrize(
    "source",
    [
        {"source_url": "https://example.org/listing"},
        {"application_url": "https://example.org/apply"},
        {"description": "Requirements: Python and SQL experience required for this role."},
    ],
)
def test_records_with_source_material_are_still_enriched(client, headers, monkeypatch, source):
    calls = []

    def enrich(record):
        calls.append(record["id"])
        return dict(record, source_summary={"fetch_status": "SUCCESS"})

    monkeypatch.setattr(source_intelligence, "enrich_opportunity", enrich)
    auth = headers()
    created = client.post(
        "/api/v1/opportunities", headers=auth, json={"title": "Source listing", **source}
    )
    assert created.status_code == 201
    record_id = created.json()["data"]["id"]
    response = client.get("/api/v1/opportunities/" + record_id, headers=auth)
    assert response.status_code == 200
    assert response.json()["data"]["source_summary"]["fetch_status"] == "SUCCESS"
    assert calls == [record_id]


def test_explicit_refresh_reports_missing_source(client, headers):
    auth = headers()
    created = client.post(
        "/api/v1/opportunities", headers=auth, json={"title": "No source listing"}
    )
    assert created.status_code == 201
    record_id = created.json()["data"]["id"]
    response = client.post(
        f"/api/v1/opportunities/{record_id}/refresh-source", headers=auth, json={}
    )
    assert response.status_code == 200
    summary = response.json()["data"]["source_summary"]
    assert summary["fetch_status"] == "FAILED"
    assert summary["failure_reason"] == "No source URL or description available"
