"""Tests for SQLiteStore."""
import time
from pathlib import Path

import pytest

from agentreplay.models import NodeType, Run, RunStatus, TraceNode
from agentreplay.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(db_path=tmp_path / "test.db")


def make_run() -> Run:
    return Run(name="test-run", start_time=time.time())


def make_node(run_id: str, parent_id: str | None = None) -> TraceNode:
    return TraceNode(
        run_id=run_id,
        parent_id=parent_id,
        node_type=NodeType.LLM,
        name="gpt-4o",
        start_time=time.time(),
        inputs={"prompts": ["Hello"]},
    )


def test_upsert_and_get_run(store: SQLiteStore) -> None:
    run = make_run()
    store.upsert_run(run)
    fetched = store.get_run(run.id)
    assert fetched is not None
    assert fetched.name == "test-run"
    assert fetched.status == RunStatus.RUNNING


def test_run_update_on_finish(store: SQLiteStore) -> None:
    run = make_run()
    store.upsert_run(run)
    run.finish()
    store.upsert_run(run)
    fetched = store.get_run(run.id)
    assert fetched is not None
    assert fetched.status == RunStatus.SUCCESS
    assert fetched.end_time is not None


def test_list_runs(store: SQLiteStore) -> None:
    for i in range(3):
        r = Run(name=f"run-{i}", start_time=time.time())
        store.upsert_run(r)
    runs = store.list_runs()
    assert len(runs) == 3


def test_upsert_node(store: SQLiteStore) -> None:
    run = make_run()
    store.upsert_run(run)
    node = make_node(run.id)
    store.upsert_node(node)
    nodes = store.list_nodes(run.id)
    assert len(nodes) == 1
    assert nodes[0].name == "gpt-4o"


def test_node_dag_parent(store: SQLiteStore) -> None:
    run = make_run()
    store.upsert_run(run)
    parent = make_node(run.id)
    store.upsert_node(parent)
    child = make_node(run.id, parent_id=parent.id)
    store.upsert_node(child)
    nodes = store.list_nodes(run.id)
    assert len(nodes) == 2
    child_fetched = next(n for n in nodes if n.parent_id == parent.id)
    assert child_fetched is not None


def test_node_finish_updates(store: SQLiteStore) -> None:
    run = make_run()
    store.upsert_run(run)
    node = make_node(run.id)
    store.upsert_node(node)
    node.finish(outputs={"result": "Paris"})
    node.token_usage = {"total_tokens": 42}
    store.upsert_node(node)
    fetched = store.list_nodes(run.id)[0]
    assert fetched.outputs == {"result": "Paris"}
    assert fetched.token_usage == {"total_tokens": 42}
    assert fetched.end_time is not None


def test_get_nonexistent_run(store: SQLiteStore) -> None:
    assert store.get_run("does-not-exist") is None
