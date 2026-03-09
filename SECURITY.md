# Security Policy

## Scope

AgentReplay is a **local development tool**. It is designed to run on your own machine, bound to `127.0.0.1`, with no network exposure.

## Reporting a Vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

Please report security issues via [GitHub private security advisories](https://github.com/Gustav-Proxi/agentreplay/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive a response within 48 hours.

## Known Security Considerations

These are **by design** limitations of the current MVP. Tracked issues are linked.

| Issue | Severity | Status | Issue |
|---|---|---|---|
| Trace data stored as plaintext (prompts may contain API keys, PII) | HIGH | Open | [#1](https://github.com/Gustav-Proxi/agentreplay/issues/1) |
| No authentication on REST endpoints | MEDIUM | Open | [#2](https://github.com/Gustav-Proxi/agentreplay/issues/2) |
| No HTTPS/TLS | MEDIUM | Open | [#3](https://github.com/Gustav-Proxi/agentreplay/issues/3) |

## Safe Usage Guidelines

1. **Never commit `.agentreplay.db` to git.** Add it to `.gitignore`.
2. **Do not expose port 7474 externally.** The server binds to `127.0.0.1` by default.
3. **Do not run AgentReplay on a shared server** with untrusted users until authentication is implemented (#2).
4. **Treat the DB file like a log file** — it contains your full prompt history.

## Fixed Vulnerabilities

| Issue | Fixed in | Description |
|---|---|---|
| CORS `allow_origins=["*"]` | v0.1.1 | Restricted to localhost only |
| Default host `0.0.0.0` | v0.1.1 | Changed to `127.0.0.1` |
| Path traversal via `--db` | v0.1.1 | Validates against home/tmp/cwd |
| Monkey-patch state race conditions | v0.1.1 | Added `threading.Lock` |
| Unbounded database growth | v0.1.1 | 500MB cap + 7-day retention |
| N+1 query in LangChain callback | v0.1.1 | Replaced with indexed `get_node()` |
| Missing SQLite indexes | v0.1.1 | Added on `run_id`, `start_time` |
| No connection timeout | v0.1.1 | `timeout=5.0` on `sqlite3.connect` |
