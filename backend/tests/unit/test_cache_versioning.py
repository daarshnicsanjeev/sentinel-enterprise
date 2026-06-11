"""
TDD tests for version-stamped doc cache.

Cached verdicts must not outlive the pipeline logic that produced them
(regression: the challan's stale APPROVED was served from cache after the
UNKNOWN->ESCALATE fix until manually purged).

Run: pytest tests/unit/test_cache_versioning.py -v
"""
import pytest

from data import history_store


DOC_HASH = "a" * 64
PAYLOAD = {
    "type": "done",
    "final_decision": "APPROVED",
    "doc_type": "CREDIT_AGREEMENT",
    "evaluation_score": 1.0,
    "hallucination_risk": "low",
    "routing_confidence": 0.9,
    "clause_results": [],
    "language": "en",
    "trace_id": "11111111-1111-1111-1111-111111111111",
}


@pytest.mark.asyncio
class TestCacheVersioning:
    async def test_round_trip_under_current_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        await history_store.init_db()
        await history_store.insert_doc_cache(DOC_HASH, PAYLOAD)
        cached = await history_store.get_doc_cache(DOC_HASH)
        assert cached is not None
        assert cached["final_decision"] == "APPROVED"

    async def test_entry_written_under_old_version_is_a_miss(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        await history_store.init_db()
        monkeypatch.setattr(history_store, "PIPELINE_VERSION", "old")
        await history_store.insert_doc_cache(DOC_HASH, PAYLOAD)
        monkeypatch.setattr(history_store, "PIPELINE_VERSION", "new")
        assert await history_store.get_doc_cache(DOC_HASH) is None

    async def test_legacy_unversioned_row_is_a_miss(self, tmp_path, monkeypatch):
        """Rows written before versioning existed (key = bare sha256) must not be served."""
        import aiosqlite, json
        db_file = str(tmp_path / "t.db")
        monkeypatch.setattr(history_store, "_DB_PATH", db_file)
        await history_store.init_db()
        async with aiosqlite.connect(db_file) as db:
            await db.execute(
                "INSERT INTO doc_cache (doc_hash, payload, cached_at) VALUES (?, ?, ?)",
                (DOC_HASH, json.dumps(PAYLOAD), "2026-01-01T00:00:00"),
            )
            await db.commit()
        assert await history_store.get_doc_cache(DOC_HASH) is None

    async def test_init_db_purges_stale_version_rows(self, tmp_path, monkeypatch):
        import aiosqlite
        db_file = str(tmp_path / "t.db")
        monkeypatch.setattr(history_store, "_DB_PATH", db_file)
        await history_store.init_db()
        monkeypatch.setattr(history_store, "PIPELINE_VERSION", "old")
        await history_store.insert_doc_cache(DOC_HASH, PAYLOAD)
        monkeypatch.setattr(history_store, "PIPELINE_VERSION", "new")
        await history_store.init_db()  # self-cleaning pass
        async with aiosqlite.connect(db_file) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM doc_cache")
            count = (await cursor.fetchone())[0]
        assert count == 0

    async def test_delete_doc_cache_uses_versioned_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        await history_store.init_db()
        await history_store.insert_doc_cache(DOC_HASH, PAYLOAD)
        await history_store.delete_doc_cache(DOC_HASH)
        assert await history_store.get_doc_cache(DOC_HASH) is None
