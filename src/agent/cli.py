import argparse
import atexit
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from agent.core import MemoryStrategy, make_agent, make_agent_with_memory

MEMORY_CHOICES = ["profile_fixed", "profile_evolving", "episodic_fixed", "episodic_evolving"]


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="CLI Chat Agent")
    parser.add_argument(
        "--model",
        default="anthropic:claude-haiku-4-5-20251001",
        help="Model string, e.g. openai:gpt-4o, anthropic:claude-haiku-4-5-20251001, google_genai:gemini-2.5-flash",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="Custom system prompt",
    )
    parser.add_argument(
        "--memory",
        default=None,
        choices=MEMORY_CHOICES,
        help="Memory strategy: profile_fixed, profile_evolving, episodic_fixed, episodic_evolving",
    )
    parser.add_argument(
        "--memory-file",
        default=None,
        metavar="PATH",
        help="Override default memory persistence file path (default: ~/.simple_agent_memory_{strategy}.json)",
    )
    parser.add_argument(
        "--no-reindex",
        action="store_true",
        default=False,
        help="Load memories without re-embedding (no OpenAI API cost on startup). Items will be scoreless in semantic search.",
    )
    args = parser.parse_args()

    if args.memory:
        from agent.memory import make_store
        from agent.memory.persistence import default_memory_path, load_store, save_store

        memory_path = Path(args.memory_file) if args.memory_file else default_memory_path(args.memory)

        # Create store first so we can pass it into make_agent_with_memory,
        # which seeds the hierarchy (for fixed strategies) before we load
        # persisted data on top.
        store = make_store()
        agent, store = make_agent_with_memory(args.memory, args.model, args.system, store=store)

        reindex = not args.no_reindex
        item_count = load_store(store, memory_path, reindex=reindex)
        if item_count > 0:
            print(f"Loaded {item_count} memories from {memory_path}")

        atexit.register(save_store, store, memory_path)

        thread_id = str(uuid.uuid4())
        print(f"Memory strategy: {args.memory}")
        print(f"Memory file: {memory_path}")
        print(f"Thread ID: {thread_id}  (memories persist across sessions)\n")
    else:
        agent = make_agent(args.model, args.system)
        thread_id = None
        messages = []

    print("Chat started. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        if thread_id:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                {"configurable": {"thread_id": thread_id}},
            )
        else:
            messages.append({"role": "user", "content": user_input})
            result = agent.invoke({"messages": messages})
            messages = result["messages"]

        ai_msg = result["messages"][-1]
        print(f"\nAssistant: {ai_msg.content}\n")

    if args.memory:
        save_store(store, memory_path)
        print(f"Memories saved to {memory_path}")


if __name__ == "__main__":
    main()
