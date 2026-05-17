import asyncio
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)


def build_index(text: str) -> FAISS:
    """Chunk a document and build a FAISS vector index over it."""
    chunks = _splitter.create_documents([text])
    return FAISS.from_documents(chunks, _embeddings)


async def build_index_async(text: str) -> FAISS:
    """Non-blocking wrapper: offloads CPU-bound FAISS indexing to a thread."""
    return await asyncio.to_thread(build_index, text)


def semantic_search(index: FAISS, query: str, k: int = 3) -> list[str]:
    """Return the top-k most semantically relevant chunks for a query."""
    docs = index.similarity_search(query, k=k)
    return [doc.page_content for doc in docs]
