"""Mock Member 1 at adapter boundaries while preserving their source implementations."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import sys
import pytest
from sqlalchemy import select
from app.config import settings
from app.config.database import Session
from app.models.runtime import Job
from app.integrations import member1
from app.services import jobs
from app.tests.test_persistent import post_opportunity, pdf


def trust_result():
    return dict(
        risk_score=0,
        risk_level="NO_SIGNALS_DETECTED",
        verification_status="UNKNOWN",
        evidence=[],
        disclaimer="Member-owned result",
    )


def test_trust_route_uses_adapter_and_preserves_envelope(client, headers):
    h = headers()
    oid = post_opportunity(client, h)
    source = trust_result()
    with patch("app.services.trust_checker.analyze", return_value=source) as provider:
        response = client.post(
            "/api/v1/verification/analyze", headers=h, json={"opportunity_id": oid}
        )
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"data", "meta"}
    assert response.json()["data"]["disclaimer"] == "Member-owned result"
    assert response.json()["data"]["verification_status"] == "UNKNOWN"
    assert "owner_id" not in source
    provider.assert_called_once()


def test_resume_jobs_call_member1_adapter(client, headers):
    h = headers()
    owner = client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]

    def analyze(text, provided_owner, document_id):
        assert "Python" in text and provided_owner == owner
        return dict(
            owner_id=provided_owner,
            document_id=document_id,
            skills=["python"],
            evidence=[
                dict(
                    skill="python",
                    quote="Python",
                    start=text.index("Python"),
                    end=text.index("Python") + 6,
                    source="RESUME_CLAIM",
                )
            ],
            disclaimer="Member-owned mock",
        )

    with patch("app.services.resume_analyzer.analyze_resume", side_effect=analyze) as provider:
        response = client.post(
            "/api/v1/skills/analyze-resume",
            headers=h,
            files={"file": ("cv.pdf", pdf("Python skills"), "application/pdf")},
        )
    assert response.status_code == 202, response.text
    job = client.get("/api/v1/jobs/" + response.json()["data"]["job_id"], headers=h).json()["data"]
    assert job["status"] == "COMPLETED"
    assert job["result"]["disclaimer"] == "Member-owned mock"
    provider.assert_called_once()


def test_adapter_rejects_cross_owner_resume_output():
    owner, document = str(uuid4()), str(uuid4())
    result = dict(
        owner_id=str(uuid4()), document_id=document, skills=[], evidence=[], disclaimer="Mock"
    )
    with (
        patch("app.services.resume_analyzer.analyze_resume", return_value=result),
        pytest.raises(member1.AIServiceUnavailable),
    ):
        member1.analyze_resume("claims", owner, document)


def test_missing_interface_fails_explicitly_without_fake_ai():
    with (
        patch("app.integrations.member1.import_module", return_value=SimpleNamespace()),
        pytest.raises(member1.AIServiceUnavailable),
    ):
        member1.discover_feed("https://configured.example/rss", str(uuid4()))


def test_provider_errors_are_redacted():
    with patch(
        "app.services.trust_checker.analyze",
        side_effect=RuntimeError("PRIVATE_PROVIDER_CREDENTIAL"),
    ):
        with pytest.raises(member1.AIServiceUnavailable) as error:
            member1.analyze_trust({"title": "Example"})
    assert "PRIVATE_PROVIDER_CREDENTIAL" not in str(error.value)
    assert error.value.__suppress_context__


def test_existing_notice_and_duplicate_interfaces_are_delegated():
    parsed = SimpleNamespace(text="Source notice")
    extracted = SimpleNamespace(title="Source title")
    duplicate = SimpleNamespace(is_duplicate=True)
    with patch("app.services.notice_parser.parse_pdf", return_value=parsed) as parser:
        assert member1.parse_notice(b"source bytes") is parsed
        parser.assert_called_once_with(b"source bytes")
    with patch(
        "app.services.ai_extractor.extract_opportunity", return_value=extracted
    ) as extractor:
        assert member1.extract_notice("notice", source_url="https://example.test") is extracted
        extractor.assert_called_once_with("notice", source_url="https://example.test")
    with patch(
        "app.services.duplicate_detector.compare_opportunities", return_value=duplicate
    ) as detector:
        assert member1.compare_opportunities({"title": "a"}, {"title": "b"}) is duplicate
        detector.assert_called_once_with({"title": "a"}, {"title": "b"}, None)


def test_eager_local_jobs_do_not_import_celery_worker(client):
    assert settings.jobs_eager
    with Session() as db:
        job = jobs.enqueue(db, str(uuid4()), "adapter-test", {})
        job_id = job.id
    with (
        patch.dict(sys.modules, {"app.worker": None}),
        patch("app.services.jobs.perform", return_value={"ok": True}),
    ):
        jobs.dispatch()
    with Session() as db:
        result = db.scalar(select(Job).where(Job.id == job_id))
        assert result.status == "COMPLETED"
        assert result.payload["result"] == {"ok": True}
