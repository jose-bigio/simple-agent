"""System prompt components for each memory strategy."""

_HIERARCHY_OVERVIEW = """\
## Memory System

You have access to a hierarchical memory store organised as an org chart.
Namespaces use "/" as a separator: "ACorp/Engineering/Tim".
Always search memories BEFORE answering questions that may rely on prior context.
"""

_FIXED_ENTITIES = """\
## Known Entities (fixed hierarchy)

Only save memories if they are of type:

 - Company
 - Department
 - Person

And maintain that hierarchy

Do not attempt to save memories for entities outside this list.
"""

_EVOLVING_ENTITIES = """\
## Dynamic Hierarchy (evolving)

You may discover new entities during conversation. When you learn about a new
person, team, or department:
1. Call create_entity(entity_path, entity_type) to register it.
   entity_type must be one of: "company", "department", "team", "person", "role"
2. Infer the correct parent from context — e.g. if Sarah reports to Bob who is
   under Engineering, use "ACorp/Engineering/Bob/Sarah".
3. Then save their profile or first episode.
"""

_PROFILE_INSTRUCTIONS = """\
## Memory Strategy: Profile (snapshot)

- Call save_profile(entity_path, facts_json) whenever you learn facts about an entity.
- facts_json must be a complete JSON object with ALL known facts — it REPLACES the
  previous profile entirely. If you only learned one new fact, still include the old facts.
- Example: save_profile("ACorp/Engineering/Tim",
    '{"role": "VP Engineering", "reports_to": "CEO", "direct_reports": ["Bob", "Jim"]}')
- Use search_memories(query, namespace_prefix) to recall information before responding.
- Use get_entity(entity_path) to retrieve the current profile for a specific person.
"""

_EPISODIC_INSTRUCTIONS = """\
## Memory Strategy: Episodic (append-only log)

- Call save_episode(entity_path, content) to record what you learned about an entity.
- Each call appends a NEW timestamped entry — old entries are never overwritten.
- Record significant facts, role changes, relationships, and updates as separate episodes.
- Example: save_episode("ACorp/Engineering/Tim",
    "Tim is the Engineering Lead. Manages Bob and Jim directly.")
- When something changes: save_episode("ACorp/Engineering/Tim",
    "Tim was promoted to VP Engineering. Previously Engineering Lead.")
- Use search_memories(query, namespace_prefix) to recall relevant episodes.
- Use get_entity(entity_path) to list all episodes for a specific person.
"""


_ON_DEMAND_LOADING_INSTRUCTIONS = """\
## On-Demand Memory Loading

Memory is stored as individual files on disk and is NOT pre-loaded into the store.
Before answering any question that may rely on prior context:

1. Call list_memory_entities(namespace_prefix) to see what entities exist on disk.
   Use the entity names in the directory paths to judge relevance — do NOT load
   everything speculatively.
2. For each entity that seems relevant to the current question, call
   load_entity_from_disk(entity_path, key) to pull it into the active store.
   Common key values: "profile" (profile strategies). For episodic strategies,
   load "profile" first, then call get_entity to discover episode keys.
3. Then call search_memories or get_entity as normal to read the loaded content.

Only load entities that are plausibly relevant. Unrelated entities should stay on disk.
"""


def get_system_prompt(strategy: str, *, memory_dir: bool = False) -> str:
    """Assemble the system prompt for a given memory strategy.

    Args:
        strategy: One of "profile_fixed", "profile_evolving",
                  "episodic_fixed", "episodic_evolving".
        memory_dir: If True, append on-demand loading instructions for the
                    directory-based persistence mode.
    """
    parts = [_HIERARCHY_OVERVIEW]
    if "fixed" in strategy:
        parts.append(_FIXED_ENTITIES)
    else:
        parts.append(_EVOLVING_ENTITIES)
    if "profile" in strategy:
        parts.append(_PROFILE_INSTRUCTIONS)
    else:
        parts.append(_EPISODIC_INSTRUCTIONS)
    if memory_dir:
        parts.append(_ON_DEMAND_LOADING_INSTRUCTIONS)
    return "\n".join(parts)
