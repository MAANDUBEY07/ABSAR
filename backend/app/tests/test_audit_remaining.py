from datetime import date, timedelta
from io import BytesIO
import http.client

import pytest
from sqlalchemy import select

from app.config import settings
from app.config.database import Session
from app.models.application import Application
from app.models.runtime import Job, CareerGoal, CareerMilestone, Notification, LocalDocument
from app.repositories import documents
from app.services import jobs, career, safe_fetch
from app.services.matching import match
from app.services.notifications import reminders
from app.routes.operations import cancel
from app.routes.trust import verification


def owner_id(client, headers):
    h = headers()
    return h, client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]


def upload_notice(client, h):
    from PIL import Image

    image = BytesIO()
    Image.new("RGB", (5, 5)).save(image, "PNG")
    response = client.post(
        "/api/v1/notices/upload",
        headers=h,
        files={"file": ("notice.png", image.getvalue(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


@pytest.mark.parametrize("fast", [True, False])
def test_notice_completion_preserves_draft(client, headers, monkeypatch, fast):
    from app.routes import notices

    monkeypatch.setattr(jobs, "dispatch", lambda: None)
    h, owner = owner_id(client, headers)
    notice = upload_notice(client, h)
    monkeypatch.setattr(
        "app.utils.file_handler.extract",
        lambda *a, **k: {"text": "Campus internship", "warnings": []},
    )
    original = jobs.enqueue

    def enqueue(*a, **k):
        row = original(*a, **k)
        if fast:
            jobs.execute(row.id)
        return row

    monkeypatch.setattr(notices, "enqueue", enqueue)
    response = client.post(f"/api/v1/notices/{notice}/extract", headers=h)
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["job_id"]
    if not fast:
        assert documents.get("extracted_notices", notice, owner)["status"] == "PROCESSING"
        jobs.execute(job_id)
    final = documents.get("extracted_notices", notice, owner)
    assert final["status"] == "NEEDS_REVIEW"
    assert final["draft"]
    jobs.execute(job_id)
    with Session() as db:
        job = db.get(Job, job_id)
        assert job.status == "COMPLETED"
        assert job.attempts == 1
    # A delayed older execution must preserve review/confirmation data.
    jobs.perform("notice", {"document_id": notice}, owner)
    assert documents.get("extracted_notices", notice, owner) == final


def test_notice_failure_and_retries(client, headers, monkeypatch):
    monkeypatch.setattr(jobs, "dispatch", lambda: None)
    h, owner = owner_id(client, headers)
    notice = upload_notice(client, h)

    def fail(*a, **k):
        raise ValueError("private provider detail")

    monkeypatch.setattr("app.utils.file_handler.extract", fail)
    response = client.post(f"/api/v1/notices/{notice}/extract", headers=h)
    job_id = response.json()["data"]["job_id"]
    jobs.execute(job_id)
    assert documents.get("extracted_notices", notice, owner)["status"] == "RETRY"
    jobs.execute(job_id)
    jobs.execute(job_id)
    final = documents.get("extracted_notices", notice, owner)
    assert final["status"] == "FAILED"
    assert final["draft"] is None
    assert "private" not in final["error"]
    with Session() as db:
        assert db.get(Job, job_id).status == "DEAD_LETTER"


def test_notice_conditional_updates_preserve_completed_state(client):
    documents.put(
        "extracted_notices",
        "n",
        {"owner_id": "u", "status": "NEEDS_REVIEW", "draft": {"title": "kept"}},
    )
    assert not documents.transition(
        "extracted_notices", "n", "u", {"UPLOADED"}, {"status": "PROCESSING"}
    )
    assert not documents.transition(
        "extracted_notices", "n", "other", {"NEEDS_REVIEW"}, {"status": "FAILED"}
    )
    assert documents.get("extracted_notices", "n")["draft"] == {"title": "kept"}


@pytest.mark.parametrize("stage", ["profile", "provider"])
def test_career_execution_cancellation(client, headers, monkeypatch, stage):
    monkeypatch.setattr(jobs, "dispatch", lambda: None)
    h, owner = owner_id(client, headers)
    response = client.post(
        "/api/v1/career-agent/start", headers=h, json={"goal": "Become a software engineer"}
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    calls = []

    def do_cancel():
        with Session() as db:
            cancel(data["job_id"], owner, db)

    original = career.profile_node

    def profile(state):
        result = original(state)
        if stage == "profile":
            do_cancel()
        return result

    def suggest(*a):
        calls.append(1)
        do_cancel()
        return {"suggestions": [{"title": "Must not persist", "description": "cancelled"}]}

    monkeypatch.setattr(career, "profile_node", profile)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr("app.services.suggestions.suggest", suggest)
    jobs.execute(data["job_id"])
    assert len(calls) == (0 if stage == "profile" else 1)
    with Session() as db:
        assert db.get(Job, data["job_id"]).status == "CANCELLED"
        assert not list(db.scalars(select(CareerMilestone)))
        assert not db.get(CareerGoal, data["id"]).payload.get("plan")


@pytest.mark.parametrize("version", ["HTTP/1.0", "HTTP/1.1"])
def test_connection_close_feed_body(monkeypatch, version):
    class Transport:
        def settimeout(self, value):
            assert value > 0

        def makefile(self, *a):
            return BytesIO(
                (
                    version + " 200 OK\r\nConnection: close\r\nContent-Length: 6\r\n\r\n<rss/>"
                ).encode()
            )

        def close(self):
            pass

    class Connection(http.client.HTTPConnection):
        def __init__(self, *a):
            super().__init__("feed.test")
            self.sock = Transport()

        def request(self, *a, **k):
            self._HTTPConnection__state = http.client._CS_REQ_SENT

    monkeypatch.setattr(safe_fetch, "PinnedHTTP", Connection)
    monkeypatch.setattr(
        safe_fetch,
        "destination",
        lambda url: (__import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(url), 80, None),
    )
    assert safe_fetch.fetch("http://feed.test") == b"<rss/>"


@pytest.mark.parametrize(
    "deadline,status,expected",
    [
        (None, "UNKNOWN", True),
        (0, "UNKNOWN", True),
        (1, "UNKNOWN", True),
        (-1, "UNKNOWN", False),
        (None, "EXPIRED", False),
    ],
)
def test_expired_recommendations_and_drafts(client, deadline, status, expected, monkeypatch):
    item = {
        "id": "o",
        "requirements": {"confirmed": True},
        "verification_status": status,
        "deadline": None
        if deadline is None
        else (date.today() + timedelta(days=deadline)).isoformat(),
    }
    result = match({}, item)
    assert result["eligibility"] == "ELIGIBLE"
    assert result["recommendable"] is expected
    monkeypatch.setattr(career, "stopped", lambda state: False)
    drafts = career.draft_node({"candidates": [{"id": "o", "matching": result}], "profile": {}})
    assert bool(drafts["draft_preparation"]) is expected


@pytest.mark.parametrize("terminal", ["COMPLETED", "DEAD_LETTER", "CANCELLED"])
def test_discovery_refresh_releases_only_terminal_key(client, terminal):
    with Session() as db:
        first = jobs.enqueue(db, "owner", "discovery", {"feed_url": "https://feed.test"})
        first_id = first.id
        assert (
            jobs.enqueue(db, "owner", "discovery", {"feed_url": "https://feed.test"}).id == first_id
        )
        first.status = terminal
        db.commit()
        second = jobs.enqueue(db, "owner", "discovery", {"feed_url": "https://feed.test"})
        assert second.id != first_id
        assert (
            jobs.enqueue(db, "owner", "discovery", {"feed_url": "https://feed.test"}).id
            == second.id
        )
        assert db.get(Job, first_id).status == terminal


def test_verification_filters_before_limit_and_sorts(client):
    with Session.begin() as db:
        db.add_all(
            [
                LocalDocument(
                    collection="verification_results",
                    id=f"a{i:04}",
                    payload={"owner_id": "owner", "opportunity_id": "other"},
                )
                for i in range(501)
            ]
        )
        db.add_all(
            [
                LocalDocument(
                    collection="verification_results",
                    id=f"z{i:04}",
                    payload={
                        "id": f"z{i:04}",
                        "owner_id": "owner",
                        "opportunity_id": "target",
                        "analyzed_at": f"2026-11-15T00:{i // 60:02}:{i % 60:02}",
                    },
                )
                for i in range(502)
            ]
        )
        db.add(
            LocalDocument(
                collection="verification_results",
                id="private",
                payload={"owner_id": "other", "opportunity_id": "target", "analyzed_at": "2099"},
            )
        )
    rows = documents.verification_history("owner", "target")
    assert len(rows) == 501
    assert rows[0]["id"] == "z0501"
    assert all(row["owner_id"] == "owner" and row["opportunity_id"] == "target" for row in rows)
    assert verification("target", "owner")["data"]["id"] == "z0501"


def test_reminders_advance_beyond_first_hundred(client):
    with Session.begin() as db:
        db.add_all(
            [
                Application(
                    id=f"a{i:04}",
                    owner_id="owner",
                    opportunity_id=f"o{i}",
                    status="SAVED",
                    payload={},
                )
                for i in range(205)
            ]
        )
        db.add(
            Application(
                id="submitted",
                owner_id="owner",
                opportunity_id="submitted",
                status="SUBMITTED",
                payload={},
            )
        )
    reminders()
    reminders()
    with Session() as db:
        rows = list(db.scalars(select(Notification)))
        assert len(rows) == 205
        assert {row.payload["application_id"] for row in rows} == {f"a{i:04}" for i in range(205)}


def test_recommendation_endpoint_excludes_expired(client, headers):
    h, owner = owner_id(client, headers)
    assert client.put("/api/v1/profile", headers=h, json={"name": "Student"}).status_code == 200
    for key, deadline in [
        ("expired", (date.today() - timedelta(days=1)).isoformat()),
        ("undated", None),
    ]:
        documents.put(
            "opportunities",
            key,
            {"id": key, "deadline": deadline, "requirements": {"confirmed": True}},
        )
    result = client.get("/api/v1/recommendations", headers=h)
    assert result.status_code == 200, result.text
    assert [item["opportunity_id"] for item in result.json()["data"]] == ["undated"]


def test_notice_retry_recovers_and_clears_error(client, headers, monkeypatch):
    monkeypatch.setattr(jobs, "dispatch", lambda: None)
    h, owner = owner_id(client, headers)
    notice = upload_notice(client, h)

    def fail(*a, **k):
        raise ValueError("failed")

    monkeypatch.setattr("app.utils.file_handler.extract", fail)
    job_id = client.post(f"/api/v1/notices/{notice}/extract", headers=h).json()["data"]["job_id"]
    jobs.execute(job_id)
    monkeypatch.setattr(
        "app.utils.file_handler.extract",
        lambda *a, **k: {"text": "Recovered internship", "warnings": []},
    )
    jobs.execute(job_id)
    final = documents.get("extracted_notices", notice, owner)
    assert final["status"] == "NEEDS_REVIEW" and final["draft"]
    assert final["error"] is None
    with Session() as db:
        assert db.get(Job, job_id).status == "COMPLETED"


def test_discovery_refresh_fetches_new_content(client, headers, monkeypatch):
    h, owner = owner_id(client, headers)
    feed = "https://public.example.test/feed"
    monkeypatch.setattr(settings, "discovery_feeds", [feed])
    calls = []

    def fetch(url):
        calls.append(url)
        return f"<rss><channel><item><title>Opportunity {len(calls)}</title><link>https://public.example.test/{len(calls)}</link></item></channel></rss>".encode()

    monkeypatch.setattr(safe_fetch, "fetch", fetch)
    ids = [
        client.post("/api/v1/discovery/jobs", headers=h, json={"feed_url": feed}).json()["data"][
            "job_id"
        ]
        for _ in range(2)
    ]
    assert ids[0] != ids[1]
    assert len(calls) == 2
    with Session() as db:
        assert all(db.get(Job, key).status == "COMPLETED" for key in ids)


@pytest.mark.parametrize("refresh", [False, True])
def test_concurrent_discovery_enqueue_shares_active_job(client, refresh):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if refresh:
        with Session() as db:
            old = jobs.enqueue(db, "concurrent", "discovery", {"feed_url": "https://feed.test"})
            old.status = "COMPLETED"
            db.commit()
    gate = Barrier(2)

    def enqueue(_):
        with Session() as db:
            gate.wait(timeout=5)
            return jobs.enqueue(db, "concurrent", "discovery", {"feed_url": "https://feed.test"}).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(enqueue, range(2)))
    assert len(set(ids)) == 1


def test_connection_close_real_socket_ownership(monkeypatch):
    import socket
    from urllib.parse import urlsplit

    reader, writer = socket.socketpair()
    writer.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 6\r\n\r\n<rss/>")
    writer.close()

    class Connection(http.client.HTTPConnection):
        def __init__(self, *a):
            super().__init__("feed.test")
            self.sock = reader

        def request(self, *a, **k):
            self._HTTPConnection__state = http.client._CS_REQ_SENT

    monkeypatch.setattr(safe_fetch, "PinnedHTTP", Connection)
    monkeypatch.setattr(safe_fetch, "destination", lambda url: (urlsplit(url), 80, None))
    try:
        assert safe_fetch.fetch("http://feed.test") == b"<rss/>"
        assert reader.fileno() == -1
    finally:
        reader.close()
