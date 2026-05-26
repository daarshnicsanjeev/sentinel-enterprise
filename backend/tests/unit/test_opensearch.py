"""
TDD tests for OpenSearch dual-backend in data/embeddings.py.

These tests verify that:
  - FAISS is still the default when VECTOR_STORE is unset
  - OpenSearch backend is selected when VECTOR_STORE=opensearch
  - save_index is a no-op for OpenSearch (persistence is server-side)
  - load_index returns None when OpenSearch is unreachable
  - load_index returns None when the index does not exist on the server
  - load_index returns an OpenSearchVectorSearch instance when index exists
  - semantic_search works identically with an OpenSearch index
  - build_index_async caches correctly through the OpenSearch backend

All OpenSearch network calls are mocked — no running OpenSearch required.

Run: pytest tests/unit/test_opensearch.py -v
"""
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

FAKE_HASH = "b" * 64  # 64-char hex SHA-256 — different from FAISS test to avoid any shared state


# ---------------------------------------------------------------------------
# 1. _get_vector_store() — env-var driven selection
# ---------------------------------------------------------------------------

class TestGetVectorStore:
    def test_defaults_to_faiss_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("VECTOR_STORE", raising=False)
        import data.embeddings as emb
        assert emb._get_vector_store() == "faiss"

    def test_returns_opensearch_when_env_set(self, monkeypatch):
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb
        assert emb._get_vector_store() == "opensearch"

    def test_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("VECTOR_STORE", "OpenSearch")
        import data.embeddings as emb
        assert emb._get_vector_store() == "opensearch"


# ---------------------------------------------------------------------------
# 2. save_index — no-op for OpenSearch
# ---------------------------------------------------------------------------

class TestSaveIndexOpensearch:
    def test_save_index_is_noop_for_opensearch(self, tmp_path, monkeypatch):
        """When VECTOR_STORE=opensearch, save_index should not write to disk."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb
        monkeypatch.setattr(emb, "_INDEX_CACHE_DIR", tmp_path)

        fake_index = MagicMock()
        emb.save_index(FAKE_HASH, fake_index)

        # save_local must NOT be called — OpenSearch persists server-side
        fake_index.save_local.assert_not_called()
        # No folder should be created
        assert not (tmp_path / FAKE_HASH).exists()

    def test_save_index_still_validates_hash_for_opensearch(self, monkeypatch):
        """Hash validation runs regardless of backend."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb
        with pytest.raises(ValueError):
            emb.save_index("../bad-hash", MagicMock())


# ---------------------------------------------------------------------------
# 3. load_index — OpenSearch backend
# ---------------------------------------------------------------------------

class TestLoadIndexOpensearch:
    def test_load_index_returns_none_when_opensearch_unreachable(self, monkeypatch):
        """Network errors are caught; None is returned so pipeline falls back to build."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        with patch.object(emb, "_get_opensearch_client", side_effect=Exception("connection refused")):
            result = emb.load_index(FAKE_HASH)

        assert result is None

    def test_load_index_returns_none_when_index_absent(self, monkeypatch):
        """If the index does not exist on the server, return None."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        with patch.object(emb, "_get_opensearch_client", return_value=mock_client):
            result = emb.load_index(FAKE_HASH)

        assert result is None
        mock_client.indices.exists.assert_called_once_with(index=f"sentinel-{FAKE_HASH[:16]}")

    def test_load_index_returns_vector_store_when_index_exists(self, monkeypatch):
        """If the index exists, return an OpenSearchVectorSearch instance."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        fake_vs = MagicMock()

        with patch.object(emb, "_get_opensearch_client", return_value=mock_client), \
             patch.object(emb, "_load_opensearch_index", return_value=fake_vs) as mock_load_os:
            result = emb.load_index(FAKE_HASH)

        assert result is fake_vs
        mock_load_os.assert_called_once_with(FAKE_HASH)

    def test_load_index_still_validates_hash_for_opensearch(self, monkeypatch):
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb
        with pytest.raises(ValueError):
            emb.load_index("not-a-valid-hash")


# ---------------------------------------------------------------------------
# 4. build_index — OpenSearch backend
# ---------------------------------------------------------------------------

class TestBuildIndexOpensearch:
    def test_build_index_calls_opensearch_from_documents(self, monkeypatch):
        """build_index should delegate to _build_opensearch_index when backend=opensearch."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        fake_vs = MagicMock()
        with patch.object(emb, "_build_opensearch_index", return_value=fake_vs) as mock_build_os:
            result = emb.build_index("some contract text")

        mock_build_os.assert_called_once_with("some contract text", None)
        assert result is fake_vs

    def test_build_index_passes_doc_hash_to_opensearch(self, monkeypatch):
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        fake_vs = MagicMock()
        with patch.object(emb, "_build_opensearch_index", return_value=fake_vs) as mock_build_os:
            result = emb.build_index("some text", doc_hash=FAKE_HASH)

        mock_build_os.assert_called_once_with("some text", FAKE_HASH)


# ---------------------------------------------------------------------------
# 5. semantic_search — identical interface for both backends
# ---------------------------------------------------------------------------

class TestSemanticSearchOpensearch:
    def test_semantic_search_calls_similarity_search_on_opensearch_index(self, monkeypatch):
        """semantic_search uses .similarity_search() — same interface for FAISS and OpenSearch."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        fake_doc = MagicMock()
        fake_doc.page_content = "relevant clause text"
        mock_index = MagicMock()
        mock_index.similarity_search.return_value = [fake_doc]

        result = emb.semantic_search(mock_index, "payment terms", k=1)

        mock_index.similarity_search.assert_called_once_with("payment terms", k=1)
        assert result == ["relevant clause text"]


# ---------------------------------------------------------------------------
# 6. build_index_async — caching with OpenSearch backend
# ---------------------------------------------------------------------------

class TestBuildIndexAsyncOpensearch:
    def test_build_index_async_skips_build_when_opensearch_cache_hits(self, monkeypatch):
        """If load_index finds the index on the server, build_index is not called."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        cached = MagicMock()
        with patch.object(emb, "load_index", return_value=cached) as mock_load, \
             patch.object(emb, "build_index") as mock_build:
            result = asyncio.run(
                emb.build_index_async("contract text", doc_hash=FAKE_HASH)
            )

        assert result is cached
        mock_build.assert_not_called()

    def test_build_index_async_builds_when_opensearch_index_absent(self, monkeypatch):
        """If the index is not on the server, build and save (save is a no-op for opensearch)."""
        monkeypatch.setenv("VECTOR_STORE", "opensearch")
        import data.embeddings as emb

        built = MagicMock()
        with patch.object(emb, "load_index", return_value=None), \
             patch.object(emb, "build_index", return_value=built) as mock_build, \
             patch.object(emb, "save_index") as mock_save:
            result = asyncio.run(
                emb.build_index_async("contract text", doc_hash=FAKE_HASH)
            )

        mock_build.assert_called_once()
        # save_index is still called (it's a no-op internally for opensearch)
        mock_save.assert_called_once_with(FAKE_HASH, built)
        assert result is built


# ---------------------------------------------------------------------------
# 7. Index name helper
# ---------------------------------------------------------------------------

class TestOpensearchIndexName:
    def test_index_name_uses_first_16_chars_of_hash(self):
        import data.embeddings as emb
        name = emb._opensearch_index_name(FAKE_HASH)
        assert name == f"sentinel-{FAKE_HASH[:16]}"

    def test_index_name_prefix_is_sentinel(self):
        import data.embeddings as emb
        name = emb._opensearch_index_name("c" * 64)
        assert name.startswith("sentinel-")
