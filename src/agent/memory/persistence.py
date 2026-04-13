"""Cross-session persistence for InMemoryStore.

Two persistence modes are provided:

Single-file mode (original):
  Serializes all store items to one JSON file on shutdown and restores them on
  startup. Embeddings are NOT serialized — regenerated on load when reindex=True.

Directory mode (on-demand):
  Each store item is saved as its own JSON file in a directory hierarchy that
  mirrors the namespace structure, e.g.:
      <memory_dir>/ACorp/Engineering/Tim/profile.json
  Files are loaded on demand by the agent rather than eagerly at startup.
  Key names that contain "/" are encoded as "__SLASH__" in filenames.
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


def default_memory_dir(strategy: str) -> Path:
    """Return ~/.simple_agent_memory_{strategy}/ for directory-based persistence."""
    return Path.home() / f".simple_agent_memory_{strategy}"


# ---------------------------------------------------------------------------
# Helpers shared by directory-mode functions
# ---------------------------------------------------------------------------

def _key_to_filename(key: str) -> str:
    """Encode a store key as a safe filename stem (handles keys containing '/')."""
    return key.replace("/", "__SLASH__")


def _filename_to_key(stem: str) -> str:
    """Decode a filename stem back to the original store key."""
    return stem.replace("__SLASH__", "/")


# ---------------------------------------------------------------------------
# Directory-mode persistence
# ---------------------------------------------------------------------------

def save_store_dir(store: InMemoryStore, memory_dir: Path) -> int:
    """Serialize each store item to its own JSON file under memory_dir.

    Directory structure mirrors the namespace hierarchy:
        memory_dir / <ns[0]> / <ns[1]> / ... / <key>.json

    Each file contains {"value": ..., "created_at": ..., "updated_at": ...}.
    The namespace and key are inferred from the file path on load, so they are
    not redundantly stored inside the file.

    Writes atomically via a .tmp sibling + rename to avoid corruption on Ctrl+C.

    Returns:
        Number of files written.
    """
    count = 0
    for ns_dict in store._data.values():
        for item in ns_dict.values():
            rel_parts = list(item.namespace) + [_key_to_filename(item.key) + ".json"]
            file_path = memory_dir.joinpath(*rel_parts)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            payload = {
                "value": item.value,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            tmp = file_path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                tmp.replace(file_path)
                count += 1
            except OSError as exc:
                logger.warning("Failed to save %s: %s", file_path, exc)
                tmp.unlink(missing_ok=True)

    logger.info("Saved %d memory items to directory %s", count, memory_dir)
    return count


def load_entity_dir(
    store: InMemoryStore,
    memory_dir: Path,
    namespace: tuple[str, ...],
    key: str,
    *,
    reindex: bool = True,
) -> bool:
    """Load a single entity item from disk into the store.

    Args:
        store: Target InMemoryStore to populate.
        memory_dir: Root directory written by save_store_dir().
        namespace: Namespace tuple, e.g. ("ACorp", "Engineering", "Tim").
        key: Item key, e.g. "profile".
        reindex: If True (default), re-put the item via store.put() so embeddings
                 are regenerated. If False, insert directly without embedding.

    Returns:
        True if the item was loaded (or was already in the store), False if the
        file does not exist on disk.
    """
    # Skip if already present to avoid redundant embedding cost.
    if store._data.get(namespace, {}).get(key) is not None:
        logger.debug("Entity %s/%s already in store, skipping disk read.", namespace, key)
        return True

    file_path = memory_dir.joinpath(*namespace, _key_to_filename(key) + ".json")
    if not file_path.exists():
        logger.debug("No file at %s — entity not found.", file_path)
        return False

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s: %s", file_path, exc)
        return False

    value = payload["value"]
    if reindex:
        store.put(namespace, key, value)
    else:
        created = datetime.fromisoformat(payload["created_at"])
        updated = datetime.fromisoformat(payload["updated_at"])
        item = Item(namespace=namespace, key=key, value=value, created_at=created, updated_at=updated)
        store._data.setdefault(namespace, {})[key] = item

    logger.info("Loaded %s/%s from %s (reindex=%s)", namespace, key, file_path, reindex)
    return True


def list_entities_dir(
    memory_dir: Path,
    namespace_prefix: tuple[str, ...] = (),
) -> list[dict]:
    """List all entity items available on disk under namespace_prefix.

    Traverses the directory tree without loading any file contents into the store.
    The directory structure itself encodes namespace and key.

    Args:
        memory_dir: Root directory written by save_store_dir().
        namespace_prefix: Optional namespace tuple to restrict the scan.

    Returns:
        List of {"namespace_path": "ACorp/Engineering/Tim", "key": "profile"} dicts.
        Returns [] if the directory does not exist.
    """
    root = memory_dir.joinpath(*namespace_prefix) if namespace_prefix else memory_dir
    if not root.exists():
        return []

    results = []
    for json_file in sorted(root.rglob("*.json")):
        rel = json_file.relative_to(memory_dir)
        # Parts: (*namespace_parts, key_filename)
        parts = rel.parts
        namespace_parts = parts[:-1]
        key = _filename_to_key(json_file.stem)
        results.append({
            "namespace_path": "/".join(namespace_parts),
            "key": key,
        })
    return results


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
