"""Agent memory strategy test harness.

Tests are organised into two groups:

1. Existing baseline tests — verify the stateless agent still works unchanged.
2. Memory strategy tests — parameterised across all four strategies, running
   the same scripted org-chart conversation through each.

Scripted scenario
-----------------
The scenario introduces a fictional company (A Corp) with an engineering org:

  Conversation A (invocation 1-2):
    "I work at A Corp. Tim leads Engineering. He manages Bob and Jim."
    "Karen runs HR at A Corp."

  Conversation B (new invocation — cross-invocation recall):
    "Who does Tim manage?"

  Conversation C:
    "Tim was recently promoted to VP. Update his role."

  Conversation D:
    "What is Tim's current role?"

Expected outcomes
-----------------
- All strategies recall Tim's reports after Conversation B.
- profile_*: Conversation D returns "VP" (previous role overwritten).
- episodic_*: Both old and new role are stored; search returns both.
- profile_evolving / episodic_evolving: can discover and store new entities.
"""

import uuid

import pytest
from dotenv import load_dotenv

from agent.core import make_agent, make_agent_with_memory

load_dotenv()

ALL_STRATEGIES = ["profile_fixed", "profile_evolving", "episodic_fixed", "episodic_evolving"]
EVOLVING_STRATEGIES = ["profile_evolving", "episodic_evolving"]
PROFILE_STRATEGIES = ["profile_fixed", "profile_evolving"]
EPISODIC_STRATEGIES = ["episodic_fixed", "episodic_evolving"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_turn(agent, thread_id: str, message: str) -> str:
    """Invoke the agent with a single new message and return the AI reply."""
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        {"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


# ---------------------------------------------------------------------------
# Baseline tests (unchanged)
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    return make_agent()


def test_agent_responds(agent):
    """Agent should return a non-empty response to a simple question."""
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is 2 + 2?"}]}
    )
    assert len(result["messages"]) > 1
    ai_msg = result["messages"][-1]
    assert ai_msg.content
    assert "4" in ai_msg.content


def test_agent_multi_turn(agent):
    """Agent should handle multi-turn conversation."""
    r1 = agent.invoke(
        {"messages": [{"role": "user", "content": "My name is Alice."}]}
    )
    msgs = r1["messages"]
    msgs.append({"role": "user", "content": "What is my name?"})
    r2 = agent.invoke({"messages": msgs})
    ai_msg = r2["messages"][-1]
    assert "Alice" in ai_msg.content


# ---------------------------------------------------------------------------
# Memory strategy fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(params=ALL_STRATEGIES)
def memory_agent(request):
    """Yields (agent, store, strategy, thread_id) for each strategy."""
    strategy = request.param
    agent, store = make_agent_with_memory(strategy)
    thread_id = str(uuid.uuid4())
    return agent, store, strategy, thread_id


@pytest.fixture(params=EVOLVING_STRATEGIES)
def evolving_memory_agent(request):
    strategy = request.param
    agent, store = make_agent_with_memory(strategy)
    thread_id = str(uuid.uuid4())
    return agent, store, strategy, thread_id


# ---------------------------------------------------------------------------
# Memory strategy tests
# ---------------------------------------------------------------------------

def test_entity_recall(memory_agent):
    """Agent should recall Tim's reports after storing them in a prior turn."""
    agent, store, strategy, thread_id = memory_agent

    # Seed conversation
    run_turn(agent, thread_id, "I work at A Corp. Tim leads Engineering. He manages Bob and Jim.")
    run_turn(agent, thread_id, "Karen runs HR at A Corp.")

    # Cross-invocation recall: new thread, same store
    new_thread = str(uuid.uuid4())
    reply = run_turn(agent, new_thread, "Who does Tim manage at A Corp?")

    assert "Bob" in reply or "Jim" in reply, (
        f"[{strategy}] Expected Tim's reports in reply, got: {reply}"
    )


def test_cross_invocation_recall(memory_agent):
    """Facts stored in one invocation should be recallable in a separate invocation."""
    agent, store, strategy, thread_id = memory_agent

    run_turn(agent, thread_id, "My name is Alice and I work in Engineering at A Corp.")

    new_thread = str(uuid.uuid4())
    reply = run_turn(agent, new_thread, "What do you know about someone named Alice?")

    assert "Alice" in reply, (
        f"[{strategy}] Expected Alice to be recalled across invocations, got: {reply}"
    )


def test_update_profile_behavior(memory_agent):
    """Profile strategies overwrite on update; episodic strategies accumulate."""
    agent, store, strategy, thread_id = memory_agent

    run_turn(agent, thread_id, "Tim is the Engineering Lead at A Corp.")
    run_turn(agent, thread_id, "Tim was promoted to VP Engineering.")

    # Inspect the store directly — don't rely on the agent's reply
    from agent.memory import namespace_from_path
    ns = namespace_from_path("ACorp/Engineering/Tim")

    if strategy in PROFILE_STRATEGIES:
        profile = store.get(ns, "profile")
        assert profile is not None, f"[{strategy}] Expected profile to exist"
        profile_str = str(profile.value).lower()
        assert "vp" in profile_str or "vice president" in profile_str, (
            f"[{strategy}] Expected VP role in profile, got: {profile.value}"
        )

    else:  # episodic
        items = store.search(ns, limit=50)
        episode_contents = [
            item.value.get("content", "").lower()
            for item in items
            if item.key.startswith("episode-")
        ]
        assert any("lead" in c or "engineering lead" in c for c in episode_contents), (
            f"[{strategy}] Expected original role in episodes, got: {episode_contents}"
        )
        assert any("vp" in c or "vice president" in c or "promoted" in c for c in episode_contents), (
            f"[{strategy}] Expected promotion episode, got: {episode_contents}"
        )


def test_evolving_discovers_new_entity(evolving_memory_agent):
    """Evolving strategies should create new entities not in the predefined schema."""
    agent, store, strategy, thread_id = evolving_memory_agent

    run_turn(
        agent,
        thread_id,
        "Sarah just joined Engineering at A Corp. She reports to Bob.",
    )

    # Check that something about Sarah ended up in the store under ACorp/Engineering
    from agent.memory import namespace_from_path
    root_ns = namespace_from_path("ACorp")
    results = store.search(root_ns, query="Sarah", limit=20)

    found = any(
        "sarah" in str(item.value).lower() or "sarah" in "/".join(item.namespace).lower()
        for item in results
    )
    assert found, (
        f"[{strategy}] Expected Sarah to be discoverable in store, "
        f"got namespaces: {[item.namespace for item in results]}"
    )


# ---------------------------------------------------------------------------
# Isolated vector vs exact search comparison
# ---------------------------------------------------------------------------

def test_vector_vs_exact_search():
    """Demonstrate the difference between vector similarity search and exact key lookup.

    Vector search finds semantically related content even without knowing the
    exact key. Exact lookup returns None for an unknown key.
    """
    from agent.memory import make_store, namespace_from_path, seed_hierarchy
    from agent.memory.store import now_iso

    store = make_store()
    seed_hierarchy(store)

    ns = namespace_from_path("ACorp/Engineering/Tim")
    key = f"episode-{now_iso()}"
    store.put(ns, key, {
        "content": "Tim oversees the entire engineering team and sets technical direction.",
        "timestamp": now_iso(),
    })

    # Vector search: semantic query — no knowledge of exact key needed
    results = store.search(
        namespace_from_path("ACorp"),
        query="who is responsible for engineering leadership?",
        limit=5,
    )
    vector_hit = any("tim" in str(item.value).lower() for item in results)
    assert vector_hit, (
        f"Vector search should find Tim for leadership query, got: {results}"
    )

    # Exact lookup with a made-up key: returns None
    missing = store.get(ns, "episode-1970-01-01T00:00:00+00:00")
    assert missing is None, "Exact lookup of unknown key should return None"

    # Exact lookup with the real key: returns the item
    found = store.get(ns, key)
    assert found is not None, "Exact lookup with correct key should return the item"
    assert "tim" in found.value.get("content", "").lower()
