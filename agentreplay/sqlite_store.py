"""Thread-safe SQLite event store for AgentReplay."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .models import Run, RunStatus, TraceNode

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    start_time  REAL NOT NULL,
    end_time    REAL,
    status      TEXT NOT NULL DEFAULT 'running',
    metadata    TEXT NOT NULL DEFAULT '{}'
)
"""

_CREATE_NODES = """
CREATE TABLE IF NOT EXISTS trace_nodes (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES runs(id),
    parent_id   TEXT,
    node_type   TEXT NOT NULL,
    name        TEXT NOT NULL,
    start_time  REAL NOT NULL,
    end_time    REAL,
    inputs      TEXT NOT NULL DEFAULT '{}',
    outputs     TEXT NOT NULL DEFAULT '{}',
    error       TEXT,
    token_usage TEXT,
    model_name  TEXT
)
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_nodes_run_id       ON trace_nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_nodes_run_start    ON trace_nodes(run_id, start_time);
CREATE INDEX IF NOT EXISTS idx_runs_start_time    ON runs(start_time DESC);
"""

# 500 MB default cap; older runs pruned when exceeded
_DEFAULT_MAX_DB_MB = 500
_DEFAULT_RETENTION_DAYS = 7
_MAX_QUERY_LIMIT = 1_000


class SQLiteStore:
    """Manages all persistence for AgentReplay using a local SQLite file."""

    def __init__(
        self,
        db_path: str | Path = ".agentreplay.db",
        max_db_mb: int = _DEFAULT_MAX_DB_MB,
        retention_days: int = _DEFAULT_RETENTION_DAYS,
    ) -> None:
        self._path = Path(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._max_db_bytes = max_db_mb * 1024 * 1024
        self._retention_days = retention_days
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection management (one connection per thread)
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                timeout=5.0,  # prevent indefinite hangs on lock contention
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._conn()
            conn.execute(_CREATE_RUNS)
            conn.execute(_CREATE_NODES)
            conn.executescript(_CREATE_INDEXES)
            conn.commit()

    def _maybe_prune(self) -> None:
        """Prune old runs if DB exceeds size cap. Called before every upsert."""
        try:
            size = os.path.getsize(self._path)
        except OSError:
            return
        if size < self._max_db_bytes:
            return
        cutoff = time.time() - self._retention_days * 86400
        conn = self._conn()
        conn.execute("DELETE FROM trace_nodes WHERE run_id IN (SELECT id FROM runs WHERE start_time < ?)", (cutoff,))
        conn.execute("DELETE FROM runs WHERE start_time < ?", (cutoff,))
        conn.execute("VACUUM")
        conn.commit()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def upsert_run(self, run: Run) -> None:
        sql = """
        INSERT INTO runs (id, name, start_time, end_time, status, metadata)
        VALUES (:id, :name, :start_time, :end_time, :status, :metadata)
        ON CONFLICT(id) DO UPDATE SET
            end_time = excluded.end_time,
            status   = excluded.status,
            metadata = excluded.metadata
        """
        with self._lock:
            self._maybe_prune()
            self._conn().execute(
                sql,
                {
                    "id": run.id,
                    "name": run.name,
                    "start_time": run.start_time,
                    "end_time": run.end_time,
                    "status": run.status.value,
                    "metadata": json.dumps(run.metadata),
                },
            )
            self._conn().commit()

    def get_run(self, run_id: str) -> Run | None:
        row = self._conn().execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self, limit: int = 50) -> list[Run]:
        limit = min(limit, _MAX_QUERY_LIMIT)
        rows = self._conn().execute(
            "SELECT * FROM runs ORDER BY start_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_run(r) for r in rows]

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def upsert_node(self, node: TraceNode) -> None:
        sql = """
        INSERT INTO trace_nodes
            (id, run_id, parent_id, node_type, name,
             start_time, end_time, inputs, outputs, error, token_usage, model_name)
        VALUES
            (:id, :run_id, :parent_id, :node_type, :name,
             :start_time, :end_time, :inputs, :outputs, :error, :token_usage, :model_name)
        ON CONFLICT(id) DO UPDATE SET
            end_time    = excluded.end_time,
            outputs     = excluded.outputs,
            error       = excluded.error,
            token_usage = excluded.token_usage
        """
        with self._lock:
            self._maybe_prune()
            self._conn().execute(
                sql,
                {
                    "id": node.id,
                    "run_id": node.run_id,
                    "parent_id": node.parent_id,
                    "node_type": node.node_type.value,
                    "name": node.name,
                    "start_time": node.start_time,
                    "end_time": node.end_time,
                    "inputs": json.dumps(node.inputs),
                    "outputs": json.dumps(node.outputs),
                    "error": node.error,
                    "token_usage": json.dumps(node.token_usage) if node.token_usage else None,
                    "model_name": node.model_name,
                },
            )
            self._conn().commit()

    def get_node(self, run_id: str, node_id: str) -> TraceNode | None:
        """Fetch a single node by id — avoids the N+1 full-scan pattern."""
        row = self._conn().execute(
            "SELECT * FROM trace_nodes WHERE run_id = ? AND id = ? LIMIT 1",
            (run_id, node_id),
        ).fetchone()
        return _row_to_node(row) if row else None

    def list_nodes(self, run_id: str) -> list[TraceNode]:
        rows = self._conn().execute(
            "SELECT * FROM trace_nodes WHERE run_id = ? ORDER BY start_time ASC",
            (run_id,),
        ).fetchall()
        return [_row_to_node(r) for r in rows]


# ------------------------------------------------------------------
# Row → Model helpers
# ------------------------------------------------------------------


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        id=row["id"],
        name=row["name"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        status=RunStatus(row["status"]),
        metadata=json.loads(row["metadata"]),
    )


def _row_to_node(row: sqlite3.Row) -> TraceNode:
    return TraceNode(
        id=row["id"],
        run_id=row["run_id"],
        parent_id=row["parent_id"],
        node_type=row["node_type"],
        name=row["name"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        inputs=json.loads(row["inputs"]),
        outputs=json.loads(row["outputs"]),
        error=row["error"],
        token_usage=json.loads(row["token_usage"]) if row["token_usage"] else None,
        model_name=row["model_name"],
    )


# Module-level default store (lazy-init on first access)
_default_store: SQLiteStore | None = None
_store_lock = threading.Lock()


def get_default_store() -> SQLiteStore:
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = SQLiteStore()
    return _default_store
