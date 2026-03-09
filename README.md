# AgentReplay

**Time-travel debugger for LLM agents.**

When your agent fails on step 6 of 10, `stdout` JSON dumps are useless. AgentReplay intercepts every step, stores the exact state into a local SQLite DAG, and gives you a dashboard to scrub *backward in time* — seeing the precise context window, tool payloads, and token usage at any millisecond.

---

## Why AgentReplay?

| Problem | AgentReplay |
|---|---|
| Agent hallucinates on step 4 | Time-scrub slider rewinds to exactly what the LLM saw |
| Agent loops — why won't it break out? | Visual diff context window iteration 3 vs 4 (roadmap) |
| "It worked last time!" | Every run is immutably stored — replay any historical execution |
| Debugging across frameworks | LangChain, OpenAI, Anthropic, smolagents — one tool |
| Telemetry goes to the cloud | Zero-telemetry. Everything stays on your machine. |

---

## Quick Start

```bash
pip install agentreplay
```

### LangChain (drop-in callback)

```python
from agentreplay.interceptors.langchain import AgentReplayCallback

cb = AgentReplayCallback(run_name="my-research-agent")
result = agent.invoke({"input": "What caused the 2008 financial crisis?"},
                      config={"callbacks": [cb]})

cb.serve()  # opens http://localhost:7474
```

### Raw OpenAI (monkey-patch)

```python
from agentreplay.interceptors.openai_patch import patched
import agentreplay

run = agentreplay.Run(name="openai-debug", start_time=__import__("time").time())
agentreplay.get_default_store().upsert_run(run)

with patched(run.id):
    response = openai.OpenAI().chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )

agentreplay.serve()  # http://localhost:7474
```

### Anthropic

```python
from agentreplay.interceptors.anthropic_patch import patched

with patched(run.id):
    response = anthropic.Anthropic().messages.create(...)
```

### smolagents

```python
from agentreplay.interceptors.smolagents_patch import wrap

wrapped_agent = wrap(agent, run_name="my-smolagent")
result = wrapped_agent.run("Solve this problem")
```

---

## Dashboard

```bash
# Start the dashboard (opens http://localhost:7474)
python -m agentreplay

# Custom port or DB path
python -m agentreplay --port 8080 --db /path/to/.agentreplay.db
```

**Three-panel layout:**

```
┌──────────────┬─────────────────────────┬──────────────────────┐
│   Run List   │     Timeline (DAG)      │   Payload Inspector  │
│              │                         │                      │
│ • run-1  ✓  │ ▾ 🤖 AGENT ResearchAgent│ name: gpt-4o         │
│ • run-2  ✗  │   ▾ ⛓ CHAIN Planning    │ latency: 843ms       │
│ • run-3  ●  │     🧠 LLM gpt-4o       │ tokens: 274          │
│             │   🔧 TOOL WebSearch      │                      │
│             │   🧠 LLM gpt-4o         │ inputs: {            │
│             │ ─────────────────────── │   "prompts": [...]   │
│             │ [time-scrub slider ────]│ }                    │
└─────────────┴─────────────────────────┴──────────────────────┘
```

**Time-scrub:** Drag the slider to roll back the agent's visible state to any point in time. See exactly what the LLM saw before it went wrong.

---

## Architecture

```
Your Agent Code
      │
      ▼
┌─────────────────────────────────────┐
│         Auto-Interceptors           │
│  LangChain  │  OpenAI  │ Anthropic  │
│  Callback   │  Patch   │   Patch    │
└─────────────────┬───────────────────┘
                  │ TraceNode (immutable)
                  ▼
┌─────────────────────────────────────┐
│        SQLite Event Store           │
│  .agentreplay.db (WAL, indexed)     │
│  runs table + trace_nodes DAG       │
└─────────────────┬───────────────────┘
                  │ REST API
                  ▼
┌─────────────────────────────────────┐
│        FastAPI Server               │
│  GET /api/runs                      │
│  GET /api/runs/{id}/nodes           │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│     React + Tailwind Dashboard      │
│  TimelineView │ PayloadInspector    │
│  ScrubBar     │ RunList             │
└─────────────────────────────────────┘
```

---

## Data Model

Every agent step is an **immutable DAG node**:

```python
class TraceNode(BaseModel):
    id: str           # UUID
    run_id: str       # links to parent Run
    parent_id: str    # links to parent Node (DAG structure)
    node_type: NodeType  # AGENT | CHAIN | LLM | TOOL

    start_time: float
    end_time: float

    inputs: dict      # exact payload sent to LLM/tool
    outputs: dict     # exact response received
    error: str        # exception message if failed
    token_usage: dict # prompt_tokens, completion_tokens, total_tokens
    model_name: str   # e.g. "gpt-4o"
```

---

## Security

AgentReplay is a **local-only development tool**. It is designed for use on your own machine:

- Server binds to `127.0.0.1` by default (not network-accessible)
- CORS restricted to localhost origins only
- No telemetry, no cloud, no accounts
- All data stays in `.agentreplay.db` on your filesystem

**Important:** LLM prompts often contain sensitive data (API keys, PII, customer data). The database is stored as plaintext SQLite. Do not commit `.agentreplay.db` to git. Add it to `.gitignore`:

```
.agentreplay.db
```

See [open security issues](https://github.com/Gustav-Proxi/agentreplay/labels/security) for planned hardening (encryption at rest, auth, TLS).

---

## Roadmap

| Feature | Status |
|---|---|
| LangChain interceptor | ✅ Done |
| OpenAI + Anthropic patches | ✅ Done |
| smolagents wrapper | ✅ Done |
| Time-scrub slider | ✅ Done |
| DB indexes + retention policy | ✅ Done |
| **Fork & Replay** | 🗺️ Planned |
| **Visual diffing** | 🗺️ Planned |
| **Live WebSocket streaming** | 🗺️ Planned |
| **Gemini + Mistral interceptors** | 🗺️ Planned |
| **pytest plugin** | 🗺️ Planned |
| **Trace export/import** | 🗺️ Planned |
| **Token cost calculator** | 🗺️ Planned |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

Good first issues are tagged [`good first issue`](https://github.com/Gustav-Proxi/agentreplay/labels/good%20first%20issue).

---

## Related Projects

- [VectorLens](https://github.com/Gustav-Proxi/vectorlens) — sister tool for RAG pipelines. Token-level attribution showing which retrieved chunks caused each output sentence.
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) — full observability platform (evaluation, datasets). AgentReplay is narrower: a debugger, not a platform.
- [LangSmith](https://smith.langchain.com) — cloud-hosted tracing for LangChain. AgentReplay is local-first with zero telemetry.

---

## License

MIT — see [LICENSE](LICENSE).
