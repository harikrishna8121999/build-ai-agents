"""Load, chunk, embed and index the policy documents."""

from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .config import PROJECT_ROOT, build_embeddings

POLICY_DIR = PROJECT_ROOT / "data" / "policies"


def load_policy_docs():
    """One Document per policy file, with the file name as its source."""
    return [
        Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": path.name})
        for path in sorted(POLICY_DIR.glob("*.md"))
    ]


def chunk_docs(docs, chunk_size=600, chunk_overlap=80):
    """Split each doc at its markdown headings, then cap the chunk size."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "title"), ("##", "section")], strip_headers=False
    )
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = []
    for doc in docs:
        for section in header_splitter.split_text(doc.page_content):
            section.metadata["source"] = doc.metadata["source"]
            chunks.extend(size_splitter.split_documents([section]))
    return chunks


@lru_cache(maxsize=1)
def get_vector_store():
    """Build the in-memory vector store once and reuse it."""
    return InMemoryVectorStore.from_documents(
        chunk_docs(load_policy_docs()), embedding=build_embeddings()
    )


def search(query, k=4):
    return get_vector_store().similarity_search(query, k=k)
