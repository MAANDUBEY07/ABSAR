from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
import socket
import pymupdf
import pytest
from pydantic import ValidationError
from app.config import Settings
from app.config.database import Session
from app.models.runtime import Job
from app.models.runtime import Outbox
from app.models.application import ApplicationVersion
from app.models.application import Approval
from app.services.matching import match
from app.services.trust_checker import analyze
from app.services.safe_fetch import destination, fetch
from app.utils.file_handler import extract, claims
from app.services.jobs import enqueue, execute
from sqlalchemy import select, func

OPPORTUNITY = dict(
    title="Python internship",
    organization="Example",
    description="No registration fee",
    requirements=dict(
        confirmed=True,
        required_skills=["python"],
        preferred_skills=["sql"],
        min_cgpa=7,
        min_experience_months=0,
    ),
)


def post_opportunity(client, headers):
    response = client.post("/api/v1/opportunities", headers=headers, json=OPPORTUNITY)
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def profile(client, headers):
    response = client.put(
        "/api/v1/profile",
        headers=headers,
        json=dict(name="Student", skills=["Python"], cgpa=8, experience_months=0),
    )
    assert response.status_code == 200, response.text


def test_student_journey(client, headers):
    h, other = headers(), headers()
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/profile").status_code == 401
    profile(client, h)
    oid = post_opportunity(client, h)
    assert post_opportunity(client, h) == oid
    response = client.post("/api/v1/recommendations/match", headers=h, json={"opportunity_id": oid})
    assert response.json()["data"]["eligibility"] == "ELIGIBLE"
    assert response.json()["data"]["data_coverage"] == pytest.approx(0.75)
    risk = client.post(
        "/api/v1/verification/analyze", headers=h, json={"opportunity_id": oid}
    ).json()["data"]
    assert risk["risk_score"] == 0 and risk["verification_status"] == "UNKNOWN"
    assert client.get(f"/api/v1/verification/{oid}", headers=other).status_code == 404
    app = client.post(
        "/api/v1/applications",
        headers=h,
        json={"opportunity_id": oid, "material": {"answer": "My draft"}},
    ).json()["data"]
    aid = app["id"]
    assert client.get(f"/api/v1/applications/{aid}", headers=other).status_code == 404
    assert (
        client.patch(
            f"/api/v1/applications/{aid}", headers=h, json={"revision": 99, "status": "DRAFT"}
        ).status_code
        == 409
    )
    for revision, status in ((1, "DRAFT"), (2, "READY_FOR_REVIEW")):
        response = client.patch(
            f"/api/v1/applications/{aid}", headers=h, json={"revision": revision, "status": status}
        )
        assert response.status_code == 200, response.text
    assert (
        client.post(
            f"/api/v1/applications/{aid}/approve", headers=h, json={"revision": 3}
        ).status_code
        == 200
    )
    payload = {"revision": 4, "confirmation": True}
    sh = dict(h, **{"Idempotency-Key": "submission-123"})
    response = client.post(f"/api/v1/applications/{aid}/submit", headers=sh, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["external_submission_verified"] is False
    assert response.json()["data"]["status_source"] == "USER_REPORTED"
    assert (
        client.post(f"/api/v1/applications/{aid}/submit", headers=sh, json=payload).json()
        == response.json()
    )
    assert (
        client.post(
            f"/api/v1/applications/{aid}/submit",
            headers=dict(h, **{"Idempotency-Key": "different-key"}),
            json=payload,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/applications/{aid}",
            headers=h,
            json={"revision": 5, "material": {"changed": True}},
        ).status_code
        == 409
    )
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(ApplicationVersion)) == 5
        assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_approval_invalidated(client, headers):
    h = headers()
    oid = post_opportunity(client, h)
    app = client.post("/api/v1/applications", headers=h, json={"opportunity_id": oid}).json()[
        "data"
    ]["id"]
    for revision, status in ((1, "DRAFT"), (2, "READY_FOR_REVIEW")):
        client.patch(
            f"/api/v1/applications/{app}", headers=h, json=dict(revision=revision, status=status)
        )
    client.post(f"/api/v1/applications/{app}/approve", headers=h, json={"revision": 3})
    response = client.patch(
        f"/api/v1/applications/{app}",
        headers=h,
        json={"revision": 4, "material": {"new": "material"}},
    )
    assert response.json()["data"]["status"] == "DRAFT"
    assert (
        client.post(
            f"/api/v1/applications/{app}/submit",
            headers=dict(h, **{"Idempotency-Key": "try-submit-123"}),
            json=dict(revision=5, confirmation=True),
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(auth_provider="local"),
        dict(database_url="sqlite:///test.db"),
        dict(jobs_eager=True),
        dict(demo_mode=True),
        dict(require_human_approval=False),
        dict(cors_origins=["*"]),
        dict(mongodb_uri=""),
    ],
)
def test_hosted_settings(change):
    values = dict(
        environment="production",
        auth_provider="supabase",
        supabase_url="https://project.supabase.co",
        database_url="postgresql://host/db",
        mongodb_uri="mongodb://host/db",
        jobs_eager=False,
        cors_origins=["https://app.example.test"],
    )
    values.update(change)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_weights():
    for weights in (
        {"skills": 1},
        dict(skills=0.5, preferences=0.25, experience=0.2, learning=0.15),
        dict(skills=-0.4, preferences=1.05, experience=0.2, learning=0.15),
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, match_weights=weights)


