"""
TDD tests for Phase 8E2 — FAISS Index Persistence.

save_index(doc_hash, index)  → writes to disk under _INDEX_CACHE_DIR
load_index(doc_hash)         → returns FAISS index if cached, else None

Run: pytest tests/unit/test_faiss_persistence.py -v
"""
import pytest
from unittest.mock import MagicMock, patch


FAKE_HASH = "a" * 64  # 64-char hex SHA-256

# ---------------------------------------------------------------------------
# 1. save_index / load_index
# ---------------------------------------------------------------------------

class TestSaveIndex:
    def test_save_index_creates_file(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        fake_index = MagicMock()
        emb.save_index(FAKE_HASH, fake_index)
        assert fake_index.save_local.called

    def test_save_index_uses_hash_as_folder_name(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        fake_index = MagicMock()
        emb.save_index(FAKE_HASH, fake_index)
        # save_local should be called with a path containing the hash
        call_args = fake_index.save_local.call_args
        path_arg = str(call_args[0][0])
        assert FAKE_HASH in path_arg

    def test_save_index_rejects_non_hex_hash(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        with pytest.raises(ValueError):
            emb.save_index("../evil/path", MagicMock())

    def test_save_index_rejects_short_hash(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        with pytest.raises(ValueError):
            emb.save_index("abc", MagicMock())


class TestLoadIndex:
    def test_load_index_returns_none_when_not_cached(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        result = emb.load_index(FAKE_HASH)
        assert result is None

    def test_load_index_returns_index_after_save(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        # Simulate save creating the folder
        index_dir = tmp_path / FAKE_HASH
        index_dir.mkdir()
        # Write dummy index files to trick the folder-exists check
        (index_dir / "index.faiss").write_bytes(b"fake")
        (index_dir / "index.pkl").write_bytes(b"fake")

        mock_index = MagicMock()
        with patch("data.embeddings.FAISS.load_local", return_value=mock_index) as mock_load:
            result = emb.load_index(FAKE_HASH)
        assert result is mock_index
        assert mock_load.called

    def test_load_index_rejects_non_hex_hash(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        with pytest.raises(ValueError):
            emb.load_index("../../etc/passwd")

    def test_load_index_returns_none_on_corrupt_files(self, tmp_path, monkeypatch):
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)
        index_dir = tmp_path / FAKE_HASH
        index_dir.mkdir()
        (index_dir / "index.faiss").write_bytes(b"corrupt")
        (index_dir / "index.pkl").write_bytes(b"corrupt")
        with patch("data.embeddings.FAISS.load_local", side_effect=Exception("corrupt")):
            result = emb.load_index(FAKE_HASH)
        assert result is None


# ---------------------------------------------------------------------------
# 2. build_index_async uses cache when available
# ---------------------------------------------------------------------------

class TestBuildIndexAsyncCaching:
    def test_build_index_async_skips_embedding_when_cached(self, tmp_path, monkeypatch):
        """If load_index returns a hit, build_index_async returns it without calling FAISS.from_documents."""
        import asyncio
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)

        cached = MagicMock()
        with patch.object(emb, "load_index", return_value=cached) as mock_load, \
             patch.object(emb, "build_index") as mock_build:
            result = asyncio.run(
                emb.build_index_async("hello world", doc_hash=FAKE_HASH)
            )
        assert result is cached
        mock_build.assert_not_called()

    def test_build_index_async_builds_and_saves_when_not_cached(self, tmp_path, monkeypatch):
        import asyncio
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)

        built = MagicMock()
        with patch.object(emb, "load_index", return_value=None), \
             patch.object(emb, "build_index", return_value=built) as mock_build, \
             patch.object(emb, "save_index") as mock_save:
            result = asyncio.run(
                emb.build_index_async("hello world", doc_hash=FAKE_HASH)
            )
        mock_build.assert_called_once()
        mock_save.assert_called_once_with(FAKE_HASH, built)
        assert result is built

    def test_build_index_async_works_without_doc_hash(self, tmp_path, monkeypatch):
        """When doc_hash is None, caching is skipped — existing behaviour preserved."""
        import asyncio
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)

        built = MagicMock()
        with patch.object(emb, "build_index", return_value=built), \
             patch.object(emb, "save_index") as mock_save:
            result = asyncio.run(
                emb.build_index_async("hello world")
            )
        mock_save.assert_not_called()
        assert result is built
