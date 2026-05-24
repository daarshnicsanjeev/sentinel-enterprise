"""
Unit + integration tests for batch processing endpoints (Phase 9C).
TDD: RED first — all tests fail until endpoints are implemented.
Run: pytest tests/unit/test_batch.py -v
"""
import io
import zipfile
import pytest
from unittest.mock import patch, AsyncMock




def make_zip(*files: tuple[str, bytes]) -> bytes:
    """Create an in-memory ZIP with the given (name, content) pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


SAMPLE_TXT = b"This is a sample document for batch testing."
SAMPLE_ZIP_ONE = make_zip(("doc1.txt", SAMPLE_TXT))
SAMPLE_ZIP_TWO = make_zip(("doc1.txt", SAMPLE_TXT), ("doc2.txt", SAMPLE_TXT))


# ---------------------------------------------------------------------------
# POST /api/analyze/batch
# ---------------------------------------------------------------------------

class TestBatchEndpoint:
    def test_batch_endpoint_returns_202(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        assert resp.status_code == 202

    def test_batch_response_includes_job_id(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        data = resp.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)
        assert len(data["job_id"]) == 36  # UUID length

    def test_batch_response_includes_total_count(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_TWO, "application/zip")},
        )
        data = resp.json()
        assert data["total"] == 2

    def test_batch_rejects_non_zip_content_type(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("doc.txt", SAMPLE_TXT, "text/plain")},
        )
        assert resp.status_code == 400

    def test_batch_rejects_invalid_zip_bytes(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("bad.zip", b"not a zip file", "application/zip")},
        )
        assert resp.status_code == 400

    def test_batch_rejects_too_many_files(self, client):
        # 51 files exceeds limit of 50
        many = make_zip(*[(f"doc{i}.txt", SAMPLE_TXT) for i in range(51)])
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("many.zip", many, "application/zip")},
        )
        assert resp.status_code == 422

    def test_batch_rejects_disallowed_extension(self, client):
        bad_zip = make_zip(("script.exe", b"MZ..."))
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("bad.zip", bad_zip, "application/zip")},
        )
        assert resp.status_code == 422

    def test_batch_rejects_zip_slip_path(self, client):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../../etc/passwd", "root:x:0:0")
        slip_zip = buf.getvalue()
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("slip.zip", slip_zip, "application/zip")},
        )
        assert resp.status_code == 422

    def test_batch_rejects_absolute_path_in_zip(self, client):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("/etc/passwd")
            zf.writestr(info, "root:x:0:0")
        abs_zip = buf.getvalue()
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("abs.zip", abs_zip, "application/zip")},
        )
        assert resp.status_code == 422

    def test_batch_job_initial_status_is_pending_or_running(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        job_id = resp.json()["job_id"]
        status_resp = client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ("pending", "running", "completed")

    def test_batch_job_has_total_field(self, client):
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        job_id = resp.json()["job_id"]
        status_resp = client.get(f"/api/jobs/{job_id}")
        assert "total" in status_resp.json()


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

class TestJobStatusEndpoint:
    def test_job_status_returns_200_for_valid_job(self, client):
        create_resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200

    def test_job_status_returns_404_for_unknown_job(self, client):
        resp = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_job_status_returns_422_for_invalid_job_id(self, client):
        resp = client.get("/api/jobs/not-a-valid-uuid")
        assert resp.status_code == 422

    def test_job_status_has_completed_field(self, client):
        create_resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/jobs/{job_id}")
        assert "completed" in resp.json()

    def test_job_status_has_results_list(self, client):
        create_resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", SAMPLE_ZIP_ONE, "application/zip")},
        )
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/jobs/{job_id}")
        assert "results" in resp.json()
        assert isinstance(resp.json()["results"], list)
