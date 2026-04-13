"""Memory tools for agent strategies.

All tools access the InMemoryStore via the injected ToolRuntime.
The store is populated by `create_agent_with_memory` and shared across invocations.

Tool availability per strategy:
    profile_fixed:    search_memories, get_entity, save_profile
    profile_evolving: search_memories, get_entity, save_profile, create_entity
    episodic_fixed:   search_memories, get_entity, save_episode
    episodic_evolving: search_memories, get_entity, save_episode, create_entity

When memory_dir is provided to get_tools(), two additional closure-based tools are
prepended: list_memory_entities and load_entity_from_disk, which enable on-demand
loading from the directory-based persistence layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from .store import namespace_from_path, now_iso

if TYPE_CHECKING:
    pass


@tool
def search_memories(query: str, namespace_prefix: str, runtime: ToolRuntime) -> str:
    """Search stored memories by semantic similarity within a namespace subtree.

    Use this BEFORE responding to any question that might rely on previously
    stored information.

    Args:
        query: Natural language description of what you're looking for.
        namespace_prefix: Root of the hierarchy to search, e.g. "ACorp" to
            search all of A Corp, or "ACorp/Engineering" for just engineering.

    Returns:
        Matching memory entries with their paths and content.
    """
    ns = namespace_from_path(namespace_prefix)
    results = runtime.store.search(ns, query=query, limit=10)
    if not results:
        return f"No memories found for query '{query}' in namespace '{namespace_prefix}'."
    lines = []
    for item in results:
        path = "/".join(item.namespace)
        score = f" (score={item.score:.3f})" if item.score is not None else ""
        lines.append(f"[{path}] {item.key}{score}: {json.dumps(item.value)}")
    return "\n".join(lines)


@tool
def get_entity(entity_path: str, runtime: ToolRuntime) -> str:
    """Retrieve stored data for a specific entity.

    For profile strategies: returns the current profile document.
    For episodic strategies: lists all accumulated episodes, oldest first.

    Args:
        entity_path: Full path to the entity, e.g. "ACorp/Engineering/Tim".

    Returns:
        Profile document or list of episodes for the entity.
    """
    ns = namespace_from_path(entity_path)
    profile = runtime.store.get(ns, "profile")
    if profile is not None:
        return f"Profile for {entity_path}:\n{json.dumps(profile.value, indent=2)}"

    # No profile — try listing episodes
    items = runtime.store.search(ns, limit=50)
    if not items:
        return f"No data found for entity '{entity_path}'."
    episodes = sorted(
        [item for item in items if item.key.startswith("episode-")],
        key=lambda x: x.key,
    )
    if not episodes:
        return f"No episodes found for entity '{entity_path}'."
    lines = [f"Episodes for {entity_path} ({len(episodes)} total):"]
    for ep in episodes:
        lines.append(f"  {ep.key}: {ep.value.get('content', json.dumps(ep.value))}")
    return "\n".join(lines)


@tool
def save_profile(entity_path: str, facts_json: str, runtime: ToolRuntime) -> str:
    """Save or update the profile for an entity (profile strategy).

    This REPLACES the entire profile — include all known facts, not just changes.
    Call this whenever you learn new information about an entity.

    Args:
        entity_path: Full path to the entity, e.g. "ACorp/Engineering/Tim".
        facts_json: JSON object with all known facts about the entity.
            Example: {"role": "VP Engineering", "reports_to": "CEO",
                      "direct_reports": ["Bob", "Jim"], "location": "SF"}

    Returns:
        Confirmation message.
    """
    ns = namespace_from_path(entity_path)
    try:
        facts = json.loads(facts_json)
    except json.JSONDecodeError as exc:
        return f"Error: facts_json must be valid JSON. {exc}"
    if not isinstance(facts, dict):
        return "Error: facts_json must be a JSON object (dict), not a list or scalar."
    runtime.store.put(ns, "profile", {"entity_type": "unknown", "name": ns[-1], **facts})
    return f"Saved profile for '{entity_path}'."


@tool
def save_episode(entity_path: str, content: str, runtime: ToolRuntime) -> str:
    """Record a timestamped observation about an entity (episodic strategy).

    Episodes accumulate — each call appends a new entry. Use this to record
    significant facts, relationship changes, or updates learned during conversation.

    Args:
        entity_path: Full path to the entity, e.g. "ACorp/Engineering/Tim".
        content: Plain-text description of what was learned or observed.
            Example: "Tim was promoted to VP Engineering. Previously Engineering Lead."

    Returns:
        Confirmation message with the episode key.
    """
    ns = namespace_from_path(entity_path)
    timestamp = now_iso()
    key = f"episode-{timestamp}"
    runtime.store.put(ns, key, {"content": content, "timestamp": timestamp})
    return f"Saved episode for '{entity_path}' as '{key}'."


@tool
def create_entity(entity_path: str, entity_type: str, runtime: ToolRuntime) -> str:
    """Register a new entity in the memory hierarchy (evolving strategies only).

    Must be called before saving a profile or episode for an entity that does
    not yet exist. Infer the correct parent path from context.

    Args:
        entity_path: Full slash-delimited path for the new entity.
            Example: "ACorp/Engineering/Tim/Sarah"
        entity_type: One of: "company", "department", "team", "person", "role".

    Returns:
        Confirmation, or an error if the entity already exists.
    """
    ns = namespace_from_path(entity_path)
    existing = runtime.store.get(ns, "profile")
    if existing is not None:
        return f"Entity '{entity_path}' already exists. Use save_profile to update it."
    runtime.store.put(ns, "profile", {"entity_type": entity_type, "name": ns[-1], "facts": {}})
    return f"Created entity '{entity_path}' of type '{entity_type}'."


def get_tools(strategy: str, memory_dir: Path | None = None) -> list:
    """Return the appropriate tool list for a given memory strategy.

    Args:
        strategy: One of the MemoryStrategy literals.
        memory_dir: If provided, two additional tools are prepended —
                    list_memory_entities and load_entity_from_disk — which enable
                    on-demand loading from a directory-based persistence layer.
    """
    common = [search_memories, get_entity]
    if "profile" in strategy:
        tools = [*common, save_profile]
    else:
        tools = [*common, save_episode]
    if "evolving" in strategy:
        tools.append(create_entity)

    if memory_dir is not None:
        from .persistence import list_entities_dir, load_entity_dir

        _memory_dir = memory_dir  # capture for closures

        @tool
        def list_memory_entities(namespace_prefix: str) -> str:
            """List all entity memory files available on disk under a namespace prefix.

            Call this BEFORE answering any question that may rely on prior context,
            to discover what entities are stored. Use the entity names in the returned
            paths to judge relevance — do NOT load everything speculatively.

            Args:
                namespace_prefix: Root of the hierarchy to scan, e.g. "ACorp" to list
                    all entities, or "ACorp/Engineering" for just engineering.

            Returns:
                Formatted list of available entity paths and their keys.
            """
            ns = namespace_from_path(namespace_prefix) if namespace_prefix.strip() else ()
            entries = list_entities_dir(_memory_dir, ns)
            if not entries:
                return f"No memory files found under '{namespace_prefix}' in {_memory_dir}."
            lines = [f"{e['namespace_path']} / {e['key']}" for e in entries]
            return "\n".join(lines)

        @tool
        def load_entity_from_disk(entity_path: str, key: str, runtime: ToolRuntime) -> str:
            """Load a specific entity's memory file from disk into the active store.

            Call this after list_memory_entities identifies a relevant entity, and
            before calling search_memories or get_entity to read its content.

            Args:
                entity_path: Full path to the entity, e.g. "ACorp/Engineering/Tim".
                key: The item key to load, e.g. "profile". For episodic strategies,
                     use get_entity after loading to list available episode keys.

            Returns:
                Confirmation of whether the item was loaded, already present, or not found.
            """
            ns = namespace_from_path(entity_path)
            already_present = runtime.store._data.get(ns, {}).get(key) is not None
            loaded = load_entity_dir(runtime.store, _memory_dir, ns, key)
            if already_present:
                return f"'{entity_path}/{key}' already in store — skipped disk read."
            if loaded:
                return f"Loaded '{entity_path}/{key}' into memory store."
            return f"No file found for '{entity_path}/{key}' on disk."

        tools = [list_memory_entities, load_entity_from_disk, *tools]

    return tools
