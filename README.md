# simple-agent

A minimal LLM agent built on [LangChain Deep Agents](https://github.com/langchain-ai/deepagents). Supports OpenAI, Anthropic, and Google models out of the box. Two ways to run it — pick one:

- [CLI guide](docs/cli.md) — interactive terminal chat
- [Fullstack guide](docs/fullstack.md) — FastAPI server + React frontend

---

## Core agent

The agent lives in `src/agent/core.py` and exposes a single factory:

```python
from agent.core import make_agent

agent = make_agent(
    model_str="anthropic:claude-haiku-4-5-20251001",  # provider:model
    system_prompt=None,                                # optional override
)
```

It wraps LangChain's `init_chat_model` + `create_deep_agent` and returns a compiled LangGraph agent that supports `.invoke()`, `.stream()`, and `.astream()`.

## Supported providers

| Provider  | Model string example                            | Required env var    |
|-----------|-------------------------------------------------|---------------------|
| Anthropic | `anthropic:claude-haiku-4-5-20251001` (default) | `ANTHROPIC_API_KEY` |
| OpenAI    | `openai:gpt-4o`                                 | `OPENAI_API_KEY`    |
| Google    | `google_genai:gemini-2.5-flash`                 | `GOOGLE_API_KEY`    |

Any model supported by LangChain's [`init_chat_model`](https://python.langchain.com/docs/how_to/chat_models_universal_init/) works — just pass the `provider:model` string.

### Running with Ollama (local models)

1. Install [Ollama](https://ollama.com) and the LangChain integration:
   ```bash
   uv pip install langchain-ollama
   ```

2. Pull the embedding model used by the memory store:
   ```bash
   ollama pull nomic-embed-text
   ```

3. Keep the embedding model running (required when using `--memory`):
   ```bash
   ollama run nomic-embed-text
   ```

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- At least one LLM provider API key

## Initial setup

```bash
git clone https://github.com/valkai-tech/simple-agent-public.git
cd simple-agent-public
uv sync
cp .env.example .env
# Fill in your API key(s) in .env
```

## Memory strategies

The agent supports four cross-session memory strategies, enabled with `--memory`:

| Strategy           | Storage model  | Hierarchy       | Loading       |
|--------------------|---------------|-----------------|---------------|
| `profile_fixed`    | Summary/overwrite | Predefined schema | Whole file  |
| `profile_evolving` | Summary/overwrite | Discovered on the fly | Whole file |
| `episodic_fixed`   | Append-only events | Predefined schema | Lazy (per-entity dir) |
| `episodic_evolving`| Append-only events | Discovered on the fly | Lazy (per-entity dir) |

**Profile** strategies maintain a current-state summary — updates overwrite old facts, so historical information is lost.  
**Episodic** strategies append each new fact as a timestamped event — full history is retained but current state requires reading all episodes.  
**Fixed** hierarchies use a predefined schema (suited to org-chart-style data) — novel entity types (locations, events, relationships) may be dropped.  
**Evolving** hierarchies discover and create new entity types on the fly — handles any domain but requires more LLM calls.

```bash
# Start a session with memory
uv run chat --memory episodic_evolving --memory-dir /tmp/my_memory
```

### Memory test scripts

Two seeding scripts let you compare how each strategy handles the same story:

**Corporate merger story** — introduces employees across two companies, role changes, and a merger:
```bash
./scripts/seed_corp.sh --memory profile_fixed
./scripts/seed_corp.sh --memory episodic_evolving
# Then ask: "What is Amy's work history?" and compare answers
```

**Neighborhood story** — a non-corporate narrative with neighbors, an injury, family relations, and a local store; designed to stress-test fixed hierarchies:
```bash
./scripts/seed_story.sh --memory profile_fixed
./scripts/seed_story.sh --memory episodic_evolving
# Then ask: "Who is Betsy?" and "What store sells ice cream?"
```

Both scripts default `--memory-dir` to `/tmp/<strategy>/corp` or `/tmp/<strategy>/story`. After seeding they print the exact `chat` command and suggested questions to run interactively.

**What each story reveals:**

| Question | profile failure | fixed hierarchy failure |
|---|---|---|
| "What is Amy's work history?" | Returns only HR (Engineering overwritten) | — |
| "What is Josh's last role?" | May drop Accountant history | — |
| "Who is Betsy?" | — | No family-relation slot; may store as bare person |
| "What store sells ice cream?" | — | No store/location schema slot; fact likely dropped |

## Running evals

```bash
uv run pytest evals/ -v
```

Evals make real LLM calls (not mocked) to verify provider integration end-to-end.

## Project structure

```
simple-agent/
├── README.md               # this file — core concepts
├── docs/
│   ├── cli.md              # CLI usage guide
│   └── fullstack.md        # server + frontend guide
├── pyproject.toml          # uv project config and dependencies
├── .env.example            # API key template
├── src/
│   └── agent/
│       ├── core.py         # agent factory (shared by both approaches)
│       ├── cli.py          # CLI entry point
│       └── server.py       # FastAPI server entry point
├── frontend/               # React chat UI
└── evals/
    └── test_agent.py       # pytest evals
```
