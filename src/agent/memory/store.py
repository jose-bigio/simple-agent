"""Memory store setup for hierarchical entity memory strategies."""

from datetime import UTC, datetime

from langgraph.store.memory import InMemoryStore


def namespace_from_path(path: str) -> tuple[str, ...]:
    """Convert a slash-delimited path to a namespace tuple.

    Examples:
        "ACorp/Engineering/Tim" -> ("ACorp", "Engineering", "Tim")
        "ACorp" -> ("ACorp",)
    """
    return tuple(p.strip() for p in path.split("/") if p.strip())


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Lazily initialised embedding function using Ollama nomic-embed-text.

    Requires Ollama to be running locally with the nomic-embed-text model pulled:
        ollama pull nomic-embed-text
    """
    from langchain.embeddings import init_embeddings
    model = init_embeddings("ollama:nomic-embed-text")
    return model.embed_documents(texts)


def make_store() -> InMemoryStore:
    """Create an InMemoryStore with Ollama nomic-embed-text vector embeddings (lazily loaded).

    Requires Ollama running locally with nomic-embed-text pulled.
    Embeddings are only generated when .put() or .search(query=...) is called.
    """
    return InMemoryStore(index={"embed": _embed_texts, "dims": 768})


def now_iso() -> str:
    """Return the current UTC time as a sortable ISO 8601 string (seconds precision)."""
    return datetime.now(UTC).isoformat(timespec="seconds")
