"""
TDD tests for cache-aware batch processing (Phase 9C cache).
Tests _process_batch directly to avoid asyncio.create_task timing issues.
Run: pytest tests/unit/test_batch_cache.py -v
"""
import io
import json
import hashlib
import zipfile
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def make_zip(*files: tuple[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


SAMPLE_CONTENT = b"This is a test document for batch cache testing."
DOC_HASH = hashlib.sha256(SAMPLE_CONTENT).hexdigest()

CACHED_PAYLOAD = {
    "type": "done",
    "final_decision": "APPROVED",
    "doc_type": "LEGAL_CONTRACT",
    "evaluation_score": 0.95,
    "hallucination_risk": "low",
    "routing_confidence": 0.88,
    "clause_results": [],
    "clause_results_history": [],
    "language": "en",
    "trace_id": "cached-trace-0000",
    "sanitized": True,
}

FRESH_PIPELINE_RESULT = {
    "final_decision": "REJECTED",
    "evaluation_score": 0.55,
    "hallucination_risk": "medium",
    "doc_type": "LEGAL_CONTRACT",
    "routing_confidence": 0.7,
    "clause_results": [],
    "clause_results_history": [],
    "language": "en",
    "sanitized": True,
    "retry_count": 0,
}



# ---------------------------------------------------------------------------
# Helpers — run _process_batch with controlled mocks
# ---------------------------------------------------------------------------

def run_batch(zf_bytes: bytes, names: list[str], force_refresh: bool = False,
              pipeline_result: dict = None, cached_result: dict = None):
    """
    Run _process_batch synchronously with mocked history_store and pipeline.
    Returns the list of results stored in the job.
    """
    import data.history_store as hs
    import api.routes as routes_mod

    job_id = "test-job-0000-0000-0000-000000000000"
    result_store = {}

    async def fake_get_cache(hash_):
        return cached_result

    async def fake_delete_cache(hash_):
        pass

    async def fake_insert_cache(hash_, payload):
        result_store["cached_payload"] = payload
        result_store["cached_hash"] = hash_

    async def fake_create_job(jid, total):
        pass

    async def fake_update_job(jid, completed, results, status):
        result_store["results"] = results
        result_store["status"] = status

    pipeline_calls = []

    async def fake_pipeline(text, trace_id, filename, tenant_id):
        pipeline_calls.append(filename)
        return pipeline_result or FRESH_PIPELINE_RESULT

    async def fake_save_history(trace_id, filename, final_state, raw_text=""):
        pass

    async def _run():
        with (
            patch.object(hs, "get_doc_cache", side_effect=fake_get_cache),
            patch.object(hs, "delete_doc_cache", side_effect=fake_delete_cache),
            patch.object(hs, "insert_doc_cache", side_effect=fake_insert_cache),
            patch.object(hs, "update_batch_job", side_effect=fake_update_job),
            patch.object(routes_mod, "_run_graph_once", side_effect=fake_pipeline),
            patch.object(routes_mod, "_save_to_history", side_effect=fake_save_history),
        ):
            await routes_mod._process_batch(job_id, zf_bytes, names, force_refresh=force_refresh)

    asyncio.run(_run())
    return result_store, pipeline_calls


# ---------------------------------------------------------------------------
# Cache HIT tests
# ---------------------------------------------------------------------------

class TestBatchCacheHit:
    def test_pipeline_not_called_when_doc_cached(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        _, pipeline_calls = run_batch(zf, ["doc.txt"], cached_result=CACHED_PAYLOAD)
        assert "doc.txt" not in pipeline_calls

    def test_result_uses_cached_decision(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["doc.txt"], cached_result=CACHED_PAYLOAD)
        results = store.get("results", [])
        assert any(r["final_decision"] == "APPROVED" for r in results if r.get("filename") == "doc.txt")

    def test_result_has_from_cache_true(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["doc.txt"], cached_result=CACHED_PAYLOAD)
        results = store.get("results", [])
        doc_result = next(r for r in results if r.get("filename") == "doc.txt")
        assert doc_result.get("from_cache") is True

    def test_cache_not_written_for_cache_hit(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["doc.txt"], cached_result=CACHED_PAYLOAD)
        assert "cached_hash" not in store  # insert_doc_cache was NOT called


# ---------------------------------------------------------------------------
# Cache MISS (fresh doc) tests
# ---------------------------------------------------------------------------

class TestBatchCacheMiss:
    def test_pipeline_called_for_fresh_doc(self):
        zf = make_zip(("fresh.txt", SAMPLE_CONTENT))
        _, pipeline_calls = run_batch(zf, ["fresh.txt"], cached_result=None)
        assert "fresh.txt" in pipeline_calls

    def test_result_has_from_cache_false(self):
        zf = make_zip(("fresh.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["fresh.txt"], cached_result=None)
        results = store.get("results", [])
        doc_result = next(r for r in results if r.get("filename") == "fresh.txt")
        assert doc_result.get("from_cache") is False

    def test_result_written_to_cache_after_pipeline(self):
        zf = make_zip(("fresh.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["fresh.txt"], cached_result=None)
        assert "cached_hash" in store
        assert store["cached_hash"] == DOC_HASH

    def test_cached_payload_has_correct_decision(self):
        zf = make_zip(("fresh.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["fresh.txt"], cached_result=None,
                             pipeline_result=FRESH_PIPELINE_RESULT)
        assert store["cached_payload"]["final_decision"] == "REJECTED"


# ---------------------------------------------------------------------------
# force_refresh tests
# ---------------------------------------------------------------------------

class TestBatchForceRefresh:
    def test_pipeline_called_even_when_cached(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        _, pipeline_calls = run_batch(zf, ["doc.txt"], force_refresh=True,
                                      cached_result=CACHED_PAYLOAD)
        assert "doc.txt" in pipeline_calls

    def test_result_has_from_cache_false_when_force_refresh(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["doc.txt"], force_refresh=True,
                             cached_result=CACHED_PAYLOAD)
        results = store.get("results", [])
        doc_result = next(r for r in results if r.get("filename") == "doc.txt")
        assert doc_result.get("from_cache") is False

    def test_cache_written_after_force_refresh_pipeline(self):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        store, _ = run_batch(zf, ["doc.txt"], force_refresh=True,
                             cached_result=CACHED_PAYLOAD)
        assert "cached_hash" in store


# ---------------------------------------------------------------------------
# HTTP endpoint tests — force_refresh param accepted
# ---------------------------------------------------------------------------

class TestBatchEndpointForceRefresh:
    def test_force_refresh_field_accepted_as_false(self, client):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", make_zip(("a.txt", b"x")), "application/zip")},
            data={"force_refresh": "false"},
        )
        assert resp.status_code == 202

    def test_force_refresh_field_accepted_as_true(self, client):
        zf = make_zip(("doc.txt", SAMPLE_CONTENT))
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("docs.zip", make_zip(("a.txt", b"x")), "application/zip")},
            data={"force_refresh": "true"},
        )
        assert resp.status_code == 202
