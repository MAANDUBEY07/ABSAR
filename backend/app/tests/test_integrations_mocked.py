from types import SimpleNamespace
from unittest.mock import patch
import pytest
from sqlalchemy import select, func
from app.config import settings
from app.config.database import Session
from app.models.runtime import Notification
from app.repositories import documents
from app.services.jobs import perform
from app.services.ai_extractor import _sanitize_error_message, ExtractedOpportunity
from app.services.suggestions import suggest
from app.services.notifications import reminders
from app.tests.test_persistent import post_opportunity


def test_rss_connector(client, headers, monkeypatch):
    h = headers()
    feed = "https://public.example.test/feed"
    monkeypatch.setattr(settings, "discovery_feeds", [feed])
    xml = b"<rss><channel><item><title>Scholarship notice</title><link>https://public.example.test/apply</link><description>Source facts only</description></item></channel></rss>"
    with patch("app.services.safe_fetch.fetch", return_value=xml):
        result = client.post("/api/v1/discovery/jobs", headers=h, json={"feed_url": feed})
    assert result.status_code == 202
    job = client.get("/api/v1/jobs/" + result.json()["data"]["job_id"], headers=h).json()["data"]
    assert job["status"] == "COMPLETED"
    assert len(job["result"]["opportunity_ids"]) == 1
    opportunity = documents.get("opportunities", job["result"]["opportunity_ids"][0])
    assert opportunity["organization"] is None and opportunity["deadline"] is None
    assert opportunity["requirements"]["confirmed"] is False
    assert (
        client.post(
            "/api/v1/discovery/jobs",
            headers=h,
            json={"feed_url": "https://unconfigured.example/feed"},
        ).status_code
        == 422
    )


def test_xml_entities_rejected(client):
    from defusedxml.common import DefusedXmlException
    from uuid import uuid4

    malicious = b'<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///private">]><rss>&xxe;</rss>'
    with (
        patch("app.services.safe_fetch.fetch", return_value=malicious),
        pytest.raises(DefusedXmlException),
    ):
        perform("discovery", {"feed_url": "https://public.example/feed"}, str(uuid4()))


def test_gemini_structured_output_and_sanitized_errors(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "private-provider-key")
    monkeypatch.setattr(settings, "gemini_model", "operator-selected-model")
    usage = SimpleNamespace(prompt_token_count=12, candidates_token_count=7)
    response = SimpleNamespace(
        parsed={"suggestions": [{"title": "Practice SQL", "description": "Build a query project"}]},
        usage_metadata=usage,
    )
    with patch("app.services.ai_extractor.get_gemini_client") as factory:
        factory.return_value.models.generate_content.return_value = response
        result = suggest("Learn backend", ["sql"])
        assert result["token_usage"] == {"input": 12, "output": 7}
        assert result["monetary_cost"] is None
        response.parsed = {
            "suggestions": [{"title": "bad", "description": "x", "change_eligibility": True}]
        }
        with pytest.raises(RuntimeError) as error:
            suggest("Learn", [])
        assert "private-provider-key" not in str(error.value)
        factory.return_value.models.generate_content.side_effect = RuntimeError(
            "private-provider-key: provider request failed"
        )
        with pytest.raises(RuntimeError) as error:
            suggest("Learn", [])
        assert "private-provider-key" not in str(error.value)
    assert "private-provider-key" not in _sanitize_error_message(
        RuntimeError("private-provider-key"), "private-provider-key", "model"
    )
    with pytest.raises(ValueError):
        ExtractedOpportunity(category="fabricated-category")


def test_notifications_use_signed_email_and_dedupe(client, headers, monkeypatch):
    h = headers()
    oid = post_opportunity(client, h)
    client.post("/api/v1/applications", headers=h, json={"opportunity_id": oid})
    response = client.patch(
        "/api/v1/notifications/preferences",
        headers=h,
        json=dict(timezone="UTC", quiet_start=0, quiet_end=0, channels=["in_app", "email"]),
    )
    assert response.status_code == 200
    assert (
        client.patch(
            "/api/v1/notifications/preferences", headers=h, json=dict(timezone="Invented/Zone")
        ).status_code
        == 422
    )
    monkeypatch.setattr(settings, "resend_api_key", "server-secret")
    monkeypatch.setattr(settings, "resend_from", "notices@example.test")
    with patch(
        "app.services.notifications.httpx.post", return_value=SimpleNamespace(is_success=True)
    ) as send:
        reminders()
        reminders()
        assert send.call_count == 1
        assert send.call_args.kwargs["json"]["to"] == ["student@example.test"]
        assert send.call_args.kwargs["headers"]["Idempotency-Key"]
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Notification)) == 1


def test_judge0_mocked_isolation(client, headers, monkeypatch):
    h = headers()
    monkeypatch.setattr(settings, "judge0_isolation_confirmed", True)
    monkeypatch.setattr(settings, "judge0_url", "https://judge.example.test")
    monkeypatch.setattr(settings, "judge0_language_ids", {"python": 71})
    aid = client.post("/api/v1/readiness/assessment", headers=h, json={"kind": "coding"}).json()[
        "data"
    ]["id"]

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Judge:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, path, **kwargs):
            assert kwargs["json"]["enable_network"] is False
            assert kwargs["json"]["cpu_time_limit"] == 2
            assert "expected_output" in kwargs["json"]
            return Response({"token": "server-token"})

        def get(self, path, **kwargs):
            return Response({"status": {"id": 3}})

    with patch("app.services.judge0.httpx.Client", Judge):
        result = client.post(
            "/api/v1/readiness/execute-code",
            headers=h,
            json=dict(
                assessment_id=aid,
                question_id="coding-1",
                language="python",
                code="user code is sent only to Judge0",
            ),
        )
    assert result.status_code == 202
    job = client.get("/api/v1/jobs/" + result.json()["data"]["job_id"], headers=h).json()["data"]
    assert job["status"] == "COMPLETED"
    assert "expected_output" not in str(job) and "user code" not in str(job)
    assert job["result"]["correctness"] is True


def test_standalone_gemini_suppresses_provider_cause(monkeypatch):
    from app.services.ai_extractor import extract_opportunity

    monkeypatch.setenv("GEMINI_API_KEY", "private-extractor-key")
    monkeypatch.setenv("GEMINI_MODEL", "operator-selected-model")
    with patch(
        "app.services.ai_extractor.get_gemini_client",
        side_effect=RuntimeError("private-extractor-key provider details"),
    ):
        with pytest.raises(RuntimeError) as error:
            extract_opportunity("A user supplied campus notice")
    assert "private-extractor-key" not in str(error.value)
    assert error.value.__suppress_context__ is True
