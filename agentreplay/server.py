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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve compiled React UI assets — mount /assets so Vite's generated paths resolve
_UI_DIR = Path(__file__).parent / "ui_dist"
if (_UI_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_UI_DIR / "assets")), name="assets")


def _get_store() -> SQLiteStore:
    return get_default_store()


# ------------------------------------------------------------------
# Runs endpoints
# ------------------------------------------------------------------


@app.get("/api/runs", response_model=list[Run])
def list_runs(limit: int = 50) -> list[Run]:
    return _get_store().list_runs(limit=limit)


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
    host: str = "0.0.0.0",
    port: int = 7474,
    open_browser: bool = False,
) -> None:
    """Start the AgentReplay server in a background daemon thread.

    Safe to call multiple times — starts only once.
    """
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    _server_thread = threading.Thread(target=_run, daemon=True, name="agentreplay-server")
    _server_thread.start()

    if open_browser:
        import time
        import webbrowser

        time.sleep(0.8)  # give uvicorn a moment to bind
        webbrowser.open(f"http://{host}:{port}")

    print(f"AgentReplay dashboard: http://{host}:{port}")
