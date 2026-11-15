"""Mocked Supabase-to-student journey; no cloud credentials, Redis or provider calls."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from app.config import settings
from app.config.database import Session
from app.models.application import Application, Approval
from app.models.profile import Profile
from app.tests.test_persistent import post_opportunity


def test_supabase_profile_catalog_application_and_calendar_integration(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://team-project.supabase.co")
    private = ec.generate_private_key(ec.SECP256R1())
    instant = datetime.now(timezone.utc)
    owner, other = str(uuid4()), str(uuid4())

    def headers(subject):
        claims = dict(
            sub=subject,
            iss="https://team-project.supabase.co/auth/v1",
            aud="authenticated",
            role="authenticated",
            iat=instant,
            exp=instant + timedelta(minutes=10),
            email="signed@example.test",
        )
        token = jwt.encode(claims, private, algorithm="ES256", headers={"kid": "team-key"})
        return {"Authorization": "Bearer " + token}

    h, other_h = headers(owner), headers(other)
    jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    with patch("app.utils.auth.jwks_client", return_value=jwks) as provider:
        profile = client.put(
            "/api/v1/profile/me",
            headers=h,
            json=dict(
                name="Student",
                dob="2004-01-01",
                gender="Female",
                category="SC",
                domicile_state="Bihar",
                annual_income=180000,
                skills=["Python"],
                education={"highest_degree": "BTech", "percentage": 82},
            ),
        )
        assert profile.status_code == 200, profile.text
        assert profile.json()["data"]["id"] == owner
        assert profile.json()["data"]["email"] == "signed@example.test"
        deadline = (date.today() + timedelta(days=30)).isoformat()
        listing = client.post(
            "/api/v1/opportunities",
            headers=h,
            json=dict(
                title="Research opening",
                category="research",
                opportunity_mode="hybrid",
                category_metadata={"source_note": "User supplied"},
                deadline=deadline,
                requirements={"confirmed": True, "required_skills": ["python"]},
            ),
        )
        assert listing.status_code == 201, listing.text
        oid = listing.json()["data"]["id"]
        assert (
            client.get("/api/v1/opportunities/" + oid, headers=h).json()["data"]["category"]
            == "research"
        )
        assessment = client.post("/api/v1/eligibility/check/" + oid, headers=h).json()["data"]
        assert assessment["api_status"] == "ELIGIBLE"
        app = client.post(
            "/api/v1/applications",
            headers=h,
            json={"opportunity_id": oid, "material": {"answer": "Student claim"}},
        ).json()["data"]
        aid = app["id"]
        for revision, status in [(1, "DRAFT"), (2, "READY_FOR_REVIEW")]:
            result = client.patch(
                "/api/v1/applications/" + aid,
                headers=h,
                json=dict(revision=revision, status=status),
            )
            assert result.status_code == 200, result.text
        assert (
            client.post(
                "/api/v1/applications/" + aid + "/approve", headers=h, json={"revision": 3}
            ).status_code
            == 200
        )
        submit_h = dict(h, **{"Idempotency-Key": "member2-integration-001"})
        body = dict(revision=4, confirmation=True)
        receipt = client.post(
            "/api/v1/applications/" + aid + "/submit", headers=submit_h, json=body
        )
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["data"]["status_source"] == "USER_REPORTED"
        assert receipt.json()["data"]["external_submission_verified"] is False
        assert (
            client.post(
                "/api/v1/applications/" + aid + "/submit", headers=submit_h, json=body
            ).json()
            == receipt.json()
        )
        assert client.get("/api/v1/applications/" + aid, headers=other_h).status_code == 404
        events = client.get("/api/v1/calendar/deadlines", headers=h).json()["data"]
        assert events[0]["deadline"] == deadline and events[0]["application_id"] == aid
        assert client.get("/api/v1/calendar/deadlines", headers=other_h).json()["data"] == []
        assert set(profile.json()) == set(listing.json()) == set(receipt.json()) == {"data", "meta"}
        assert all(
            call.args == ("https://team-project.supabase.co/auth/v1/.well-known/jwks.json",)
            for call in provider.call_args_list
        )
    with Session() as db:
        assert db.get(Application, aid).status == "SUBMITTED"
        assert (
            db.scalar(select(Profile).where(Profile.owner_id == owner)).payload["annual_income"]
            == 180000
        )
        assert db.scalar(select(Approval).where(Approval.owner_id == owner)) is not None


def test_discovery_adapter_accepts_a_mock_service_without_redis(client, headers, monkeypatch):
    h = headers()
    owner = client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]
    oid = post_opportunity(client, h)
    feed = "https://configured.example/rss"
    monkeypatch.setattr(settings, "discovery_feeds", [feed])
    source = dict(owner_id=owner, opportunity_ids=[oid], connector="MOCK_MEMBER1")
    with patch("app.services.scraper.discover_feed", return_value=source) as provider:
        response = client.post("/api/v1/discovery/jobs", headers=h, json={"feed_url": feed})
    assert response.status_code == 202, response.text
    result = client.get("/api/v1/jobs/" + response.json()["data"]["job_id"], headers=h).json()[
        "data"
    ]
    assert result["status"] == "COMPLETED"
    assert result["result"]["opportunity_ids"] == [oid]
    provider.assert_called_once_with(feed, owner)
