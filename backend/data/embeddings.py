"""
Vector-store abstraction for Sentinel document embeddings.

Supports two backends, selected by the VECTOR_STORE environment variable:

  VECTOR_STORE=faiss        (default) — in-process FAISS, cached to disk under
                                        faiss_cache/ keyed by SHA-256 doc_hash.
  VECTOR_STORE=opensearch   — Amazon OpenSearch Service (or local Docker image).
                              Indices are persistent server-side; save_index is
                              a no-op. Index name: sentinel-{doc_hash[:16]}.

All callers use the same four public symbols regardless of backend:
  build_index(text, doc_hash=None)       → vector store object
  build_index_async(text, doc_hash=None) → same, non-blocking
  save_index(doc_hash, index)            → persist (no-op for OpenSearch)
  load_index(doc_hash)                   → cached index or None
  semantic_search(index, query, k=3)     → list[str] of top-k chunks
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
_embeddings = None  # loaded on first use to avoid torch at import time

_INDEX_CACHE_DIR = Path(__file__).parent.parent / "faiss_cache"
_INDEX_CACHE_DIR.mkdir(exist_ok=True)

_HEX64_RE = re.compile(r'^[0-9a-f]{64}$')


# =============================================================================
# Backend selector — reads env var at call time so tests can monkeypatch it
# =============================================================================

def _get_vector_store() -> str:
    """Return the active vector-store backend: 'faiss' (default) or 'opensearch'."""
    return os.getenv("VECTOR_STORE", "faiss").lower()


# =============================================================================
# Shared helpers
# =============================================================================

def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def _validate_hash(doc_hash: str) -> None:
    if not _HEX64_RE.match(doc_hash):
        raise ValueError(f"doc_hash must be a 64-char lowercase hex string, got: {doc_hash!r}")


# =============================================================================
# OpenSearch helpers (lazy-imported — opensearch-py not required for FAISS mode)
# =============================================================================

def _opensearch_index_name(doc_hash: str) -> str:
    """Derive a safe OpenSearch index name from the first 16 chars of doc_hash."""
    return f"sentinel-{doc_hash[:16]}"


def _opensearch_url() -> str:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    use_ssl = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
    scheme = "https" if use_ssl else "http"
    return f"{scheme}://{host}:{port}"


def _get_opensearch_client():
    """Create and return a low-level OpenSearch client (lazy import)."""
    from opensearchpy import OpenSearch
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "admin")
    use_ssl = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(user, password),
        use_ssl=use_ssl,
        verify_certs=False,
    )


def _build_opensearch_index(text: str, doc_hash: str | None = None) -> Any:
    """Chunk text and index it into OpenSearch. Returns an OpenSearchVectorSearch.

    Uses engine='lucene' (supported in OpenSearch 2.x; nmslib is deprecated).
    Sets verify_certs=False for AWS-signed certificates and a 30s timeout so
    the pipeline fails fast rather than hanging if the domain is unreachable.
    Falls back to FAISS in-process if OpenSearch is unavailable.
    """
    from langchain_community.vectorstores import OpenSearchVectorSearch
    chunks = _splitter.create_documents([text])
    index_name = _opensearch_index_name(doc_hash) if doc_hash else "sentinel-temp"
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "admin")
    return OpenSearchVectorSearch.from_documents(
        chunks,
        _get_embeddings(),
        opensearch_url=_opensearch_url(),
        http_auth=(user, password),
        index_name=index_name,
        engine="lucene",          # lucene is the default k-NN engine in OpenSearch 2.x
        space_type="cosinesimil",
        verify_certs=False,       # AWS endpoint uses a cert not in the default trust store
        ssl_assert_hostname=False,
        timeout=5,                # seconds — fail fast rather than hanging indefinitely
    )


def _load_opensearch_index(doc_hash: str) -> Any:
    """Return an OpenSearchVectorSearch over the existing index (no re-indexing)."""
    from langchain_community.vectorstores import OpenSearchVectorSearch
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "admin")
    return OpenSearchVectorSearch(
        opensearch_url=_opensearch_url(),
        http_auth=(user, password),
        index_name=_opensearch_index_name(doc_hash),
        embedding_function=_get_embeddings(),
        verify_certs=False,
        ssl_assert_hostname=False,
        timeout=30,
    )


# =============================================================================
# Public API — identical interface for both backends
# =============================================================================

def save_index(doc_hash: str, index: Any) -> None:
    """Persist a vector index.

    FAISS   → writes to disk under _INDEX_CACHE_DIR/{doc_hash}/
    OpenSearch → no-op (index already lives on the server)
    """
    _validate_hash(doc_hash)
    if _get_vector_store() == "opensearch":
        return  # server-side persistence; nothing to do locally
    dest = _INDEX_CACHE_DIR / doc_hash
    dest.mkdir(exist_ok=True)
    index.save_local(str(dest))


def load_index(doc_hash: str) -> Any | None:
    """Load a cached vector index, or return None if not found / unreachable.

    FAISS   → checks _INDEX_CACHE_DIR/{doc_hash}/index.faiss on disk
    OpenSearch → checks whether the index exists on the server
    """
    _validate_hash(doc_hash)

    if _get_vector_store() == "opensearch":
        try:
            client = _get_opensearch_client()
            index_name = _opensearch_index_name(doc_hash)
            if not client.indices.exists(index=index_name):
                return None
            return _load_opensearch_index(doc_hash)
        except Exception:
            return None

    # FAISS (default)
    index_dir = _INDEX_CACHE_DIR / doc_hash
    if not (index_dir / "index.faiss").exists():
        return None
    try:
        return FAISS.load_local(str(index_dir), _get_embeddings(), allow_dangerous_deserialization=True)
    except Exception:
        return None


def build_index(text: str, doc_hash: str | None = None) -> Any:
    """Chunk a document and build a vector index over it.

    FAISS   → builds an in-process FAISS index (doc_hash unused here)
    OpenSearch → creates / overwrites an index on the server using doc_hash as
                 part of the index name.

    If OpenSearch is configured but unreachable, automatically falls back to
    FAISS so the pipeline never stalls on a network error.
    """
    if _get_vector_store() == "opensearch":
        try:
            return _build_opensearch_index(text, doc_hash)
        except Exception as exc:
            import logging
            logging.getLogger("sentinel.embeddings").warning(
                "OpenSearch index build failed — falling back to FAISS: %s", exc
            )
            # Fall through to FAISS below
    # FAISS (default / fallback)
    chunks = _splitter.create_documents([text])
    return FAISS.from_documents(chunks, _get_embeddings())


async def build_index_async(text: str, doc_hash: str | None = None) -> Any:
    """Non-blocking wrapper: checks cache first, then builds and saves.

    Works identically for both FAISS and OpenSearch backends.
    """
    if doc_hash is not None:
        cached = load_index(doc_hash)
        if cached is not None:
            return cached
    index = await asyncio.to_thread(build_index, text, doc_hash)
    if doc_hash is not None:
        save_index(doc_hash, index)
    return index


_MAX_K = 50


def semantic_search(index: Any, query: str, k: int = 3) -> list[str]:
    """Return the top-k most semantically relevant chunks for a query.

    Both FAISS and OpenSearchVectorSearch expose .similarity_search(query, k=k),
    so this function is backend-agnostic.
    """
    k = max(1, min(k, _MAX_K))
    docs = index.similarity_search(query, k=k)
    return [doc.page_content for doc in docs]
