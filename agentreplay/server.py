"""FastAPI REST server exposing AgentReplay data, with background daemon launcher."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import Run, TraceNode
from .sqlite_store import SQLiteStore, get_default_store

app = FastAPI(title="AgentReplay", version="0.1.0")

# Restrict CORS to localhost only — prevents remote pages exfiltrating trace data
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:7474",
        "http://127.0.0.1:7474",
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

# Serve compiled React UI assets
_UI_DIR = Path(__file__).parent / "ui_dist"
if (_UI_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_UI_DIR / "assets")), name="assets")


def _get_store() -> SQLiteStore:
    return get_default_store()


# ------------------------------------------------------------------
# Runs endpoints
# ------------------------------------------------------------------


@app.get("/api/runs", response_model=list[Run])
def list_runs(
    limit: int = 50,
    status: str | None = None,
    q: str | None = None
) -> list[Run]:

    limit = min(limit, 200)

    return _get_store().list_runs(
        limit=limit,
        status=status,
        search=q
    )


@app.get("/api/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    run = _get_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ------------------------------------------------------------------
# Nodes endpoints
# ------------------------------------------------------------------


@app.get("/api/runs/{run_id}/nodes", response_model=list[TraceNode])
def list_nodes(run_id: str) -> list[TraceNode]:
    store = _get_store()
    if not store.get_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return store.list_nodes(run_id)


# ------------------------------------------------------------------
# Serve dashboard root
# ------------------------------------------------------------------


@app.get("/")
def root() -> Any:
    index = _UI_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "message": "AgentReplay API is running. UI not built yet.",
        "docs": "/docs",
        "runs": "/api/runs",
    }


# ------------------------------------------------------------------
# Background daemon
# ------------------------------------------------------------------

_server_thread: threading.Thread | None = None


def serve(
    host: str = "127.0.0.1",
    port: int = 7474,
    open_browser: bool = False,
) -> None:
    """Start the AgentReplay server in a background daemon thread.

    Safe to call multiple times — starts only once.

    Warning: if host is changed to "0.0.0.0" the dashboard becomes
    network-accessible and will expose all trace data (prompts, outputs).
    """
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    _server_thread = threading.Thread(target=_run, daemon=True, name="agentreplay-server")
    _server_thread.start()

    if open_browser:
        import time
        import webbrowser

        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")

    print(f"AgentReplay dashboard: http://localhost:{port}")
