from datetime import timedelta
from unittest.mock import patch
import pytest
from sqlalchemy import select, func
from app.config.database import Session
from app.models.base import now
from app.models.runtime import Job, LocalDocument
from app.repositories import documents
from app.services import jobs
from app.services.catalog import create_opportunity
from app.services.matching import match
from app.services.eligibility_adapter import evaluate_opportunity
from app.services.verification_refresh import refresh
from app.integrations import member1
from app.services.trust_checker import analyze, check_opportunity_trust
from app.services.ai_extractor import ExtractedOpportunity
from app.schemas.opportunity import CANONICAL_CATEGORIES, OpportunityInput


@pytest.mark.parametrize(
    "confirmed,criteria,profile,expected",
    [
        (False, {"min_cgpa": 9}, {"cgpa": 6}, "UNKNOWN"),
        (True, {}, {}, "ELIGIBLE"),
        (True, {"min_cgpa": 7}, {}, "UNKNOWN"),
        (True, {"min_cgpa": 7}, {"cgpa": 6}, "INELIGIBLE"),
    ],
)
def test_one_eligibility_decision(confirmed, criteria, profile, expected):
    item = {"id": "o", "title": "Source", "requirements": dict(criteria, confirmed=confirmed)}
    result = match(profile, item)
    engine = evaluate_opportunity(profile, item)
    assert result["eligibility"] == expected
    assert result["eligibility_detail"] == engine


@pytest.mark.parametrize(
    "income,expected", [(None, "UNKNOWN"), (200000, "ELIGIBLE"), (400000, "INELIGIBLE")]
)
def test_explicit_demographic_rules(income, expected):
    item = {
        "id": "o",
        "title": "Source",
        "requirements": {
            "confirmed": True,
            "max_annual_income": 250000,
            "domicile_states": ["Delhi"],
        },
    }
    profile = {"domicile_state": "delhi", "annual_income": income}
    assert match(profile, item)["eligibility"] == expected


def test_observations_and_fuzzy_review_preserve_both_records(client):
    data = {
        "title": "Python student internship opportunity",
        "organization": "Campus org",
        "application_url": "https://campus.example/apply",
        "source_url": "https://one.example",
        "category_metadata": {"amount": 100},
    }
    first = create_opportunity(data)
    second = create_opportunity(
        dict(data, source_url="https://two.example", category_metadata={"amount": 200})
    )
    assert first["id"] == second["id"]
    observations = documents.related("opportunity_observations", "opportunity_id", first["id"])
    assert len(observations) == 2
    assert {o["data"]["category_metadata"]["amount"] for o in observations} == {100, 200}
    create_opportunity(
        dict(data, source_url="https://two.example", category_metadata={"amount": 200})
    )
    assert len(documents.related("opportunity_observations", "opportunity_id", first["id"])) == 2
    third = create_opportunity(dict(data, title="Python student internship opportunities"))
    assert third["id"] != first["id"]
    reviews = documents.related("duplicate_reviews", "candidate_id", third["id"])
    assert reviews and reviews[0]["action"] == "HUMAN_REVIEW_REQUIRED"
    assert len(documents.scan("opportunities")) == 2


def test_recovery_exhaustion_updates_notice(client):
    documents.put(
        "extracted_notices", "n", {"owner_id": "u", "status": "PROCESSING", "draft": None}
    )
    with Session.begin() as db:
        db.add(
            Job(
                id="j",
                owner_id="u",
                dedupe_key="d",
                status="RUNNING",
                attempts=3,
                lease_until=now() - timedelta(seconds=1),
                payload={"kind": "notice", "arguments": {"document_id": "n"}},
            )
        )
    jobs.recover()
    assert documents.get("extracted_notices", "n")["status"] == "FAILED"
    with Session() as db:
        assert db.get(Job, "j").status == "DEAD_LETTER"


