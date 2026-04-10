from typing import Literal

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

MemoryStrategy = Literal[
    "profile_fixed",
    "profile_evolving",
    "episodic_fixed",
    "episodic_evolving",
]


def make_agent(
    model_str: str = "anthropic:claude-haiku-4-5-20251001",
    system_prompt: str | None = None,
):
    """Create a deep agent with the specified model provider.

    Args:
        model_str: Provider and model in "provider:model" format.
                   Examples: "openai:gpt-4o", "anthropic:claude-haiku-4-5-20251001",
                   "google_genai:gemini-2.5-flash"
        system_prompt: Optional system prompt override.

    Returns:
        A compiled LangGraph agent supporting .invoke(), .stream(), .astream().
    """
    model = init_chat_model(model_str)
    kwargs = {}
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    return create_deep_agent(model=model, **kwargs)


def make_agent_with_memory(
    strategy: MemoryStrategy,
    model_str: str = "anthropic:claude-haiku-4-5-20251001",
    system_prompt: str | None = None,
    *,
    store: InMemoryStore | None = None,
) -> tuple:
    """Create a deep agent configured for a specific memory strategy.

    All strategies use InMemoryStore with OpenAI vector embeddings for
    cross-invocation persistence. A shared InMemorySaver checkpointer
    keeps conversation history within a thread.

    Args:
        strategy: One of "profile_fixed", "profile_evolving",
                  "episodic_fixed", "episodic_evolving".
        model_str: Provider and model in "provider:model" format.
        system_prompt: Optional additional system prompt prepended before
                       the strategy-specific memory instructions.

    Returns:
        (agent, store) tuple. Pass the same store to multiple agent
        invocations to share memory across conversations. Inspect the
        store directly in tests to assert on stored content.
    """
    from agent.memory import get_system_prompt, get_tools, make_store, seed_hierarchy

    if store is None:
        store = make_store()
    if "fixed" in strategy:
        seed_hierarchy(store)

    memory_prompt = get_system_prompt(strategy)
    combined_prompt = (
        f"{system_prompt}\n\n{memory_prompt}" if system_prompt else memory_prompt
    )

    model = init_chat_model(model_str)
    tools = get_tools(strategy)
    checkpointer = InMemorySaver()

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=combined_prompt,
        store=store,
        checkpointer=checkpointer,
    )
    return agent, store
