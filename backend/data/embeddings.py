import asyncio
import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
_embeddings = None  # loaded on first use to avoid torch at import time

_INDEX_CACHE_DIR = Path(__file__).parent.parent / "faiss_cache"
_INDEX_CACHE_DIR.mkdir(exist_ok=True)

_HEX64_RE = re.compile(r'^[0-9a-f]{64}$')


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def _validate_hash(doc_hash: str) -> None:
    if not _HEX64_RE.match(doc_hash):
        raise ValueError(f"doc_hash must be a 64-char lowercase hex string, got: {doc_hash!r}")


def save_index(doc_hash: str, index: FAISS) -> None:
    """Persist a FAISS index to disk under _INDEX_CACHE_DIR/{doc_hash}/."""
    _validate_hash(doc_hash)
    dest = _INDEX_CACHE_DIR / doc_hash
    dest.mkdir(exist_ok=True)
    index.save_local(str(dest))


def load_index(doc_hash: str) -> FAISS | None:
    """Load a cached FAISS index from disk, or return None if not found."""
    _validate_hash(doc_hash)
    index_dir = _INDEX_CACHE_DIR / doc_hash
    if not (index_dir / "index.faiss").exists():
        return None
    try:
        return FAISS.load_local(str(index_dir), _get_embeddings(), allow_dangerous_deserialization=True)
    except Exception:
        return None


def build_index(text: str) -> FAISS:
    """Chunk a document and build a FAISS vector index over it."""
    chunks = _splitter.create_documents([text])
    return FAISS.from_documents(chunks, _get_embeddings())


async def build_index_async(text: str, doc_hash: str | None = None) -> FAISS:
    """Non-blocking wrapper: checks disk cache first, then builds and saves."""
    if doc_hash is not None:
        cached = load_index(doc_hash)
        if cached is not None:
            return cached
    index = await asyncio.to_thread(build_index, text)
    if doc_hash is not None:
        save_index(doc_hash, index)
    return index


_MAX_K = 50


def semantic_search(index: FAISS, query: str, k: int = 3) -> list[str]:
    """Return the top-k most semantically relevant chunks for a query."""
    k = max(1, min(k, _MAX_K))
    docs = index.similarity_search(query, k=k)
    return [doc.page_content for doc in docs]