def test_refresh_advances_after_allegations(client):
    with Session.begin() as db:
        db.add_all(
            [
                LocalDocument(
                    collection="verification_results",
                    id=f"a{i:04}",
                    payload={"owner_id": "u", "type": "USER_ALLEGATION", "opportunity_id": "other"},
                )
                for i in range(105)
            ]
        )
    item = create_opportunity({"title": "Source"})
    documents.put("verification_results", "zzz", {"owner_id": "u", "opportunity_id": item["id"]})
    with patch("app.integrations.member1.analyze_trust", return_value=analyze(item)) as provider:
        refresh()
        assert provider.call_count == 1


@pytest.mark.parametrize(
    "text", ["We never ask for OTP.", "No guaranteed job or placement is offered."]
)
def test_denials_are_not_signals(text):
    assert analyze({"description": text})["risk_score"] == 0
    report = check_opportunity_trust({"description": text})
    assert not any("Demands sensitive" in signal for signal in report.negative_indicators)


def test_negation_does_not_hide_affirmative_request():
    assert (
        analyze({"description": "We never ask for OTP, but send your credit card number."})[
            "risk_score"
        ]
        > 0
    )


def test_trust_get_is_read_only(client, headers):
    h = headers()
    item = create_opportunity({"title": "Source"})
    with Session() as db:
        before = db.scalar(select(func.count()).select_from(LocalDocument))
    assert client.get(f"/api/v1/trust/verify/{item['id']}", headers=h).status_code == 404
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(LocalDocument)) == before
    assert (
        client.post(
            "/api/v1/verification/analyze", headers=h, json={"opportunity_id": item["id"]}
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/trust/verify/{item['id']}", headers=h).status_code == 200


def test_real_resume_interface_and_owned_result():
    result = member1.analyze_resume(
        "Python SQL. B.Tech in Computer Science. 2 years experience.", "owner", "doc"
    )
    assert result["owner_id"] == "owner" and result["document_id"] == "doc"
    assert "python" in result["parsed_skills"] and result["experience_years"] == 2
    assert result["readiness_score"] is not None
    assert result["warnings"] and result["evidence"]


@pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
def test_member1_and_backend_category_contract(category):
    extracted = ExtractedOpportunity(
        title="Source",
        category=category,
        opportunity_mode="hybrid",
        category_metadata={"source": "explicit"},
    )
    assert (
        OpportunityInput(
            title=extracted.title,
            category=extracted.category,
            opportunity_mode=extracted.opportunity_mode,
            category_metadata=extracted.category_metadata,
        ).category
        == category
    )


def test_member1_scraped_data_enters_ingestion(client):
    from app.services.scraper import ScrapedOpportunity

    source = ScrapedOpportunity(
        id="source-id",
        title="Student grant",
        category="grant",
        organization="Campus",
        description="Original",
        source_url="https://campus.example",
        source_name="Campus",
        category_metadata={"source_fact": 1},
    )
    result = member1.ingest_scraped(source)
    assert result["source_attribution"] == "Campus" and result["retrieved_at"]
    assert result["provenance"]["id"] == "source-id" and result["category_metadata"] == {
        "source_fact": 1
    }


def test_registered_source_worker_uses_pinned_fetch(client, headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "discovery_sources", ["nsp_portal"])
    h = headers()
    with patch(
        "app.services.safe_fetch.fetch",
        return_value=b'<article><h2>Student scholarship award</h2><a href="/apply">Apply</a><p>Source description</p></article>',
    ) as fetch:
        response = client.post("/api/v1/discovery/sources/nsp_portal/jobs", headers=h)
    assert response.status_code == 202, response.text
    job = client.get("/api/v1/jobs/" + response.json()["data"]["job_id"], headers=h).json()["data"]
    assert job["status"] == "COMPLETED", job
    assert job["result"]["opportunity_ids"]
    fetch.assert_called_once()
    assert client.post("/api/v1/discovery/sources/unknown/jobs", headers=h).status_code == 422
