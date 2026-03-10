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


def test_get_node(client: TestClient, patch_store: SQLiteStore) -> None:
    run = Run(name="run", start_time=time.time())
    patch_store.upsert_run(run)
    node = TraceNode(
        run_id=run.id,
        node_type=NodeType.TOOL,
        name="search",
        start_time=time.time(),
    )
    patch_store.upsert_node(node)

    r = client.get(f"/api/runs/{run.id}/nodes/{node.id}")
    assert r.status_code == 200
    assert r.json()["id"] == node.id
    assert r.json()["name"] == "search"


def test_get_node_not_found(client: TestClient, patch_store: SQLiteStore) -> None:
    run = Run(name="run", start_time=time.time())
    patch_store.upsert_run(run)

    r = client.get(f"/api/runs/{run.id}/nodes/fake-node-id")
    assert r.status_code == 404


def test_get_run_stats(client: TestClient, patch_store: SQLiteStore) -> None:
    now = time.time()
    run = Run(name="run", start_time=now, end_time=now + 4.231)
    run.status = run.status  # keep default
    patch_store.upsert_run(run)

    nodes = [
        TraceNode(run_id=run.id, node_type=NodeType.LLM, name="llm1", start_time=now, token_usage={"total_tokens": 300}),
        TraceNode(run_id=run.id, node_type=NodeType.LLM, name="llm2", start_time=now, token_usage={"total_tokens": 242}),
        TraceNode(run_id=run.id, node_type=NodeType.LLM, name="llm3", start_time=now, token_usage={"total_tokens": 300}),
        TraceNode(run_id=run.id, node_type=NodeType.TOOL, name="tool1", start_time=now),
        TraceNode(run_id=run.id, node_type=NodeType.TOOL, name="tool2", start_time=now),
        TraceNode(run_id=run.id, node_type=NodeType.CHAIN, name="chain1", start_time=now),
        TraceNode(run_id=run.id, node_type=NodeType.AGENT, name="agent1", start_time=now),
    ]
    for n in nodes:
        patch_store.upsert_node(n)

    r = client.get(f"/api/runs/{run.id}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == run.id
    assert data["total_nodes"] == 7
    assert data["by_type"]["llm"] == 3
    assert data["by_type"]["tool"] == 2
    assert data["by_type"]["chain"] == 1
    assert data["by_type"]["agent"] == 1
    assert data["total_tokens"] == 842


def test_get_run_stats_not_found(client: TestClient) -> None:
    r = client.get("/api/runs/fake-id/stats")
    assert r.status_code == 404