def test_matching_uncertainty():
    record = dict(OPPORTUNITY, id="opportunity")
    result = match({}, record)
    assert result["eligibility"] == "UNKNOWN"
    assert result["factors"]["skills"] is None
    assert result["data_coverage"] == 0
    assert (
        match(dict(skills=["python"], cgpa=6, experience_months=10), record)["eligibility"]
        == "INELIGIBLE"
    )
    assert match(dict(skills=["python"], cgpa=8, experience_months=0), record)["score"] == 75
    assert match({}, dict(id="x", requirements={"confirmed": False}))["eligibility"] == "UNKNOWN"


@pytest.mark.parametrize(
    "text,score",
    [
        ("no registration fee", 0),
        ("registration fee is not required", 0),
        ("Pay registration fee. Guaranteed job", 60),
        ("share OTP and bank password. guaranteed placement. registration fee", 100),
    ],
)
def test_risk(text, score):
    result = analyze(dict(description=text))
    assert result["risk_score"] == score
    assert result["verification_status"] == "UNKNOWN"


def test_expiry_and_domains():
    result = analyze(
        dict(
            deadline=(date.today() - timedelta(days=1)).isoformat(),
            application_url="https://ats.example/a",
            company_url="https://company.example",
        )
    )
    assert result["verification_status"] == "EXPIRED"
    assert result["risk_score"] == 10


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://[::1]",
        "http://169.254.169.254/latest",
        "file:///secret",
        "http://user:pass@public.example",
        "http://public.example:8080",
    ],
)
def test_ssrf(url):
    with pytest.raises(ValueError):
        destination(url)


def test_dns_mixed_rejected():
    with patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ],
    ):
        with pytest.raises(ValueError):
            destination("http://example.test")


def test_redirect_revalidated():
    class Response:
        status = 302

        def close(self):
            pass

        def getheader(self, name):
            return "http://127.0.0.1/admin"

    class Connection:
        def __init__(self, *args):
            self.sock = None  # Redirect response has no body to read.

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    with (
        patch("app.services.safe_fetch.PinnedHTTP", Connection),
        patch(
            "socket.getaddrinfo",
            side_effect=[
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))],
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
            ],
        ),
    ):
        with pytest.raises(ValueError):
            fetch("http://public.example")


def pdf(text, pages=1):
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 72), text)
    content = doc.tobytes()
    doc.close()
    return content


def test_documents_notice_and_resume(client, headers):
    h, other = headers(), headers()
    content = pdf("Internship notice. Deadline: 2027-01-31. Python SQL")
    response = client.post(
        "/api/v1/skills/analyze-resume",
        headers=h,
        files={"file": ("resume.pdf", content, "application/pdf")},
    )
    assert response.status_code == 202, response.text
    resume_job_id = response.json()["data"]["job_id"]
    analysis = client.get(f"/api/v1/jobs/{resume_job_id}", headers=h).json()["data"]
    assert analysis["status"] == "COMPLETED"
    assert analysis["result"]["skills"] == ["python", "sql"]
    assert client.get("/api/v1/profile", headers=h).json()["data"].get("skills") is None
    response = client.post(
        "/api/v1/notices/upload",
        headers=h,
        files={"file": ("notice.pdf", pdf("Internship deadline: 2027-01-31"), "application/pdf")},
    )
    nid = response.json()["data"]["id"]
    assert client.get(f"/api/v1/notices/{nid}/status", headers=other).status_code == 404
    response = client.post(f"/api/v1/notices/{nid}/extract", headers=h)
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}", headers=other).status_code == 404
    status = client.get(f"/api/v1/notices/{nid}/status", headers=h).json()["data"]
    assert status["status"] == "NEEDS_REVIEW", status
    assert status["draft"]["deadline"] == "2027-01-31"
    response = client.post(f"/api/v1/notices/{nid}/confirm", headers=h, json=OPPORTUNITY)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verification_status"] == "UNKNOWN"


