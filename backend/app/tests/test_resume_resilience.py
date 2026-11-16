import pytest
from unittest.mock import patch, MagicMock
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from sqlalchemy.exc import OperationalError
from app.repositories import documents
from app.models.base import now
import pymupdf


def make_sample_pdf(content="Experienced Python, React, and Docker developer."):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# MongoDB Fallback Tests
# ---------------------------------------------------------------------------

def test_mongodb_unavailable_during_write(client, monkeypatch):
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_col.update_one.side_effect = ServerSelectionTimeoutError("Atlas TLS timeout")
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_col

    monkeypatch.setattr(documents, "client", mock_client)

    doc_id = "test-doc-write-fallback"
    payload = {"title": "Fallback Write Test", "data": "persisted-to-sql"}

    # Should fall back to PostgreSQL LocalDocument without raising
    saved = documents.put("test_fallback_col", doc_id, payload)
    assert saved["id"] == doc_id
    assert saved["data"] == "persisted-to-sql"

    # Confirm it is stored in SQL LocalDocument
    sql_record = documents._get_sql("test_fallback_col", doc_id)
    assert sql_record is not None
    assert sql_record["data"] == "persisted-to-sql"


def test_mongodb_unavailable_during_read(client, monkeypatch):
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_col.find_one.side_effect = ServerSelectionTimeoutError("Atlas connection refused")
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_col

    monkeypatch.setattr(documents, "client", mock_client)

    doc_id = "test-doc-read-fallback"
    # Seed SQL LocalDocument
    documents._put_sql("test_fallback_col", doc_id, {"id": doc_id, "data": "from-sql-fallback"})

    retrieved = documents.get("test_fallback_col", doc_id)
    assert retrieved is not None
    assert retrieved["data"] == "from-sql-fallback"


def test_mongodb_unavailable_during_scan(client, monkeypatch):
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_col.find.side_effect = ServerSelectionTimeoutError("Atlas network down")
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_col

    monkeypatch.setattr(documents, "client", mock_client)

    doc_id = "test-doc-scan-fallback"
    owner = "scan-owner-1"
    documents._put_sql("test_fallback_col", doc_id, {"id": doc_id, "owner_id": owner, "title": "Scanned Document"})

    results = documents.scan("test_fallback_col", owner=owner)
    assert len(results) >= 1
    assert any(r["id"] == doc_id for r in results)


def test_mongodb_recovering_after_fallback_write(client, monkeypatch):
    doc_id = "test-doc-recovery"
    owner = "recovery-owner"

    # 1. MongoDB had an OLD version
    old_time = "2026-01-01T00:00:00"
    mongo_storage = {
        doc_id: {"id": doc_id, "owner_id": owner, "version": "v1-old", "_updated_at": old_time}
    }

    mock_client = MagicMock()
    mock_col = MagicMock()

    def mock_find_one(query, projection):
        record_id = query.get("_id")
        return mongo_storage.get(record_id)

    def mock_update_one(filter_query, update_doc, upsert=False):
        record_id = filter_query.get("_id")
        data = update_doc.get("$set", {})
        mongo_storage[record_id] = dict(data, id=record_id)
        return MagicMock(matched_count=1)

    mock_col.find_one.side_effect = mock_find_one
    mock_col.update_one.side_effect = mock_update_one
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_col

    monkeypatch.setattr(documents, "client", mock_client)

    # 2. While Mongo was down, a newer version was written to PostgreSQL
    new_time = "2026-06-01T12:00:00"
    documents._put_sql(
        "test_fallback_col",
        doc_id,
        {"id": doc_id, "owner_id": owner, "version": "v2-newer", "_updated_at": new_time},
    )

    # 3. Read should detect newer PostgreSQL record, return it, and sync forward to MongoDB
    result = documents.get("test_fallback_col", doc_id, owner=owner)
    assert result["version"] == "v2-newer"
    # Verify it synced forward to MongoDB storage
    assert mongo_storage[doc_id]["version"] == "v2-newer"


def test_both_storage_systems_failing(monkeypatch):
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_col.update_one.side_effect = ServerSelectionTimeoutError("Mongo dead")
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_col
    monkeypatch.setattr(documents, "client", mock_client)

    # Make SQL also fail
    with patch("app.repositories.documents.Session.begin", side_effect=OperationalError("DB Connection Lost", None, None)):
        with pytest.raises(OperationalError):
            documents.put("test_col", "fail-id", {"value": 123})


