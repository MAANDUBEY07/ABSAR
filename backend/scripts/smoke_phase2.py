"""Real localhost HTTP smoke; private temporary database and owned child process only."""

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import httpx
import pymupdf


def run():
    backend = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="avsar-phase2-http-") as folder:
        root = Path(folder).resolve()
        env = dict(
            os.environ,
            ENVIRONMENT="test",
            AUTH_PROVIDER="local",
            AI_PROVIDER="deterministic",
            JOBS_EAGER="true",
            MONGODB_URI="",
            DATABASE_URL="sqlite:///" + str(root / "db.sqlite"),
            CAREER_CHECKPOINT_DB=str(root / "checkpoints.sqlite"),
            JWT_SECRET=secrets.token_urlsafe(48),
            RATE_LIMIT_PER_MINUTE="10000",
            CORS_ORIGINS='["http://localhost:3000"]',
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            cwd=backend,
            env=env,
            check=True,
            capture_output=True,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        os.environ.update(env)
        sys.path.insert(0, str(backend))
        import threading
        import uvicorn
        from main import app
        from app.config.database import engine

        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if not thread.is_alive():
                        raise RuntimeError("Backend exited during startup")
                    time.sleep(0.1)
                assert client.get("/ready").status_code == 200
                preflight = client.options(
                    "/api/v1/profile",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "GET",
                        "Access-Control-Request-Headers": "Authorization",
                    },
                )
                assert (
                    preflight.headers.get("access-control-allow-origin") == "http://localhost:3000"
                )
                assert client.get("/api/v1/profile").status_code == 401
                password = secrets.token_urlsafe(24)
                signup = client.post(
                    "/api/auth/signup",
                    json={"email": "phase2@example.invalid", "password": password},
                )
                assert signup.status_code == 201
                headers = {"Authorization": "Bearer " + signup.json()["access_token"]}

                def call(method, path, body=None, extra=None):
                    response = client.request(
                        method, "/api/v1" + path, json=body, headers=dict(headers, **(extra or {}))
                    )
                    assert response.is_success, (path, response.status_code, response.text)
                    return response.json()["data"]

                call(
                    "PUT",
                    "/profile",
                    {
                        "name": "Integration fixture",
                        "cgpa": 8,
                        "skills": ["Python"],
                        "annual_income": 200000,
                    },
                )
                item = call(
                    "POST",
                    "/opportunities",
                    {
                        "title": "HTTP integration fixture",
                        "category": "grant",
                        "deadline": "2040-01-01",
                        "opportunity_mode": "hybrid",
                        "requirements": {
                            "confirmed": True,
                            "min_cgpa": 7,
                            "max_annual_income": 250000,
                        },
                    },
                )
                oid = item["id"]
                assert (
                    call("POST", "/recommendations/match", {"opportunity_id": oid})["eligibility"]
                    == "ELIGIBLE"
                )
                assert call("POST", "/eligibility/check/" + oid)["api_status"] == "ELIGIBLE"
                assert client.get("/api/v1/trust/verify/" + oid, headers=headers).status_code == 404
                call("POST", "/verification/analyze", {"opportunity_id": oid})
                call("GET", "/trust/verify/" + oid)
                application = call("POST", "/applications", {"opportunity_id": oid})
                aid = application["id"]
                for status in ["DRAFT", "READY_FOR_REVIEW"]:
                    application = call(
                        "PATCH",
                        "/applications/" + aid,
                        {"revision": application["revision"], "status": status},
                    )
                application = call(
                    "POST",
                    "/applications/" + aid + "/approve",
                    {"revision": application["revision"]},
                )
                body = {"revision": application["revision"], "confirmation": True}
                extra = {"Idempotency-Key": secrets.token_urlsafe(20)}
                receipt = call("POST", "/applications/" + aid + "/submit", body, extra)
                assert call("POST", "/applications/" + aid + "/submit", body, extra) == receipt
                assert receipt["external_submission_verified"] is False
                assert call("GET", "/calendar/deadlines")[0]["opportunity_id"] == oid
                with pymupdf.open() as pdf:
                    page = pdf.new_page()
                    page.insert_text((72, 72), "Python SQL. B.Tech. 2 years experience.")
                    content = pdf.tobytes()
                accepted = client.post(
                    "/api/v1/resume/upload",
                    headers=headers,
                    files={"file": ("cv.pdf", content, "application/pdf")},
                )
                assert accepted.status_code == 202
                job_id = accepted.json()["data"]["job_id"]
                for _ in range(100):
                    result = call("GET", "/jobs/" + job_id + "/result")
                    if result["status"] == "COMPLETED":
                        break
                    time.sleep(0.1)
                assert result["status"] == "COMPLETED", result
                assert "python" in result["result"]["parsed_skills"]
                assert result["result"]["experience_years"] == 2
                print(
                    "PASS: real HTTP startup/readiness/CORS/local auth/profile/catalog/eligibility/trust/application approval/idempotent submission/calendar/resume job"
                )
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "Smoke server did not shut down"
            engine.dispose()


if __name__ == "__main__":
    run()
