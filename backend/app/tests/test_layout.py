"""Regression coverage for the requested package layout and documented routes."""

from datetime import date, timedelta
from pathlib import Path
import ast
from app.tests.test_persistent import OPPORTUNITY, post_opportunity, profile, pdf


def test_chart_files_contain_implementations():
    root = Path(__file__).resolve().parents[2]
    paths = [
        "main.py",
        "app/config/settings.py",
        "app/config/database.py",
        "app/models/profile.py",
        "app/models/opportunity.py",
        "app/models/resume.py",
        "app/models/application.py",
        "app/models/trust_report.py",
        "app/schemas/profile.py",
        "app/schemas/opportunity.py",
        "app/schemas/eligibility.py",
        "app/schemas/resume.py",
        "app/schemas/trust.py",
        "app/schemas/application.py",
        "app/routes/profile.py",
        "app/routes/opportunities.py",
        "app/routes/discovery.py",
        "app/routes/eligibility.py",
        "app/routes/resume.py",
        "app/routes/trust.py",
        "app/routes/applications.py",
        "app/routes/calendar.py",
        "app/services/ai_extractor.py",
        "app/services/notice_parser.py",
        "app/services/scraper.py",
        "app/services/resume_analyzer.py",
        "app/services/eligibility_engine.py",
        "app/services/trust_checker.py",
        "app/services/duplicate_detector.py",
        "app/utils/auth.py",
        "app/utils/file_handler.py",
        "app/utils/validators.py",
    ]
    for name in paths:
        source = (root / name).read_text(encoding="utf-8")
        assert "# Placeholder" not in source, name
        assert ast.parse(source).body, name
    from main import app as root_app
    from app.main import app

    assert root_app is app


def test_chart_profile_catalog_and_feed(client, headers):
    h = headers()
    profile(client, h)
    oid = post_opportunity(client, h)
    assert (
        client.get("/api/v1/profile/me", headers=h).json()
        == client.get("/api/v1/profile", headers=h).json()
    )
    listing = client.get("/api/v1/opportunities", headers=h, params={"search": "Python"})
    assert listing.status_code == 200
    assert listing.json()["data"][0]["id"] == oid
    assert (
        client.get("/api/v1/discovery/feed", headers=h).json()["data"][0]["opportunity_id"] == oid
    )


def test_external_eligibility_contract_remains_distinct(client, headers):
    h, other = headers(), headers()
    profile(client, h)
    oid = post_opportunity(client, h)
    result = client.post("/api/v1/eligibility/check/" + oid, headers=h)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["api_status"] == "ELIGIBLE"
    unknown = client.post("/api/v1/opportunities", headers=h, json={"title": "Unconfirmed"}).json()[
        "data"
    ]["id"]
    batch = client.post(
        "/api/v1/eligibility/batch", headers=h, json={"opportunity_ids": [oid, unknown]}
    ).json()["data"]
    assert batch[1]["api_status"] == "CANNOT_DETERMINE"
    assert (
        client.post("/api/v1/eligibility/check/" + oid, headers=other).json()["data"]["api_status"]
        == "POTENTIALLY_ELIGIBLE"
    )
    assert (
        client.post(
            "/api/v1/eligibility/batch", headers=h, json={"opportunity_ids": [oid] * 51}
        ).status_code
        == 422
    )


def test_calendar_contains_only_owner_applications(client, headers):
    h, other = headers(), headers()
    deadline = (date.today() + timedelta(days=20)).isoformat()
    oid = client.post(
        "/api/v1/opportunities", headers=h, json=dict(OPPORTUNITY, deadline=deadline)
    ).json()["data"]["id"]
    aid = client.post("/api/v1/applications", headers=h, json={"opportunity_id": oid}).json()[
        "data"
    ]["id"]
    result = client.get("/api/v1/calendar/deadlines", headers=h)
    assert result.status_code == 200, result.text
    assert result.json()["data"][0]["application_id"] == aid
    assert result.json()["data"][0]["deadline"] == deadline
    assert client.get("/api/v1/calendar/deadlines", headers=other).json()["data"] == []
    assert (
        client.get(
            "/api/v1/calendar/events",
            headers=h,
            params={"start": "2027-12-31", "end": "2027-01-01"},
        ).status_code
        == 422
    )


def test_resume_and_trust_chart_routes(client, headers):
    h, other = headers(), headers()
    oid = post_opportunity(client, h)
    result = client.post(
        "/api/v1/resume/upload",
        headers=h,
        files={"file": ("resume.pdf", pdf("Python developer"), "application/pdf")},
    )
    assert result.status_code == 202, result.text
    document_id = result.json()["data"]["document_id"]
    result = client.post(
        "/api/v1/resume/match/" + oid, headers=h, json={"document_id": document_id}
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["matched_required"] == ["python"]
    assert (
        client.post(
            "/api/v1/resume/match/" + oid, headers=other, json={"document_id": document_id}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/trust/verify/" + oid, headers=h).json()["data"]["verification_status"]
        == "UNKNOWN"
    )


def test_ci_tracks_backend_code_and_uses_relocated_pytest_suite():
    root = Path(__file__).resolve().parents[3]
    workflow = (root / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "backend-code" in workflow
    assert "working-directory: backend" in workflow
    assert "python -m pytest app/tests -q" in workflow
    assert "unittest discover" not in workflow
    assert "-s backend/tests" not in workflow
