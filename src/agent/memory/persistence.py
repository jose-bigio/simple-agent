"""Cross-session persistence for InMemoryStore.

Serializes all store items to JSON on shutdown and restores them on startup.
Embeddings (vectors) are NOT serialized — they are regenerated on load when
reindex=True (the default), or skipped with reindex=False for free/instant
loading (items will appear scoreless in vector search).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from langgraph.store.base import Item
from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)


def default_memory_path(strategy: str) -> Path:
    """Return ~/.simple_agent_memory_{strategy}.json."""
    return Path.home() / f".simple_agent_memory_{strategy}.json"


def save_store(store: InMemoryStore, path: Path) -> None:
    """Serialize all store items to JSON at path.

    Writes atomically via a temp file to avoid corruption on Ctrl+C.
    Safe to call multiple times (atexit + explicit call).
    """
    items: list[dict] = []
    for ns_dict in store._data.values():
        for item in ns_dict.values():
            items.append({
                "namespace": list(item.namespace),
                "key": item.key,
                "value": item.value,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            })

    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
        tmp.replace(path)
        logger.info("Saved %d memory items to %s", len(items), path)
    except OSError as exc:
        logger.warning("Failed to save memory store to %s: %s", path, exc)
        tmp.unlink(missing_ok=True)


def load_store(store: InMemoryStore, path: Path, *, reindex: bool = True) -> int:
    """Load persisted items from path into store.

    Args:
        store: Target InMemoryStore to populate (must already have embeddings
               configured if reindex=True).
        path: JSON file written by save_store().
        reindex: If True (default), re-put each item via store.put() so
                 embeddings are regenerated — costs OpenAI API calls but
                 restores full semantic search scoring. If False, insert Items
                 directly into store._data preserving timestamps but leaving
                 items scoreless in vector search.

    Returns:
        Number of items loaded, or 0 if file does not exist.
    """
    if not path.exists():
        logger.info("No memory file at %s — starting fresh", path)
        return 0

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read memory file %s: %s — starting fresh", path, exc)
        return 0

    count = 0
    for item_dict in raw:
        ns = tuple(item_dict["namespace"])
        key = item_dict["key"]
        value = item_dict["value"]

        if reindex:
            store.put(ns, key, value)
        else:
            created = datetime.fromisoformat(item_dict["created_at"])
            updated = datetime.fromisoformat(item_dict["updated_at"])
            item = Item(
                namespace=ns,
                key=key,
                value=value,
                created_at=created,
                updated_at=updated,
            )
            store._data[ns][key] = item

        count += 1

    logger.info("Loaded %d memory items from %s (reindex=%s)", count, path, reindex)
    return count
