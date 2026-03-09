"""Tests for the FastAPI REST endpoints."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentreplay.models import NodeType, Run, TraceNode
from agentreplay.server import app
from agentreplay.sqlite_store import SQLiteStore


@pytest.fixture(autouse=True)
def patch_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SQLiteStore:
    store = SQLiteStore(db_path=tmp_path / "api_test.db")
    import agentreplay.server as server_mod

    monkeypatch.setattr(server_mod, "_get_store", lambda: store)
    return store


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_runs_empty(client: TestClient) -> None:
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_get_run_not_found(client: TestClient) -> None:
    r = client.get("/api/runs/fake-id")
    assert r.status_code == 404


def test_list_and_get_run(client: TestClient, patch_store: SQLiteStore) -> None:
    run = Run(name="my-run", start_time=time.time())
    patch_store.upsert_run(run)

    r = client.get("/api/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "my-run"

    r2 = client.get(f"/api/runs/{run.id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == run.id


def test_list_nodes(client: TestClient, patch_store: SQLiteStore) -> None:
    run = Run(name="run", start_time=time.time())
    patch_store.upsert_run(run)
    node = TraceNode(
        run_id=run.id,
        node_type=NodeType.TOOL,
        name="search",
        start_time=time.time(),
        inputs={"query": "python"},
    )
    patch_store.upsert_node(node)

    r = client.get(f"/api/runs/{run.id}/nodes")
    assert r.status_code == 200
    nodes = r.json()
    assert len(nodes) == 1
    assert nodes[0]["name"] == "search"
