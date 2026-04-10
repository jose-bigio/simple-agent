"""System prompt components for each memory strategy."""

_HIERARCHY_OVERVIEW = """\
## Memory System

You have access to a hierarchical memory store organised as an org chart.
Namespaces use "/" as a separator: "ACorp/Engineering/Tim".
Always search memories BEFORE answering questions that may rely on prior context.
"""

_FIXED_ENTITIES = """\
## Known Entities (fixed hierarchy)

Only save memories for the following predefined entities:

  ACorp                          (company)
  ACorp/Engineering              (department)
  ACorp/Engineering/Tim          (person)
  ACorp/Engineering/Tim/Bob      (person)
  ACorp/Engineering/Tim/Jim      (person)
  ACorp/HR                       (department)
  ACorp/HR/Karen                 (person)

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


def get_system_prompt(strategy: str) -> str:
    """Assemble the system prompt for a given memory strategy.

    Args:
        strategy: One of "profile_fixed", "profile_evolving",
                  "episodic_fixed", "episodic_evolving".
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
    return "\n".join(parts)