# ---------------------------------------------------------------------------
# In-process Execution and Latest Resume Endpoint Tests
# ---------------------------------------------------------------------------

def test_resume_upload_in_process_execution_and_retrieval(client, headers):
    h = headers()
    pdf_bytes = make_sample_pdf("Proficient in Python, React, and Fastapi.")

    # 1. Upload resume -> 202 Accepted
    upload_res = client.post(
        "/api/v1/resume/upload",
        headers=h,
        files={"file": ("my_resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 202, upload_res.text
    data = upload_res.json()["data"]
    job_id = data["job_id"]
    doc_id = data["document_id"]
    assert job_id
    assert doc_id

    # 2. In-process execution completes in BackgroundTask
    job_res = client.get(f"/api/v1/jobs/{job_id}/result", headers=h)
    assert job_res.status_code == 200
    job_data = job_res.json()["data"]
    assert job_data["status"] == "COMPLETED"
    assert "python" in job_data["result"]["skills"]
    assert "react" in job_data["result"]["skills"]

    # 3. GET /resume/latest returns the completed analysis
    latest_res = client.get("/api/v1/resume/latest", headers=h)
    assert latest_res.status_code == 200, latest_res.text
    latest = latest_res.json()["data"]
    assert latest is not None
    assert latest["document_id"] == doc_id
    assert "python" in latest["skills"]
    assert latest["readiness_score"] is not None


def test_resume_latest_empty_state_and_user_isolation(client, headers):
    user1_h = headers()
    user2_h = headers()

    # User 2 has no resume uploaded -> returns empty state (null data)
    res2 = client.get("/api/v1/resume/latest", headers=user2_h)
    assert res2.status_code == 200
    assert res2.json()["data"] is None

    # User 1 uploads resume
    pdf_bytes = make_sample_pdf("Software Engineer specializing in Go and Kubernetes.")
    client.post(
        "/api/v1/resume/upload",
        headers=user1_h,
        files={"file": ("user1.pdf", pdf_bytes, "application/pdf")},
    )

    # User 1 retrieves their resume
    res1 = client.get("/api/v1/resume/latest", headers=user1_h)
    assert res1.status_code == 200
    assert res1.json()["data"] is not None
    assert "kubernetes" in res1.json()["data"]["skills"]

    # User 2 STILL receives null (User 1's data is isolated)
    res2_again = client.get("/api/v1/resume/latest", headers=user2_h)
    assert res2_again.status_code == 200
    assert res2_again.json()["data"] is None


def test_in_process_automatic_recovery(client, headers, monkeypatch):
    from datetime import timedelta
    from app.services import jobs
    from app.models.runtime import Job, Outbox
    from app.models.base import now
    from app.config.database import Session

    monkeypatch.setattr(jobs.settings, "job_dispatch_mode", "in_process")
    monkeypatch.setattr(jobs, "_last_recovery_at", 0.0)

    # 1. Insert an expired RUNNING job with attempts=1
    with Session() as db:
        job1 = Job(
            owner_id="test-owner-1",
            dedupe_key="test-dedupe-1",
            payload={"kind": "resume", "arguments": {"document_id": "doc1"}},
            status="RUNNING",
            attempts=1,
            lease_until=now() - timedelta(minutes=5),
        )
        # Insert a job with attempts=3 that should dead-letter
        job2 = Job(
            owner_id="test-owner-2",
            dedupe_key="test-dedupe-2",
            payload={"kind": "resume", "arguments": {"document_id": "doc2"}},
            status="RUNNING",
            attempts=3,
            lease_until=now() - timedelta(minutes=5),
        )
        db.add_all([job1, job2])
        db.commit()
        j1_id, j2_id = job1.id, job2.id

    # 2. Trigger dispatch() -> should execute recovery
    jobs.dispatch()

    # 3. Check statuses
    with Session() as db:
        r1 = db.get(Job, j1_id)
        r2 = db.get(Job, j2_id)
        assert r1.status in {"RETRY", "COMPLETED", "RUNNING"}
        assert r2.status == "DEAD_LETTER"
