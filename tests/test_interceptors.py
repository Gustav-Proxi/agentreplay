"""Tests for AgentReplay interceptors (OpenAI, Anthropic, smolagents)."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agentreplay.models import NodeType, RunStatus, TraceNode
from agentreplay.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(db_path=tmp_path / "test.db")


# ============================================================================
# OpenAI Patch Tests
# ============================================================================


class TestOpenAIPatch:
    """Tests for openai_patch.patch/unpatch."""

    def test_patch_without_openai_installed(self) -> None:
        """Patch should raise ImportError with helpful message if openai not installed."""
        from agentreplay.interceptors import openai_patch

        # Save original state
        original_patch_state = openai_patch._patch_state.copy()

        try:
            # Mock openai as not importable
            with patch.dict(sys.modules, {"openai": None}):
                with pytest.raises(ImportError, match="openai package not found"):
                    openai_patch.patch("test-run-id")
        finally:
            # Restore state
            openai_patch._patch_state.clear()
            openai_patch._patch_state.update(original_patch_state)
            openai_patch.unpatch()

    def test_patch_and_unpatch_restore_original(self, store: SQLiteStore) -> None:
        """Patching and unpatching should restore original OpenAI methods."""
        from agentreplay.interceptors import openai_patch

        # Create mock openai module
        mock_openai = MagicMock()
        original_sync_create = MagicMock()
        original_async_create = AsyncMock()
        mock_openai.OpenAI.chat.completions.create = original_sync_create
        mock_openai.AsyncOpenAI.chat.completions.create = original_async_create

        original_patch_state = openai_patch._patch_state.copy()

        try:
            with patch.dict(sys.modules, {"openai": mock_openai}):
                openai_patch.patch("test-run-id", store)
                assert openai_patch._patch_state["patched"]
                assert mock_openai.OpenAI.chat.completions.create != original_sync_create

                openai_patch.unpatch()
                assert not openai_patch._patch_state["patched"]
                assert mock_openai.OpenAI.chat.completions.create == original_sync_create
        finally:
            openai_patch._patch_state.clear()
            openai_patch._patch_state.update(original_patch_state)

    def test_successful_sync_call_records_node(self, store: SQLiteStore) -> None:
        """Successful chat.completions.create call should record a node."""
        from agentreplay.interceptors import openai_patch

        # Setup mocks
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        original_create = MagicMock(return_value=mock_response)
        mock_openai.OpenAI.chat.completions.create = original_create
        mock_openai.AsyncOpenAI.chat.completions.create = AsyncMock()

        original_patch_state = openai_patch._patch_state.copy()

        try:
            with patch.dict(sys.modules, {"openai": mock_openai}):
                openai_patch.patch("test-run-id", store)

                # Create a mock client instance and call patched create
                mock_client = MagicMock()
                patched_create = mock_openai.OpenAI.chat.completions.create
                result = patched_create(
                    mock_client,
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hi"}],
                )

                # Verify response returned
                assert result == mock_response

                # Verify node was recorded
                nodes = store.list_nodes("test-run-id")
                assert len(nodes) == 1
                node = nodes[0]
                assert node.node_type == NodeType.LLM
                assert node.name == "openai_gpt-4"
                assert node.inputs["model"] == "gpt-4"
                assert node.outputs["content"] == "Hello, world!"
                assert node.outputs["finish_reason"] == "stop"
                assert node.token_usage == {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                }
        finally:
            openai_patch._patch_state.clear()
            openai_patch._patch_state.update(original_patch_state)
            openai_patch.unpatch()

    def test_sync_call_exception_records_error(self, store: SQLiteStore) -> None:
        """Exception in chat.completions.create should record error on node."""
        from agentreplay.interceptors import openai_patch

        mock_openai = MagicMock()

        def raise_error(*args: object, **kwargs: object) -> None:
            raise ValueError("API rate limited")

        original_create = raise_error
        mock_openai.OpenAI.chat.completions.create = original_create
        mock_openai.AsyncOpenAI.chat.completions.create = AsyncMock()

        original_patch_state = openai_patch._patch_state.copy()

        try:
            with patch.dict(sys.modules, {"openai": mock_openai}):
                openai_patch.patch("test-run-id", store)

                # Save original for patching
                openai_patch._original_openai_create = original_create
                openai_patch._original_openai_async_create = AsyncMock()

                # Call should raise
                mock_client = MagicMock()
                with pytest.raises(ValueError, match="API rate limited"):
                    openai_patch._patched_create_sync(
                        mock_client, model="gpt-4", messages=[]
                    )

                # Verify error was recorded
                nodes = store.list_nodes("test-run-id")
                assert len(nodes) == 1
                node = nodes[0]
                assert node.error is not None
                assert "API rate limited" in node.error
                assert node.end_time is not None
        finally:
            openai_patch._patch_state.clear()
            openai_patch._patch_state.update(original_patch_state)
            openai_patch.unpatch()

    def test_patched_context_manager(self, store: SQLiteStore) -> None:
        """Context manager should patch and unpatch automatically."""
        from agentreplay.interceptors import openai_patch

        mock_openai = MagicMock()
        original_create = MagicMock()
        mock_openai.OpenAI.chat.completions.create = original_create
        mock_openai.AsyncOpenAI.chat.completions.create = AsyncMock()

        with patch.dict(sys.modules, {"openai": mock_openai}):
            with openai_patch.patched("test-run-id", store):
                assert openai_patch._patch_state["patched"]
                assert mock_openai.OpenAI.chat.completions.create != original_create

            assert not openai_patch._patch_state["patched"]
            assert mock_openai.OpenAI.chat.completions.create == original_create


# ============================================================================
# Anthropic Patch Tests
# ============================================================================


class TestAnthropicPatch:
    """Tests for anthropic_patch (if it exists)."""

    def test_anthropic_patch_exists_or_skip(self) -> None:
        """Test that anthropic_patch can be imported if it exists."""
        try:
            from agentreplay.interceptors import anthropic_patch  # noqa: F401

            # If import succeeds, test exists (placeholder for actual tests)
            assert True
        except ImportError:
            pytest.skip("anthropic_patch not yet implemented")


# ============================================================================
# SmolaGents Wrapper Tests
# ============================================================================


class TestSmolagentsWrap:
    """Tests for smolagents_patch.wrap function."""

    def test_wrap_without_smolagents_installed(self, store: SQLiteStore) -> None:
        """wrap() should raise ImportError with helpful message if smolagents not installed."""
        from agentreplay.interceptors import smolagents_patch

        with patch.dict(sys.modules, {"smolagents": None}):
            with pytest.raises(ImportError, match="smolagents package not found"):
                smolagents_patch.wrap(MagicMock(), store=store)

    def test_wrap_non_multistepagent_raises_typeerror(
        self, store: SQLiteStore
    ) -> None:
        """wrap() should raise TypeError if agent is not a MultiStepAgent."""
        from agentreplay.interceptors import smolagents_patch

        mock_smolagents = MagicMock()

        class FakeAgent:
            pass

        mock_smolagents.MultiStepAgent = MagicMock()

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            with pytest.raises(TypeError, match="must be an instance of smolagents"):
                smolagents_patch.wrap(FakeAgent(), store=store)

    def test_wrap_successful_run_records_root_node(self, store: SQLiteStore) -> None:
        """Successful agent.run() should record root AGENT node with task input and result output."""
        from agentreplay.interceptors import smolagents_patch

        # Mock smolagents
        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def run(self, task: str) -> str:
                return "Task completed successfully"

        mock_agent = MockMultiStepAgent()
        mock_smolagents.MultiStepAgent = type(mock_agent)

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            wrapped = smolagents_patch.wrap(
                mock_agent, run_name="test-run", store=store
            )
            result = wrapped.run("What is 2+2?")

            assert result == "Task completed successfully"

            # Verify run was created
            runs = store.list_runs()
            assert len(runs) == 1
            run = runs[0]
            assert run.name == "test-run"
            assert run.status == RunStatus.SUCCESS

            # Verify root node was created
            nodes = store.list_nodes(run.id)
            assert len(nodes) == 1
            root_node = nodes[0]
            assert root_node.node_type == NodeType.AGENT
            assert root_node.name == "smolagents_run"
            assert root_node.parent_id is None
            assert root_node.inputs == {"task": "What is 2+2?"}
            assert root_node.outputs == {"result": "Task completed successfully"}
            assert root_node.error is None
            assert root_node.end_time is not None

    def test_wrap_run_exception_records_error(self, store: SQLiteStore) -> None:
        """Exception in agent.run() should record error on root node and run."""
        from agentreplay.interceptors import smolagents_patch

        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def run(self, task: str) -> str:
                raise RuntimeError("Agent failed")

        mock_agent = MockMultiStepAgent()
        mock_smolagents.MultiStepAgent = type(mock_agent)

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            wrapped = smolagents_patch.wrap(mock_agent, store=store)

            with pytest.raises(RuntimeError, match="Agent failed"):
                wrapped.run("What is 2+2?")

            # Verify run was recorded with error
            runs = store.list_runs()
            assert len(runs) == 1
            run = runs[0]
            assert run.status == RunStatus.ERROR

            # Verify node was recorded with error
            nodes = store.list_nodes(run.id)
            assert len(nodes) == 1
            root_node = nodes[0]
            assert root_node.error is not None
            assert "Agent failed" in root_node.error
            assert root_node.end_time is not None

    def test_wrap_with_step_method_records_child_nodes(
        self, store: SQLiteStore
    ) -> None:
        """Agent.step() calls should record child CHAIN nodes."""
        from agentreplay.interceptors import smolagents_patch

        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def __init__(self) -> None:
                self.step_count = 0

            def step(self) -> dict[str, object]:
                self.step_count += 1
                return {"step": self.step_count, "action": "think"}

            def run(self, task: str) -> str:
                # Simulate calling step internally
                self.step()
                self.step()
                return "Done"

        mock_agent = MockMultiStepAgent()
        mock_smolagents.MultiStepAgent = type(mock_agent)

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            wrapped = smolagents_patch.wrap(mock_agent, store=store)
            result = wrapped.run("Test task")

            assert result == "Done"

            # Verify nodes
            runs = store.list_runs()
            run_id = runs[0].id
            nodes = store.list_nodes(run_id)

            # Should have 1 root + 2 step nodes
            assert len(nodes) == 3
            root = nodes[0]
            assert root.node_type == NodeType.AGENT
            assert root.parent_id is None

            # Step nodes should be children of root
            step_nodes = [n for n in nodes if n.node_type == NodeType.CHAIN]
            assert len(step_nodes) == 2
            for step_node in step_nodes:
                assert step_node.parent_id == root.id

    def test_wrap_uses_default_store(self) -> None:
        """wrap() should use get_default_store() if store is None."""
        from agentreplay.interceptors import smolagents_patch
        from agentreplay.sqlite_store import get_default_store

        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def run(self, task: str) -> str:
                return "OK"

        mock_agent = MockMultiStepAgent()
        mock_smolagents.MultiStepAgent = type(mock_agent)

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            wrapped = smolagents_patch.wrap(mock_agent)  # No store param
            result = wrapped.run("Test")

            assert result == "OK"

            # Verify it used the default store
            default_store = get_default_store()
            runs = default_store.list_runs()
            assert len(runs) > 0

    def test_wrap_forwards_other_attributes(self, store: SQLiteStore) -> None:
        """Wrapped agent should forward non-run attributes to original agent."""
        from agentreplay.interceptors import smolagents_patch

        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def __init__(self) -> None:
                self.config = {"max_steps": 10}
                self.model = "gpt-4"

            def run(self, task: str) -> str:
                return "OK"

        mock_agent = MockMultiStepAgent()
        mock_smolagents.MultiStepAgent = type(mock_agent)

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            wrapped = smolagents_patch.wrap(mock_agent, store=store)

            # Should be able to access original attributes
            assert wrapped.config == {"max_steps": 10}
            assert wrapped.model == "gpt-4"


# ============================================================================
# Integration Tests
# ============================================================================


class TestInterceptorIntegration:
    """Integration tests for multiple interceptors."""

    def test_multiple_runs_same_store(self, store: SQLiteStore) -> None:
        """Multiple runs should all be recorded in the same store."""
        from agentreplay.interceptors import smolagents_patch

        mock_smolagents = MagicMock()

        class MockMultiStepAgent:
            def __init__(self, name: str):
                self.name = name

            def run(self, task: str) -> str:
                return f"{self.name}: {task}"

        mock_smolagents.MultiStepAgent = MockMultiStepAgent

        with patch.dict(sys.modules, {"smolagents": mock_smolagents}):
            agent1 = MockMultiStepAgent("Agent1")
            agent2 = MockMultiStepAgent("Agent2")

            wrapped1 = smolagents_patch.wrap(
                agent1, run_name="run1", store=store
            )
            wrapped2 = smolagents_patch.wrap(
                agent2, run_name="run2", store=store
            )

            wrapped1.run("Task A")
            wrapped2.run("Task B")

            # Verify both runs recorded
            runs = store.list_runs()
            assert len(runs) == 2
            assert any(r.name == "run1" for r in runs)
            assert any(r.name == "run2" for r in runs)