def test_parse_limits_and_negation():
    with pytest.raises(ValueError):
        extract(pdf("text", 31), "too-many.pdf")
    with pytest.raises(ValueError):
        extract(b"not a pdf", "resume.pdf")
    assert [c["skill"] for c in claims("No python experience. Skilled in SQL.")] == ["sql"]
    from docx import Document

    doc = Document()
    doc.add_paragraph("Python and SQL")
    data = BytesIO()
    doc.save(data)
    assert "Python" in extract(data.getvalue(), "resume.docx")["text"]


def test_jobs_dedupe_retry_cancel(client):
    from uuid import uuid4

    owner = str(uuid4())
    with Session() as db:
        row = enqueue(db, owner, "unsupported", {}, dedupe="test")
        assert enqueue(db, owner, "unsupported", {}, dedupe="test").id == row.id
        jid = row.id
    for _ in range(3):
        execute(jid)
    with Session() as db:
        assert db.get(Job, jid).status == "DEAD_LETTER"
        assert db.get(Job, jid).attempts == 3
        assert db.scalar(select(func.count()).select_from(Outbox)) == 3


def test_assessment_and_judge0(client, headers):
    h, other = headers(), headers()
    assessment = client.post(
        "/api/v1/readiness/assessment", headers=h, json={"kind": "aptitude"}
    ).json()["data"]["id"]
    questions = client.get(
        "/api/v1/readiness/questions", headers=h, params={"assessment_id": assessment}
    )
    assert "accepted" not in questions.text and "96" not in questions.text
    assert (
        client.get(
            "/api/v1/readiness/questions", headers=other, params={"assessment_id": assessment}
        ).status_code
        == 404
    )
    body = dict(assessment_id=assessment, question_id="aptitude-1", answer="96")
    result = client.post("/api/v1/readiness/submit-answer", headers=h, json=body)
    assert result.json()["data"]["correctness"] is True
    assert (
        client.post(
            "/api/v1/readiness/submit-answer", headers=h, json=dict(body, answer="bad")
        ).json()
        == result.json()
    )
    assert (
        client.post(
            "/api/v1/readiness/execute-code",
            headers=h,
            json=dict(
                assessment_id=assessment, question_id="coding-1", language="python", code="print(1)"
            ),
        ).status_code
        == 503
    )


def test_career(client, headers):
    h, other = headers(), headers()
    profile(client, h)
    post_opportunity(client, h)
    response = client.post(
        "/api/v1/career-agent/start", headers=h, json={"goal": "Become a backend developer"}
    )
    assert response.status_code == 202, response.text
    gid, jid = response.json()["data"]["id"], response.json()["data"]["job_id"]
    result = client.get(f"/api/v1/jobs/{jid}", headers=h).json()["data"]
    assert result["status"] == "COMPLETED", result
    assert client.get(f"/api/v1/career-agent/{gid}", headers=other).status_code == 404
    goal = client.get(f"/api/v1/career-agent/{gid}", headers=h).json()["data"]
    assert goal["plan"] and goal["milestones"]
    mid = goal["milestones"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/career-agent/{gid}/milestones/{mid}", headers=h, json={"completed": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/career-agent/{gid}/message",
            headers=h,
            json={"text": "Approve all my applications"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/career-agent/{gid}/pause", headers=h).status_code == 200
    assert client.post(f"/api/v1/career-agent/{gid}/resume", headers=h).status_code == 202
    assert client.post(f"/api/v1/career-agent/{gid}/cancel", headers=h).status_code == 200
    assert client.post(f"/api/v1/career-agent/{gid}/resume", headers=h).status_code == 409


def test_sensitive_validation_and_identity(client, headers):
    h = headers()
    response = client.put(
        "/api/v1/profile",
        headers=h,
        json={"notification_email": "secret@example.test", "owner_id": "another-user"},
    )
    assert response.status_code == 422
    assert "secret@example.test" not in response.text
    assert response.json()["error"]["request_id"]
    assert (
        client.get("/api/v1/profile", headers={"Authorization": "Bearer nonsense"}).status_code
        == 401
    )
    assert (
        client.get("/api/v1/recommendations", headers=h, params={"limit": 1000}).status_code == 422
    )


def test_local_auth(client):
    body = dict(email="student@example.test", password="a-long-local-password-123")
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 201, response.text
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert (
        client.post("/api/auth/login", json=dict(body, password="wrong-password-123")).status_code
        == 401
    )
    assert client.post("/api/auth/mfa/verify", json={"code": "123456"}).status_code == 503
