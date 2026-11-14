from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import zipfile
import pytest
from sqlalchemy import select
from app.config import settings
from app.config.database import Session
from app.models.runtime import Job
from app.models.runtime import Outbox
from app.models.base import now
from app.services.jobs import enqueue, execute, dispatch, recover
from app.utils.file_handler import extract
from app.services.observability import strip_sensitive


def test_cancelled_job_not_executed(client, headers):
    h = headers()
    response = client.get("/api/v1/auth/me", headers=h)
    owner = response.json()["data"]["id"]
    with Session() as db:
        job = enqueue(db, owner, "unsupported", {})
        job_id = job.id
    assert (
        client.post(f"/api/v1/jobs/{job_id}/cancel", headers=h).json()["data"]["status"]
        == "CANCELLED"
    )
    execute(job_id)
    with Session() as db:
        assert db.get(Job, job_id).attempts == 0


def test_stale_lease_recovery(client):
    with Session() as db:
        job = enqueue(db, str(uuid4()), "unsupported", {})
        job.status = "RUNNING"
        job.lease_until = now() - timedelta(minutes=1)
        job.attempts = 1
        db.commit()
        job_id = job.id
    recover()
    with Session() as db:
        assert db.get(Job, job_id).status == "RETRY"
        assert len(list(db.scalars(select(Outbox)))) == 2


def test_delivery_failure_keeps_outbox(client, monkeypatch):
    monkeypatch.setattr(settings, "jobs_eager", False)
    with Session() as db:
        enqueue(db, str(uuid4()), "unsupported", {})
    with patch("app.worker.execute_job.delay", side_effect=RuntimeError("broker unavailable")):
        with pytest.raises(RuntimeError):
            dispatch()
    with Session() as db:
        assert db.scalar(select(Outbox)).status == "PENDING"


def test_archive_expansion_limits():
    data = BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "a" * (20 * 1024 * 1024 + 1))
    with pytest.raises(ValueError):
        extract(data.getvalue(), "bomb.docx")


def test_image_limit_and_mocked_ocr():
    from PIL import Image

    data = BytesIO()
    Image.new("RGB", (16, 16)).save(data, "PNG")
    with patch(
        "app.utils.file_handler.pytesseract.image_to_string", return_value="Campus internship"
    ):
        assert extract(data.getvalue(), "notice.png")["text"] == "Campus internship"
    with patch("app.utils.file_handler.Image.open") as image:
        image.return_value.__enter__.return_value = type(
            "Image", (), dict(format="PNG", width=4001, height=4000)
        )()
        with pytest.raises(ValueError):
            extract(data.getvalue(), "notice.png")


def test_sentry_redaction():
    event = strip_sensitive(
        dict(
            request={"data": "secret"},
            user={"email": "private"},
            message="token",
            exception={},
            contexts={},
            event_id="safe",
        ),
        None,
    )
    assert event == {"event_id": "safe"}


def test_dependency_manifest_contract():
    import importlib.util

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "validate", root / "backend/scripts/validate_dependencies.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate(root / "backend") > 20


def test_optional_deployment_contract():
    import yaml

    root = Path(__file__).resolve().parents[3]
    if not (root / "render.yaml").exists():
        pytest.skip("Root deployment configuration is outside the backend-only branch scope")
    render = yaml.safe_load((root / "render.yaml").read_text())
    services = render["services"]
    assert [s["name"] for s in services] == [
        "opportunityos-api",
        "opportunityos-worker",
        "opportunityos-scheduler",
    ]
    for service in services:
        assert service["branch"] == "main"
        assert service["autoDeployTrigger"] == "checksPass"
        assert {"fromGroup": "opportunityos-backend"} in service["envVars"]
        assert {"key": "JOBS_EAGER", "value": "false"} in service["envVars"]
    assert services[2]["numInstances"] == 1
    for path in ["tests.yml", "release.yml"]:
        workflow = root / ".github/workflows" / path
        if not workflow.exists():
            continue
        text = workflow.read_text()
        assert "configure-aws-credentials" not in text and "id-token: write" not in text


def test_hosted_rate_limit_fails_closed(client, monkeypatch):
    from app.main import redis

    monkeypatch.setattr(settings, "environment", "production")
    with patch.object(redis, "eval", side_effect=RuntimeError("private broker credential")):
        response = client.get("/api/v1/auth/config", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 503
    assert "private broker credential" not in response.text
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_legacy_disabled_in_hosted_mode(client, monkeypatch):
    from app.main import redis

    monkeypatch.setattr(settings, "environment", "production")
    with patch.object(redis, "eval", return_value=1):
        response = client.post(
            "/api/auth/signup",
            json={"email": "student@example.test", "password": "a-local-password-123"},
        )
    assert response.status_code == 503
    assert "Legacy routes" in response.text
