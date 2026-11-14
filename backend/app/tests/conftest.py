import os
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import jwt
import pytest

# Isolated file databases permit independent API, worker and document-store connections.
_test_dir = tempfile.TemporaryDirectory(prefix="opportunityos-tests-")
os.environ.update(
    ENVIRONMENT="test",
    AUTH_PROVIDER="local",
    AI_PROVIDER="deterministic",
    JOBS_EAGER="true",
    DATABASE_URL="sqlite:///" + str(Path(_test_dir.name) / "test.db"),
    CAREER_CHECKPOINT_DB=str(Path(_test_dir.name) / "checkpoints.sqlite"),
    RATE_LIMIT_PER_MINUTE="100000",
)
from app.config import settings
from app.config.database import engine
from app.models.base import Base
from app.main import app, local_rates
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    local_rates.clear()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def headers():
    instant = datetime.now(timezone.utc)

    def make(subject=None):
        token = jwt.encode(
            dict(
                sub=subject or str(uuid4()),
                email="student@example.test",
                email_verified=True,
                iss="opportunityos-local",
                aud="opportunityos",
                iat=instant,
                exp=instant + timedelta(hours=1),
            ),
            settings.jwt_secret,
            algorithm="HS256",
        )
        return {"Authorization": "Bearer " + token}

    return make


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _test_dir.cleanup()
