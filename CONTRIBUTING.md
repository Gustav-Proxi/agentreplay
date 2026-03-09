# Contributing to AgentReplay

Thank you for your interest in contributing! AgentReplay is a local-first, zero-telemetry time-travel debugger for LLM agents.

---

## Where to Start

- **Good first issues:** [`good first issue`](https://github.com/Gustav-Proxi/agentreplay/labels/good%20first%20issue) — small, well-scoped tasks ideal for getting familiar with the codebase
- **Help wanted:** [`help wanted`](https://github.com/Gustav-Proxi/agentreplay/labels/help%20wanted) — larger tasks where we'd love community input
- **Security:** [`security`](https://github.com/Gustav-Proxi/agentreplay/labels/security) — hardening tasks (encryption, auth, TLS)

---

## Development Setup

**Requirements:** Python 3.11+, Node.js 18+

```bash
git clone https://github.com/Gustav-Proxi/agentreplay
cd agentreplay

# Python backend
pip install -e ".[dev]"

# React dashboard
cd ui && npm install && npm run dev   # dev server at http://localhost:5173
# (proxies /api to http://localhost:7474)

# Run tests
python -m pytest tests/ -v

# Start API server (separate terminal)
python -m agentreplay --no-browser
```

---

## Project Structure

```
agentreplay/
├── agentreplay/               # Python package
│   ├── models.py              # Pydantic schemas: Run, TraceNode, NodeType
│   ├── sqlite_store.py        # Thread-safe SQLite store (WAL, indexes, retention)
│   ├── server.py              # FastAPI REST API + background serve()
│   ├── __main__.py            # CLI entrypoint: python -m agentreplay
│   └── interceptors/
│       ├── langchain.py       # LangChain BaseCallbackHandler
│       ├── openai_patch.py    # OpenAI monkey-patch (sync + async)
│       ├── anthropic_patch.py # Anthropic monkey-patch (sync + async)
│       └── smolagents_patch.py# smolagents wrap() proxy
├── ui/                        # React + Vite frontend
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── RunList.tsx
│       │   ├── TimelineView.tsx
│       │   └── PayloadInspector.tsx
│       └── hooks/useApi.ts
├── tests/                     # pytest test suite
│   ├── test_store.py
│   ├── test_api.py
│   └── test_interceptors.py
└── examples/                  # Runnable examples
```

---

## Adding a New Interceptor

Follow `interceptors/openai_patch.py` as a template:

1. Create `agentreplay/interceptors/<provider>_patch.py`
2. Implement `patch(run_id, store)`, `unpatch()`, `patched()` context manager
3. Use `threading.Lock` for `_patch_state` (thread safety — see the security audit)
4. Lazy-import the SDK with a helpful error message
5. Map provider fields to `TraceNode` schema
6. Add tests in `tests/test_interceptors.py` — mock the SDK, no real API keys
7. Export from `interceptors/__init__.py`

---

## Code Standards

- **Type hints:** Always. Strict mypy compatible.
- **Formatting:** `black` + `isort` (run `black . && isort .` before committing)
- **Tests:** All new features need tests. Mock external SDKs — no API keys in tests.
- **No breaking changes** to `SQLiteStore` or `TraceNode` schemas without a migration path.

---

## Pull Request Process

1. Fork the repo, create a branch: `git checkout -b feature/your-feature`
2. Make your changes with tests
3. Run the full suite: `python -m pytest tests/ -v`
4. Push and open a PR against `main`
5. Fill in the PR template (linked to the relevant issue)
6. A maintainer will review within 48 hours

---

## Security Vulnerabilities

**Do not open public issues for security vulnerabilities.**

Email the maintainer directly or open a [private security advisory](https://github.com/Gustav-Proxi/agentreplay/security/advisories/new) on GitHub.

See the [security label](https://github.com/Gustav-Proxi/agentreplay/labels/security) for known issues being tracked publicly (non-critical hardening tasks).

---

## Design Philosophy

AgentReplay follows the same principles as [VectorLens](https://github.com/Gustav-Proxi/vectorlens):

- **Invisible infrastructure:** zero Docker, zero Postgres, zero accounts. One `pip install`.
- **Local-first, zero telemetry:** your prompts and agent data never leave your machine.
- **Drop-in, not intrusive:** one callback or one context manager. No code rewrites.
- **Immutable audit trail:** every step is an append-only DAG node. No mutation of history.
