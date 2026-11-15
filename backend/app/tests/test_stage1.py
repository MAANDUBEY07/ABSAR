from datetime import date
from unittest.mock import patch
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.schemas.opportunity import OpportunityInput
from app.integrations.normalization import deadline
from app.integrations.notice import extract_draft
from app.services.ai_extractor import ExtractedOpportunity
from app.repositories import documents
from app.config.database import Session
from app.services.jobs import enqueue
from app.config import settings


@pytest.mark.parametrize("value", ["2026-12-31", "31 December 2026", "31/12/2026", "12/31/2026"])
def test_deadline_formats(value):
    assert deadline(value) == date(2026, 12, 31)


@pytest.mark.parametrize("value", ["02/03/2026", "2026-02-30", "unknown", 123])
def test_uncertain_deadlines_rejected(value):
    with pytest.raises(ValueError):
        OpportunityInput(title="Source", deadline=value)


def test_legacy_category_mode_read_without_rewrite(client, headers):
    h = headers()
    documents.put(
        "opportunities",
        "legacy",
        {
            "id": "legacy",
            "title": "Source",
            "category": "coding_challenge",
            "remote": True,
            "location": "Delhi",
        },
    )
    item = client.get("/api/v1/opportunities/legacy", headers=h).json()["data"]
    assert item["category"] == "coding_competition"
    assert item["opportunity_mode"] == "online" and item["location"] == "Delhi"
    assert (
        client.get(
            "/api/v1/opportunities", headers=h, params={"category": "coding_competition"}
        ).json()["data"][0]["id"]
        == "legacy"
    )
    assert OpportunityInput(title="Source", remote=False).opportunity_mode is None
    assert OpportunityInput(title="Source", category="research").category == "research"


def test_notice_pipeline_uses_original_services():
    parsed = SimpleNamespace(
        text="Original source", page_count=1, has_extractable_text=True, warnings=[]
    )
    extracted = ExtractedOpportunity(
        title="Source",
        category="grant",
        deadline="02/03/2026",
        eligibility_criteria=["Source income criterion"],
    )
    with (
        patch("app.services.notice_parser.parse_pdf", return_value=parsed) as parser,
        patch("app.services.ai_extractor.extract_opportunity", return_value=extracted) as extractor,
    ):
        result = extract_draft(b"pdf", "source.pdf")
    parser.assert_called_once_with(b"pdf")
    extractor.assert_called_once_with("Original source", source_url=None)
    assert result["draft"]["deadline"] is None and result["warnings"]
    assert result["draft"]["requirements"]["confirmed"] is False
    assert result["draft"]["source_eligibility_criteria"] == ["Source income criterion"]


def test_notice_pipeline_does_not_invent_missing_text():
    parsed = SimpleNamespace(text="", has_extractable_text=False)
    with (
        patch("app.services.notice_parser.parse_pdf", return_value=parsed),
        pytest.raises(ValueError),
    ):
        extract_draft(b"pdf", "source.pdf")


def test_job_result_owner_and_error_contract(client, headers, monkeypatch):
    monkeypatch.setattr("app.services.jobs.dispatch", lambda: None)
    h, other = headers(), headers()
    owner = client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]
    with Session() as db:
        job = enqueue(db, owner, "unsupported", {"private_input": "not returned"})
        key = job.id
        job.status = "COMPLETED"
        job.payload = dict(job.payload, result={"skills": ["python"]})
        db.commit()
    response = client.get(f"/api/v1/jobs/{key}/result", headers=h)
    assert response.status_code == 200
    assert response.json()["data"]["result"] == {"skills": ["python"]}
    assert "private_input" not in response.text
    assert client.get(f"/api/v1/jobs/{key}/result", headers=other).status_code == 404
    assert client.get(f"/api/v1/jobs/{key}/result").status_code == 401


def test_cognito_settings_rejected():
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(auth_provider="cognito")
    assert settings.auth_provider in {"supabase", "local"}


def test_configured_notice_worker_draft_not_publication(client, headers, monkeypatch):
    from app.tests.test_persistent import pdf

    monkeypatch.setattr("app.services.jobs.dispatch", lambda: None)
    h = headers()
    uploaded = client.post(
        "/api/v1/notices/upload",
        headers=h,
        files={"file": ("notice.pdf", pdf("Source grant"), "application/pdf")},
    )
    assert uploaded.status_code == 201
    key = uploaded.json()["data"]["id"]
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    source = ExtractedOpportunity(title="Source grant", category="grant")
    with patch("app.services.ai_extractor.extract_opportunity", return_value=source):
        job_id = client.post(f"/api/v1/notices/{key}/extract", headers=h).json()["data"]["job_id"]
        from app.services.jobs import execute

        execute(job_id)
    result = client.get(f"/api/v1/jobs/{job_id}/result", headers=h).json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["result"]["status"] == "NEEDS_REVIEW"
    assert result["result"]["draft"]["provenance"] == "MEMBER1_AI_EXTRACTION"
    assert not documents.scan("opportunities")
