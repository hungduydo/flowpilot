"""
ChromaDB client for RAG knowledge base.

Manages document embedding, storage, and retrieval using ChromaDB.
Uses OpenAI embeddings (text-embedding-3-small) or falls back to ChromaDB defaults.
"""

import hashlib
from pathlib import Path
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger()

# Collection names
COLLECTION_PATTERNS = "workflow_patterns"
COLLECTION_NODES = "node_reference"
COLLECTION_EXAMPLES = "example_workflows"
COLLECTION_TEMPLATES = "n8n_templates"

_chroma_client = None


def get_chroma_client():
    """Get or create ChromaDB HTTP client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        logger.info(
            "ChromaDB client created",
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return _chroma_client


def _get_embedding_function():
    """Get embedding function. Uses ChromaDB default (all-MiniLM-L6-v2) for local embedding."""
    # Use ChromaDB's built-in default embedding (sentence-transformers)
    # This runs locally — no API key needed, no quota issues
    return None


def get_collection(name: str):
    """Get or create a ChromaDB collection."""
    client = get_chroma_client()
    ef = _get_embedding_function()
    kwargs = {"name": name}
    if ef:
        kwargs["embedding_function"] = ef
    return client.get_or_create_collection(**kwargs)


def _chunk_markdown(text: str, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    """
    Split markdown text into chunks by sections (## headers).
    Falls back to character-based splitting if no headers found.
    """
    chunks = []

    # Split by ## headers
    sections = text.split("\n## ")
    if len(sections) > 1:
        for i, section in enumerate(sections):
            if i == 0:
                # First section might have # header
                content = section.strip()
            else:
                content = f"## {section.strip()}"

            if len(content) > chunk_size:
                # Further split large sections
                words = content.split()
                current = []
                current_len = 0
                for word in words:
                    if current_len + len(word) + 1 > chunk_size and current:
                        chunks.append({"text": " ".join(current)})
                        # Keep overlap
                        overlap_words = current[-10:] if len(current) > 10 else current
                        current = list(overlap_words)
                        current_len = sum(len(w) + 1 for w in current)
                    current.append(word)
                    current_len += len(word) + 1
                if current:
                    chunks.append({"text": " ".join(current)})
            elif content:
                chunks.append({"text": content})
    else:
        # No headers, split by size
        words = text.split()
        current = []
        current_len = 0
        for word in words:
            if current_len + len(word) + 1 > chunk_size and current:
                chunks.append({"text": " ".join(current)})
                current = current[-10:] if len(current) > 10 else current
                current_len = sum(len(w) + 1 for w in current)
            current.append(word)
            current_len += len(word) + 1
        if current:
            chunks.append({"text": " ".join(current)})

    return chunks


def ingest_markdown_file(
    file_path: str | Path,
    collection_name: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    """
    Ingest a markdown file into a ChromaDB collection.
    Returns number of chunks ingested.
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning("File not found", path=str(path))
        return 0

    text = path.read_text(encoding="utf-8")
    chunks = _chunk_markdown(text)

    if not chunks:
        return 0

    collection = get_collection(collection_name)

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        # Create deterministic ID based on file + chunk content
        content_hash = hashlib.md5(chunk["text"].encode()).hexdigest()[:12]
        doc_id = f"{path.stem}_{i}_{content_hash}"
        ids.append(doc_id)
        documents.append(chunk["text"])
        metadatas.append({
            "source": path.name,
            "chunk_index": i,
            "category": collection_name,
            **(metadata or {}),
        })

    # Upsert to avoid duplicates
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    logger.info(
        "Ingested markdown file",
        file=path.name,
        collection=collection_name,
        chunks=len(chunks),
    )
    return len(chunks)


def ingest_all_knowledge() -> dict[str, int]:
    """Ingest all knowledge files from the knowledge directory."""
    knowledge_dir = Path(__file__).parent / "knowledge"
    results = {}

    # Patterns
    patterns_dir = knowledge_dir / "patterns"
    if patterns_dir.exists():
        for f in patterns_dir.glob("*.md"):
            count = ingest_markdown_file(f, COLLECTION_PATTERNS)
            results[f"patterns/{f.name}"] = count

    # Nodes
    nodes_dir = knowledge_dir / "nodes"
    if nodes_dir.exists():
        for f in nodes_dir.glob("*.md"):
            count = ingest_markdown_file(f, COLLECTION_NODES)
            results[f"nodes/{f.name}"] = count

    # Examples
    examples_dir = knowledge_dir / "examples"
    if examples_dir.exists():
        for f in examples_dir.glob("*.md"):
            count = ingest_markdown_file(f, COLLECTION_EXAMPLES)
            results[f"examples/{f.name}"] = count

    logger.info("Knowledge base ingestion complete", results=results)
    return results


def ingest_template(
    template_id: int,
    distilled_text: str,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    """
    Ingest a distilled template text into the n8n_templates collection.

    Returns list of ChromaDB document IDs for tracking.
    """
    if not distilled_text.strip():
        return []

    collection = get_collection(COLLECTION_TEMPLATES)

    chunks = _chunk_markdown(distilled_text)
    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        content_hash = hashlib.md5(chunk["text"].encode()).hexdigest()[:12]
        doc_id = f"tpl_{template_id}_{i}_{content_hash}"
        ids.append(doc_id)
        documents.append(chunk["text"])
        metadatas.append({
            "source": f"n8n_template_{template_id}",
            "template_id": str(template_id),
            "chunk_index": i,
            "category": COLLECTION_TEMPLATES,
            **(metadata or {}),
        })

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    logger.info(
        "Ingested template",
        template_id=template_id,
        chunks=len(chunks),
    )
    return ids


def remove_template_chunks(chroma_doc_ids: list[str]) -> None:
    """Remove specific template chunks from ChromaDB."""
    if not chroma_doc_ids:
        return
    try:
        collection = get_collection(COLLECTION_TEMPLATES)
        collection.delete(ids=chroma_doc_ids)
        logger.info("Removed template chunks", count=len(chroma_doc_ids))
    except Exception as e:
        logger.warning("Failed to remove template chunks", error=str(e))


def search(query: str, n_results: int = 5, collection_names: list[str] | None = None) -> str:
    """
    Search across knowledge collections and return formatted context.

    Returns a formatted string suitable for injecting into LLM prompts.
    """
    collections = collection_names or [
        COLLECTION_PATTERNS,
        COLLECTION_NODES,
        COLLECTION_EXAMPLES,
        COLLECTION_TEMPLATES,
    ]

    all_results = []
    for col_name in collections:
        try:
            collection = get_collection(col_name)
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count()) if collection.count() > 0 else 1,
            )

            if results and results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    all_results.append({
                        "text": doc,
                        "source": meta.get("source", "unknown"),
                        "category": col_name,
                        "distance": dist,
                    })
        except Exception as e:
            logger.warning("Search failed for collection", collection=col_name, error=str(e))

    if not all_results:
        return ""

    # Sort by distance (lower = more relevant)
    all_results.sort(key=lambda x: x["distance"])

    # Take top results and format
    top_results = all_results[:n_results]
    context_parts = []
    for r in top_results:
        context_parts.append(f"[Source: {r['source']}]\n{r['text']}")

    return "\n\n---\n\n".join(context_parts)
